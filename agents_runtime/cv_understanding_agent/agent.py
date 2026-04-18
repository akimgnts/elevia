from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, Iterable, List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda

from .config import get_llm, get_model_name
from .contracts import AgentSessionRequest, EvidenceItem, QuestionItem, SessionResponse, SkillLinkItem
from .prompts import EXTRACTION_PROMPT, INTEGRATION_PROMPT
from .repository_adapter import prepare_understanding_input


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)
    return cleaned.strip()


def _safe_json_loads(raw_text: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return json.loads(_strip_code_fences(raw_text))
    except Exception:
        return fallback


def _dedupe_strings(values: Iterable[Any]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        label = str(value or "").strip()
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(label)
    return result


def _document_blocks_from_seed(career_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    for index, exp in enumerate(career_profile.get("experiences") or []):
        if not isinstance(exp, dict):
            continue
        blocks.append(
            {
                "id": f"block-exp-{index}",
                "block_type": "experience",
                "label": str(exp.get("title") or "Experience").strip() or "Experience",
                "source_text": " ; ".join(
                    _dedupe_strings(
                        [
                            exp.get("company"),
                            *list(exp.get("responsibilities") or []),
                            *list(exp.get("achievements") or []),
                        ]
                    )
                )
                or None,
                "confidence": 0.8,
                "metadata": {
                    "experience_ref": f"exp-{index}",
                    "company": str(exp.get("company") or "").strip(),
                },
            }
        )
    for index, item in enumerate(career_profile.get("projects") or []):
        if not isinstance(item, dict):
            continue
        blocks.append(
            {
                "id": f"block-proj-{index}",
                "block_type": "project",
                "label": str(item.get("title") or "Project").strip() or "Project",
                "source_text": str(item.get("description") or "").strip() or None,
                "confidence": 0.72,
                "metadata": {"project_ref": f"proj-{index}"},
            }
        )
    for index, item in enumerate(career_profile.get("education") or []):
        label = ""
        if isinstance(item, dict):
            label = " - ".join(
                [part for part in [item.get("degree"), item.get("field"), item.get("institution")] if isinstance(part, str) and part.strip()]
            )
        else:
            label = str(item or "").strip()
        if not label:
            continue
        blocks.append(
            {
                "id": f"block-edu-{index}",
                "block_type": "education",
                "label": label,
                "source_text": label,
                "confidence": 0.68,
                "metadata": {"education_ref": f"edu-{index}"},
            }
        )
    for index, item in enumerate(career_profile.get("certifications") or []):
        label = str(item or "").strip()
        if not label:
            continue
        blocks.append(
            {
                "id": f"block-cert-{index}",
                "block_type": "certification",
                "label": label,
                "source_text": label,
                "confidence": 0.7,
                "metadata": {"certification_ref": f"cert-{index}"},
            }
        )
    return blocks


def _mission_units_from_seed(career_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    mission_units: List[Dict[str, Any]] = []
    for index, exp in enumerate(career_profile.get("experiences") or []):
        if not isinstance(exp, dict):
            continue
        lines = _dedupe_strings(
            [*list(exp.get("responsibilities") or []), *list(exp.get("achievements") or []), *list(exp.get("impact_signals") or [])]
        )
        for mission_index, mission in enumerate(lines):
            mission_units.append(
                {
                    "id": f"exp-{index}-mission-{mission_index}",
                    "block_ref": f"block-exp-{index}",
                    "experience_ref": f"exp-{index}",
                    "mission_text": mission,
                    "context": str(exp.get("company") or exp.get("title") or "").strip() or None,
                    "skill_candidates_open": [],
                    "tool_candidates_open": [],
                    "quantified_signals": [],
                    "autonomy_hypothesis": exp.get("autonomy_level"),
                    "evidence": [
                        {
                            "source_type": "experience_mission",
                            "source_value": mission,
                            "confidence": 0.7,
                            "mapping_status": "seed",
                            "target_path": f"career_profile.experiences[{index}]",
                        }
                    ],
                }
            )
    return mission_units


def _entity_classification_from_seed(career_profile: Dict[str, Any], blocks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    entities: Dict[str, List[Dict[str, Any]]] = {
        "experiences": [],
        "projects": [],
        "education": [],
        "certifications": [],
        "skills": [],
        "tools": [],
    }
    for block in blocks:
        target = f"{block['block_type']}s" if block["block_type"] != "education" else "education"
        if target in entities:
            entities[target].append(
                {
                    "id": block["id"].replace("block-", ""),
                    "entity_type": block["block_type"],
                    "label": block["label"],
                    "confidence": block.get("confidence"),
                    "raw_value": block.get("source_text"),
                    "metadata": block.get("metadata") or {},
                }
            )
    for index, exp in enumerate(career_profile.get("experiences") or []):
        if not isinstance(exp, dict):
            continue
        for skill_index, skill in enumerate(exp.get("canonical_skills_used") or []):
            if not isinstance(skill, dict):
                continue
            label = str(skill.get("label") or "").strip()
            if not label:
                continue
            entities["skills"].append(
                {
                    "id": f"exp-{index}-skill-{skill_index}",
                    "entity_type": "skill",
                    "label": label,
                    "confidence": 0.78,
                    "raw_value": label,
                    "metadata": {"experience_ref": f"exp-{index}", "uri": skill.get("uri")},
                }
            )
        for tool_index, tool in enumerate(exp.get("tools") or []):
            label = str(tool.get("label") if isinstance(tool, dict) else tool).strip()
            if not label:
                continue
            entities["tools"].append(
                {
                    "id": f"exp-{index}-tool-{tool_index}",
                    "entity_type": "tool",
                    "label": label,
                    "confidence": 0.76,
                    "raw_value": label,
                    "metadata": {"experience_ref": f"exp-{index}"},
                }
            )
    return entities


def _fallback_extraction(career_profile: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "summary": "The deterministic profile seed is available, but the LLM extraction failed or returned invalid JSON.",
        "overall_status": "needs_confirmation",
        "skill_links": [],
        "questions": [
            {
                "id": "profile-primary",
                "category": "profile_scope",
                "prompt": "What is the most important experience or skill to confirm first?",
                "field_path": "career_profile.experiences",
                "suggested_answer": None,
                "confidence": 0.2,
                "rationale": "The autonomous runtime could not safely extract structured enrichments from the current input.",
            }
        ]
        if not (career_profile.get("experiences") or [])
        else [],
        "open_signal_notes": [],
    }


class CVUnderstandingAgent:
    def __init__(self) -> None:
        self.name = "cv_understanding_agent"
        self.version = "v1"

    def run(self, request: AgentSessionRequest) -> SessionResponse:
        understanding_input = prepare_understanding_input(request.model_dump())
        career_profile = (
            understanding_input.get("deterministic_profile_seed", {}).get("career_profile_seed")
            or request.profile.get("career_profile")
            or {}
        )
        llm = get_llm()

        extraction_chain = EXTRACTION_PROMPT | llm | StrOutputParser()

        extraction_raw = extraction_chain.invoke(
            {
                "understanding_input_json": json.dumps(understanding_input, ensure_ascii=False, indent=2),
            }
        )
        extraction = _safe_json_loads(extraction_raw, _fallback_extraction(career_profile))

        integration_chain = INTEGRATION_PROMPT | llm | StrOutputParser()
        integration_raw = integration_chain.invoke(
            {
                "career_profile_seed_json": json.dumps(career_profile, ensure_ascii=False, indent=2),
                "extraction_json": json.dumps(extraction, ensure_ascii=False, indent=2),
            }
        )
        integration = _safe_json_loads(
            integration_raw,
            {
                "overall_status": extraction.get("overall_status", "needs_confirmation"),
                "questions": extraction.get("questions", []),
                "skill_links": extraction.get("skill_links", []),
                "confidence_map": {"skill_links": 0.45, "questions": 0.35},
                "patch_notes": ["Fallback integration path used."],
            },
        )

        skill_links = [
            SkillLinkItem(
                experience_ref=item.get("experience_ref"),
                skill=item.get("skill") or {"label": "Unknown", "source": "llm_inference"},
                tools=item.get("tools") or [],
                context=item.get("context"),
                autonomy_level=item.get("autonomy_level"),
                evidence=[
                    EvidenceItem(
                        source_type="llm_inference",
                        source_value=value if isinstance(value, str) else None,
                        confidence=0.6,
                        mapping_status="inferred",
                        target_path=None,
                    )
                    for value in (item.get("evidence") or [])
                ],
            ).model_dump()
            for item in integration.get("skill_links", [])
            if isinstance(item, dict) and isinstance(item.get("skill"), dict) and str(item["skill"].get("label") or "").strip()
        ]

        questions = [
            QuestionItem(
                id=item.get("id") or f"question-{index}",
                category=item.get("category") or "clarification",
                prompt=item.get("prompt") or "Please confirm this point.",
                field_path=item.get("field_path"),
                suggested_answer=item.get("suggested_answer"),
                confidence=item.get("confidence"),
                rationale=item.get("rationale"),
            ).model_dump()
            for index, item in enumerate(integration.get("questions", []))
            if isinstance(item, dict)
        ]

        blocks = _document_blocks_from_seed(career_profile)
        missions = _mission_units_from_seed(career_profile)
        entities = _entity_classification_from_seed(career_profile, blocks)

        merged_career_profile = dict(career_profile)
        merged_experiences = list(merged_career_profile.get("experiences") or [])
        for index, exp in enumerate(merged_experiences):
            if not isinstance(exp, dict):
                continue
            exp_ref = f"exp-{index}"
            exp["skill_links"] = [link for link in skill_links if link.get("experience_ref") == exp_ref]
        merged_career_profile["experiences"] = merged_experiences

        accepted_signal = understanding_input.get("signal_buckets", {}).get("accepted_signal", {})
        ambiguous_signal = understanding_input.get("signal_buckets", {}).get("ambiguous_signal", {})
        rejected_signal = understanding_input.get("signal_buckets", {}).get("rejected_signal", [])
        unmapped_signal = understanding_input.get("signal_buckets", {}).get("unmapped_but_promising_signal", [])

        return SessionResponse(
            session_id=f"ext_pus_{uuid.uuid4().hex[:12]}",
            status="ready",
            provider="langchain_openai",
            trace_summary={
                "mode": "external_llm_runtime",
                "agent_name": self.name,
                "agent_version": self.version,
                "model": get_model_name(),
                "question_count": len(questions),
                "skill_link_count": len(skill_links),
            },
            understanding_input=understanding_input,
            document_blocks=blocks,
            mission_units=missions,
            open_signal={
                "skills": [],
                "tools": [],
                "accepted_signal": accepted_signal,
                "ambiguous_signal": ambiguous_signal,
                "rejected_signal": rejected_signal,
                "unmapped_but_promising_signal": unmapped_signal,
                "open_signal_notes": extraction.get("open_signal_notes", []),
            },
            canonical_signal={
                "mapped_skills": _dedupe_strings(
                    link.get("skill", {}).get("label") for link in skill_links if link.get("skill", {}).get("uri")
                ),
                "skill_link_count": len(skill_links),
            },
            understanding_status={
                "provider_mode": "external_llm_runtime",
                "overall_status": integration.get("overall_status") or extraction.get("overall_status") or "needs_confirmation",
                "understood_count": len(blocks) + len(skill_links),
                "needs_confirmation_count": len(questions),
                "patch_notes": integration.get("patch_notes", []),
            },
            entity_classification=entities,
            proposed_profile_patch={"career_profile": merged_career_profile},
            skill_links=skill_links,
            evidence_map={
                "career_profile.skill_links": [e for link in skill_links for e in (link.get("evidence") or [])],
                "source_context.rejected_tokens": [
                    {
                        "source_type": "rejected_token",
                        "source_value": item.get("label"),
                        "confidence": 0.2,
                        "mapping_status": "rejected",
                    }
                    for item in rejected_signal
                ],
            },
            confidence_map={
                "skill_links": float((integration.get("confidence_map") or {}).get("skill_links") or 0.55),
                "questions": float((integration.get("confidence_map") or {}).get("questions") or 0.45),
            },
            questions=questions,
        )
