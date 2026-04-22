from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from compass.canonical.canonical_store import get_canonical_store

from .input_builder import build_understanding_input
from .schemas import (
    ProfileUnderstandingDocumentBlock,
    ProfileUnderstandingEntity,
    ProfileUnderstandingEvidence,
    ProfileUnderstandingMissionUnit,
    ProfileUnderstandingQuestion,
    ProfileUnderstandingSessionRequest,
    ProfileUnderstandingSessionResponse,
    ProfileUnderstandingSkillLink,
)


_KNOWN_TOOL_LABELS: Sequence[str] = (
    "Excel",
    "Power BI",
    "Tableau",
    "SQL",
    "Python",
    "R",
    "SAP",
    "Salesforce",
    "HubSpot",
    "Jira",
    "Notion",
    "Figma",
    "Git",
    "Looker Studio",
    "dbt",
    "Metabase",
)

_GENERIC_NOISE_LABELS: Sequence[str] = (
    "communication",
    "marketing",
    "audience",
    "content",
    "content creation",
    "analysis",
    "support",
    "activation",
    "understanding",
    "campaigns",
    "analyse",
)

_AUTONOMY_KEYWORDS: Dict[str, Sequence[str]] = {
    "ownership": ("led", "owned", "managed", "defined", "spearheaded", "built"),
    "autonomous": ("created", "designed", "implemented", "delivered", "developed", "analyzed"),
    "partial": ("supported", "assisted", "contributed", "helped"),
}


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


def _normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _is_noise_label(label: str) -> bool:
    normalized = _normalize_label(label)
    if len(normalized) < 2:
        return True
    if len(normalized) == 1:
        return True
    return normalized in {_normalize_label(item) for item in _GENERIC_NOISE_LABELS}


def _label_present_in_text(label: str, text: str) -> bool:
    normalized_label = _normalize_label(label)
    normalized_text = _normalize_label(text)
    if not normalized_label or not normalized_text:
        return False
    pattern = r"(?<!\w)" + re.escape(normalized_label) + r"(?!\w)"
    return re.search(pattern, normalized_text) is not None


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return _dedupe_strings(str(item or "").strip() for item in value if str(item or "").strip())


def _extract_candidate_labels(source_context: Dict[str, Any]) -> List[str]:
    labels: List[str] = []
    labels.extend(str(item).strip() for item in source_context.get("validated_labels", []) if str(item).strip())
    labels.extend(str(item).strip() for item in source_context.get("tight_candidates", []) if str(item).strip())
    cleaned = []
    for label in _dedupe_strings(labels):
        if _is_noise_label(label):
            continue
        cleaned.append(label)
    return cleaned


def _career_profile_from_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    career_profile = payload.get("career_profile")
    if isinstance(career_profile, dict):
        return dict(career_profile)
    return {}


def _experience_tools_label(experience: Dict[str, Any]) -> List[str]:
    tools = experience.get("tools", []) or []
    labels: List[str] = []
    for tool in tools:
        if isinstance(tool, dict):
            labels.append(str(tool.get("label") or "").strip())
        else:
            labels.append(str(tool).strip())
    return _dedupe_strings(labels)


def _build_entity(
    entity_id: str,
    entity_type: str,
    label: str,
    *,
    confidence: float,
    raw_value: str | None = None,
    metadata: Dict[str, Any] | None = None,
) -> ProfileUnderstandingEntity:
    return ProfileUnderstandingEntity(
        id=entity_id,
        entity_type=entity_type,
        label=label,
        confidence=confidence,
        raw_value=raw_value,
        metadata=metadata or {},
    )


def _build_evidence(
    source_type: str,
    *,
    source_value: str | None = None,
    confidence: float | None = None,
    mapping_status: str | None = None,
    target_path: str | None = None,
) -> ProfileUnderstandingEvidence:
    return ProfileUnderstandingEvidence(
        source_type=source_type,
        source_value=source_value,
        confidence=confidence,
        mapping_status=mapping_status,
        target_path=target_path,
    )


def _tool_label_from_skill_entry(skill: Dict[str, Any]) -> List[str]:
    values = skill.get("tools", []) or []
    return _dedupe_strings(values)


def _joined_text(parts: Sequence[str]) -> str | None:
    text = " | ".join(part for part in parts if part)
    return text or None


def _block_metadata(block_type: str, index: int, item: Dict[str, Any]) -> Dict[str, Any]:
    if block_type == "experience":
        return {
            "experience_ref": f"exp-{index}",
            "company": str(item.get("company") or "").strip(),
            "dates": str(item.get("dates") or "").strip() or None,
        }
    if block_type == "project":
        return {
            "project_ref": f"proj-{index}",
            "organization": str(item.get("organization") or "").strip() or None,
            "technologies": _string_list(item.get("technologies") or []),
        }
    return {key: value for key, value in item.items() if value}


def _extract_quantified_signals(text: str) -> List[str]:
    if not text:
        return []
    pattern = re.compile(r"\b(?:\d+(?:[.,]\d+)?\s?(?:%|k|K|M|€|\$|ans?|mois|jours?)|\d+[.,]?\d*)\b")
    return _dedupe_strings(match.group(0) for match in pattern.finditer(text))


def _infer_autonomy(text: str, fallback: str | None = None) -> str | None:
    if fallback:
        return str(fallback).strip() or None
    lowered = text.lower()
    for level, keywords in _AUTONOMY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return level
    return None


def _find_tools_in_text(text: str, baseline_tools: Sequence[str], source_context: Dict[str, Any]) -> List[str]:
    candidates = [*baseline_tools, *_KNOWN_TOOL_LABELS]
    tools: List[str] = []
    for label in _dedupe_strings(candidates):
        if _is_noise_label(label):
            continue
        if _label_present_in_text(label, text):
            tools.append(label)
    return _dedupe_strings([*baseline_tools, *tools])[:6]


def _find_skills_for_mission(text: str, experience: Dict[str, Any], source_context: Dict[str, Any]) -> List[str]:
    canonical_labels: List[str] = []
    for skill in experience.get("canonical_skills_used", []) or []:
        if not isinstance(skill, dict):
            continue
        label = str(skill.get("label") or "").strip()
        if label and not _is_noise_label(label):
            canonical_labels.append(label)

    matched = [label for label in canonical_labels if _label_present_in_text(label, text)]
    if matched:
        return _dedupe_strings(matched)

    candidate_labels = _extract_candidate_labels(source_context)
    open_labels = [
        label
        for label in candidate_labels
        if label not in _KNOWN_TOOL_LABELS and _label_present_in_text(label, text)
    ]
    if open_labels:
        return _dedupe_strings(open_labels[:2])
    return _dedupe_strings(open_labels[:3])


def _build_document_blocks(career_profile: Dict[str, Any]) -> List[ProfileUnderstandingDocumentBlock]:
    blocks: List[ProfileUnderstandingDocumentBlock] = []

    for index, experience in enumerate(career_profile.get("experiences", []) or []):
        if not isinstance(experience, dict):
            continue
        label = str(experience.get("title") or "Experience").strip()
        company = str(experience.get("company") or "").strip()
        source_text = _joined_text(
            [
                label,
                company,
                " ; ".join(_string_list(experience.get("responsibilities") or [])),
                " ; ".join(_string_list(experience.get("achievements") or [])),
            ]
        )
        blocks.append(
            ProfileUnderstandingDocumentBlock(
                id=f"block-exp-{index}",
                block_type="experience",
                label=label,
                source_text=source_text,
                confidence=0.8,
                metadata=_block_metadata("experience", index, experience),
            )
        )

    for index, project in enumerate(career_profile.get("projects", []) or []):
        if not isinstance(project, dict):
            continue
        label = str(project.get("title") or project.get("description") or "Projet").strip()
        source_text = _joined_text(
            [
                label,
                str(project.get("description") or "").strip(),
                " ; ".join(_string_list(project.get("technologies") or [])),
            ]
        )
        blocks.append(
            ProfileUnderstandingDocumentBlock(
                id=f"block-proj-{index}",
                block_type="project",
                label=label,
                source_text=source_text,
                confidence=0.7,
                metadata=_block_metadata("project", index, project),
            )
        )

    for index, education in enumerate(career_profile.get("education", []) or []):
        if isinstance(education, dict):
            degree = str(education.get("degree") or "").strip()
            field = str(education.get("field") or "").strip()
            institution = str(education.get("institution") or "").strip()
            label = " - ".join(part for part in (degree, field or institution) if part) or "Formation"
            source_text = _joined_text([degree, field, institution])
            metadata = _block_metadata("education", index, education)
        else:
            label = str(education or "").strip() or "Formation"
            source_text = label
            metadata = {"raw_value": label}
        blocks.append(
            ProfileUnderstandingDocumentBlock(
                id=f"block-edu-{index}",
                block_type="education",
                label=label,
                source_text=source_text,
                confidence=0.68,
                metadata=metadata,
            )
        )

    for index, certification in enumerate(career_profile.get("certifications", []) or []):
        label = str(certification or "").strip()
        if not label:
            continue
        blocks.append(
            ProfileUnderstandingDocumentBlock(
                id=f"block-cert-{index}",
                block_type="certification",
                label=label,
                source_text=label,
                confidence=0.72,
                metadata={"certification_ref": f"cert-{index}"},
            )
        )

    return blocks


def _build_entity_classification(
    career_profile: Dict[str, Any],
    source_context: Dict[str, Any],
    document_blocks: Sequence[ProfileUnderstandingDocumentBlock],
) -> Dict[str, List[ProfileUnderstandingEntity]]:
    entities: Dict[str, List[ProfileUnderstandingEntity]] = {
        "experiences": [],
        "projects": [],
        "education": [],
        "certifications": [],
        "skills": [],
        "tools": [],
    }

    for block in document_blocks:
        entity_group = f"{block.block_type}s" if block.block_type != "education" else "education"
        if entity_group in entities:
            entities[entity_group].append(
                _build_entity(
                    block.id.replace("block-", ""),
                    block.block_type,
                    block.label,
                    confidence=block.confidence or 0.6,
                    raw_value=block.source_text,
                    metadata=block.metadata,
                )
            )

    for index, experience in enumerate(career_profile.get("experiences", []) or []):
        if not isinstance(experience, dict):
            continue
        for skill_index, skill in enumerate(experience.get("canonical_skills_used", []) or []):
            if not isinstance(skill, dict):
                continue
            label = str(skill.get("label") or "").strip()
            if not label:
                continue
            entities["skills"].append(
                _build_entity(
                    f"exp-{index}-skill-{skill_index}",
                    "skill",
                    label,
                    confidence=0.75,
                    raw_value=label,
                    metadata={"experience_ref": f"exp-{index}", "uri": skill.get("uri")},
                )
            )
        for tool_index, tool in enumerate(_experience_tools_label(experience)):
            entities["tools"].append(
                _build_entity(
                    f"exp-{index}-tool-{tool_index}",
                    "tool",
                    tool,
                    confidence=0.77,
                    raw_value=tool,
                    metadata={"experience_ref": f"exp-{index}", "source": "experience.tools"},
                )
            )

    for tool_index, label in enumerate(_extract_candidate_labels(source_context)):
        entity_type = "tool" if label in _KNOWN_TOOL_LABELS else "skill"
        bucket = "tools" if entity_type == "tool" else "skills"
        entities[bucket].append(
            _build_entity(
                f"ctx-{entity_type}-{tool_index}",
                entity_type,
                label,
                confidence=0.46,
                raw_value=label,
                metadata={"source": "source_context"},
            )
        )

    for key, values in entities.items():
        deduped: List[ProfileUnderstandingEntity] = []
        seen: set[tuple[str, str]] = set()
        for item in values:
            dedupe_key = (item.entity_type, item.label.lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            deduped.append(item)
        entities[key] = deduped

    return entities


def _mission_lines_for_experience(experience: Dict[str, Any]) -> List[str]:
    return _dedupe_strings(
        [
            *_string_list(experience.get("responsibilities") or []),
            *_string_list(experience.get("achievements") or []),
            *_string_list(experience.get("impact_signals") or []),
        ]
    )


def _build_project_mission_lines(project: Dict[str, Any]) -> List[str]:
    lines = _string_list(project.get("missions") or [])
    description = str(project.get("description") or "").strip()
    if description:
        lines.append(description)
    return _dedupe_strings(lines)


def _build_mission_units(
    career_profile: Dict[str, Any],
    source_context: Dict[str, Any],
    document_blocks: Sequence[ProfileUnderstandingDocumentBlock],
) -> List[ProfileUnderstandingMissionUnit]:
    block_lookup = {block.id: block for block in document_blocks}
    mission_units: List[ProfileUnderstandingMissionUnit] = []

    for index, experience in enumerate(career_profile.get("experiences", []) or []):
        if not isinstance(experience, dict):
            continue
        experience_ref = f"exp-{index}"
        block_ref = f"block-exp-{index}"
        block = block_lookup.get(block_ref)
        baseline_tools = _experience_tools_label(experience)
        lines = _mission_lines_for_experience(experience)
        if not lines and block and block.source_text:
            lines = [block.source_text]
        for mission_index, mission_text in enumerate(lines):
            mission_units.append(
                ProfileUnderstandingMissionUnit(
                    id=f"{experience_ref}-mission-{mission_index}",
                    block_ref=block_ref,
                    experience_ref=experience_ref,
                    mission_text=mission_text,
                    context=str(experience.get("company") or experience.get("title") or "").strip() or None,
                    skill_candidates_open=_find_skills_for_mission(mission_text, experience, source_context),
                    tool_candidates_open=_find_tools_in_text(mission_text, baseline_tools, source_context),
                    quantified_signals=_extract_quantified_signals(mission_text),
                    autonomy_hypothesis=_infer_autonomy(mission_text, str(experience.get("autonomy_level") or "").strip() or None),
                    evidence=[
                        _build_evidence(
                            "experience_mission",
                            source_value=mission_text,
                            confidence=0.72,
                            mapping_status="mission_extracted",
                            target_path=f"career_profile.experiences[{index}]",
                        )
                    ],
                )
            )

    for index, project in enumerate(career_profile.get("projects", []) or []):
        if not isinstance(project, dict):
            continue
        block_ref = f"block-proj-{index}"
        lines = _build_project_mission_lines(project)
        baseline_tools = _string_list(project.get("technologies") or [])
        project_ref = f"proj-{index}"
        for mission_index, mission_text in enumerate(lines):
            mission_units.append(
                ProfileUnderstandingMissionUnit(
                    id=f"{project_ref}-mission-{mission_index}",
                    block_ref=block_ref,
                    experience_ref=None,
                    mission_text=mission_text,
                    context=str(project.get("title") or "Projet").strip() or None,
                    skill_candidates_open=_dedupe_strings(
                        [
                            label
                            for label in _extract_candidate_labels(source_context)
                            if label.lower() in mission_text.lower() and label not in _KNOWN_TOOL_LABELS
                        ]
                    ),
                    tool_candidates_open=_find_tools_in_text(mission_text, baseline_tools, source_context),
                    quantified_signals=_extract_quantified_signals(mission_text),
                    autonomy_hypothesis=_infer_autonomy(mission_text),
                    evidence=[
                        _build_evidence(
                            "project_signal",
                            source_value=mission_text,
                            confidence=0.64,
                            mapping_status="mission_extracted",
                            target_path=f"career_profile.projects[{index}]",
                        )
                    ],
                )
            )

    return mission_units


def _build_skill_links_from_missions(
    career_profile: Dict[str, Any],
    source_context: Dict[str, Any],
    mission_units: Sequence[ProfileUnderstandingMissionUnit],
) -> List[ProfileUnderstandingSkillLink]:
    skill_links: List[ProfileUnderstandingSkillLink] = []

    for mission in mission_units:
        if not mission.experience_ref:
            continue
        experience_index = int(mission.experience_ref.split("-")[-1])
        experience = (career_profile.get("experiences", []) or [])[experience_index]
        canonical_entries = experience.get("canonical_skills_used", []) or []
        canonical_by_label = {
            str(item.get("label") or "").strip().lower(): item
            for item in canonical_entries
            if isinstance(item, dict) and str(item.get("label") or "").strip()
        }
        skill_labels = mission.skill_candidates_open
        if not skill_labels:
            continue
        for skill_label in skill_labels:
            canonical = canonical_by_label.get(skill_label.lower())
            link_tools = mission.tool_candidates_open or _experience_tools_label(experience)
            if not canonical and not link_tools:
                continue
            evidence = [
                _build_evidence(
                    "mission_unit",
                    source_value=mission.mission_text,
                    confidence=0.74 if canonical else 0.48,
                    mapping_status="mapped" if canonical else "open",
                    target_path=f"career_profile.experiences[{experience_index}].skill_links",
                ),
                *mission.evidence,
            ]
            deduped_evidence: List[ProfileUnderstandingEvidence] = []
            seen_evidence: set[tuple[str, str | None, str | None]] = set()
            for item in evidence:
                key = (item.source_type, item.source_value, item.target_path)
                if key in seen_evidence:
                    continue
                seen_evidence.add(key)
                deduped_evidence.append(item)
            skill_links.append(
                ProfileUnderstandingSkillLink(
                    experience_ref=mission.experience_ref,
                    skill={
                        "label": canonical.get("label") if canonical else skill_label,
                        "uri": canonical.get("uri") if canonical else None,
                        "source": "mission_unit" if canonical else "open_signal",
                    },
                    tools=[{"label": tool, "source": "mission_unit"} for tool in link_tools[:5]],
                    context=mission.mission_text,
                    autonomy_level=mission.autonomy_hypothesis,
                    evidence=deduped_evidence,
                )
            )

    deduped_links: List[ProfileUnderstandingSkillLink] = []
    seen_links: set[tuple[str | None, str, str | None]] = set()
    for link in skill_links:
        link_key = (
            link.experience_ref,
            link.skill.label.lower(),
            (link.context or "").lower()[:96] or None,
        )
        if link_key in seen_links:
            continue
        seen_links.add(link_key)
        deduped_links.append(link)
    return deduped_links


def _build_open_signal(
    mission_units: Sequence[ProfileUnderstandingMissionUnit],
    source_context: Dict[str, Any],
) -> Dict[str, Any]:
    open_skills: List[str] = []
    open_tools: List[str] = []
    rejected: List[str] = []

    for mission in mission_units:
        open_skills.extend(mission.skill_candidates_open)
        open_tools.extend(mission.tool_candidates_open)

    for token in source_context.get("rejected_tokens", []) or []:
        if isinstance(token, dict):
            label = str(token.get("label") or token.get("token") or "").strip()
            reason = str(token.get("reason") or "rejected_by_parser").strip()
        else:
            label = str(token or "").strip()
            reason = "rejected_by_parser"
        if label:
            rejected.append(f"{label}:{reason}")

    return {
        "skills": [label for label in _dedupe_strings(open_skills) if label not in _KNOWN_TOOL_LABELS],
        "tools": [label for label in _dedupe_strings(open_tools) if label in _KNOWN_TOOL_LABELS or label.lower() not in {item.lower() for item in open_skills}],
        "validated_labels": _extract_candidate_labels(source_context),
        "rejected_or_unknown": rejected,
    }


def _build_canonical_signal(
    entity_classification: Dict[str, List[ProfileUnderstandingEntity]],
    skill_links: Sequence[ProfileUnderstandingSkillLink],
) -> Dict[str, Any]:
    return {
        "mapped_skills": [entity.label for entity in entity_classification.get("skills", []) if entity.metadata.get("uri")],
        "mapped_tools": [entity.label for entity in entity_classification.get("tools", []) if entity.label in _KNOWN_TOOL_LABELS],
        "skill_link_count": len(skill_links),
        "experience_count": len(entity_classification.get("experiences", [])),
    }


def _build_understanding_status(
    document_blocks: Sequence[ProfileUnderstandingDocumentBlock],
    mission_units: Sequence[ProfileUnderstandingMissionUnit],
    source_context: Dict[str, Any],
    provider: str,
) -> Dict[str, Any]:
    block_statuses: List[Dict[str, Any]] = []
    mission_map: Dict[str, int] = {}
    for mission in mission_units:
        mission_map[mission.block_ref] = mission_map.get(mission.block_ref, 0) + 1

    for block in document_blocks:
        mission_count = mission_map.get(block.id, 0)
        if block.block_type in {"education", "certification"}:
            status = "understood" if block.source_text else "needs_confirmation"
        elif mission_count > 0:
            status = "understood"
        else:
            status = "partially_understood"
        block_statuses.append(
            {
                "block_id": block.id,
                "block_type": block.block_type,
                "status": status,
                "mission_count": mission_count,
                "confidence": block.confidence,
            }
        )

    return {
        "provider_mode": provider,
        "overall_status": "understood" if mission_units else "needs_confirmation",
        "accepted_signal_count": len(source_context.get("validated_labels", []) or []),
        "rejected_signal_count": len(source_context.get("rejected_tokens", []) or []),
        "block_statuses": block_statuses,
    }


def _build_evidence_map(
    skill_links: Sequence[ProfileUnderstandingSkillLink],
    mission_units: Sequence[ProfileUnderstandingMissionUnit],
    source_context: Dict[str, Any],
) -> Dict[str, List[ProfileUnderstandingEvidence]]:
    evidence_map: Dict[str, List[ProfileUnderstandingEvidence]] = {
        "career_profile.skill_links": [],
        "career_profile.mission_units": [],
        "source_context.validated_labels": [],
        "source_context.rejected_tokens": [],
    }

    for link in skill_links:
        evidence_map["career_profile.skill_links"].extend(link.evidence)

    for mission in mission_units:
        evidence_map["career_profile.mission_units"].extend(mission.evidence)

    for label in source_context.get("validated_labels", []) or []:
        clean = str(label or "").strip()
        if clean:
            evidence_map["source_context.validated_labels"].append(
                _build_evidence(
                    "validated_label",
                    source_value=clean,
                    confidence=0.78,
                    mapping_status="validated",
                )
            )

    for token in source_context.get("rejected_tokens", []) or []:
        if isinstance(token, dict):
            value = str(token.get("label") or token.get("token") or "").strip()
        else:
            value = str(token or "").strip()
        if value:
            evidence_map["source_context.rejected_tokens"].append(
                _build_evidence(
                    "rejected_token",
                    source_value=value,
                    confidence=0.22,
                    mapping_status="rejected",
                )
            )

    return evidence_map


def _build_confidence_map(
    document_blocks: Sequence[ProfileUnderstandingDocumentBlock],
    mission_units: Sequence[ProfileUnderstandingMissionUnit],
    entity_classification: Dict[str, List[ProfileUnderstandingEntity]],
    skill_links: Sequence[ProfileUnderstandingSkillLink],
    source_context: Dict[str, Any],
) -> Dict[str, float]:
    experience_count = len(entity_classification.get("experiences", []))
    skill_count = len(entity_classification.get("skills", []))
    validated_count = len(source_context.get("validated_labels", []) or [])
    return {
        "document_blocks": round(min(0.92, 0.44 + (len(document_blocks) * 0.06)), 3),
        "mission_units": round(min(0.9, 0.36 + (len(mission_units) * 0.05)), 3),
        "entity_classification": round(min(0.9, 0.45 + (experience_count * 0.08) + (skill_count * 0.04)), 3),
        "skill_links": round(min(0.88, 0.38 + (len(skill_links) * 0.05)), 3),
        "source_context.validated_labels": round(min(0.95, 0.4 + (validated_count * 0.1)), 3),
    }


def _default_stub_questions(
    career_profile: Dict[str, Any],
    mission_units: Sequence[ProfileUnderstandingMissionUnit],
    source_context: Dict[str, Any],
) -> List[ProfileUnderstandingQuestion]:
    questions: List[ProfileUnderstandingQuestion] = []
    experiences = career_profile.get("experiences", []) or []
    candidate_labels = _extract_candidate_labels(source_context)

    for index, item in enumerate(experiences[:4]):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "cette experience").strip()
        company = str(item.get("company") or "").strip()
        anchor = f"{title} chez {company}".strip() if company else title
        tools = _experience_tools_label(item)
        exp_missions = [mission for mission in mission_units if mission.experience_ref == f"exp-{index}"]
        if not item.get("autonomy_level"):
            suggested_autonomy = next((mission.autonomy_hypothesis for mission in exp_missions if mission.autonomy_hypothesis), "autonomous")
            questions.append(
                ProfileUnderstandingQuestion(
                    id=f"experience-{index}-autonomy",
                    category="experience_autonomy",
                    prompt=f"Sur {anchor}, a quel niveau d'autonomie operiez-vous reellement ?",
                    field_path=f"career_profile.experiences[{index}].autonomy_level",
                    suggested_answer=suggested_autonomy,
                    confidence=0.47,
                    rationale="Les missions ont ete comprises, mais l'autonomie reste a confirmer.",
                )
            )
        if not tools:
            mission_tools = _dedupe_strings(tool for mission in exp_missions for tool in mission.tool_candidates_open)
            suggested = ", ".join((mission_tools or candidate_labels)[:3]) if (mission_tools or candidate_labels) else None
            questions.append(
                ProfileUnderstandingQuestion(
                    id=f"experience-{index}-tools",
                    category="experience_tools",
                    prompt=f"Quels outils utilisiez-vous vraiment sur {anchor} ?",
                    field_path=f"career_profile.experiences[{index}].tools",
                    suggested_answer=suggested,
                    confidence=0.52,
                    rationale="Le systeme a trouve des outils probables mission par mission, mais ils restent a confirmer.",
                )
            )

    if not career_profile.get("education"):
        questions.append(
            ProfileUnderstandingQuestion(
                id="education-primary",
                category="education",
                prompt="Quelle formation principale doit apparaitre dans votre profil final ?",
                field_path="career_profile.education",
                confidence=0.35,
                rationale="Aucune formation exploitable n'a ete structuree automatiquement.",
            )
        )

    if not career_profile.get("certifications"):
        questions.append(
            ProfileUnderstandingQuestion(
                id="certifications-primary",
                category="certifications",
                prompt="Avez-vous des certifications a rattacher au profil ?",
                field_path="career_profile.certifications",
                confidence=0.32,
                rationale="Les certifications ne sont pas encore renseignees dans le profil courant.",
            )
        )

    if not experiences:
        questions.append(
            ProfileUnderstandingQuestion(
                id="experience-primary",
                category="experience_scope",
                prompt="Quelle experience ou mission doit absolument apparaitre dans votre profil ?",
                field_path="career_profile.experiences",
                confidence=0.28,
                rationale="Aucune experience structuree n'est disponible dans le profil courant.",
            )
        )

    return questions[:8]


def _merge_skill_links_into_experiences(
    experiences: List[Dict[str, Any]],
    skill_links: Sequence[ProfileUnderstandingSkillLink],
) -> None:
    for index, experience in enumerate(experiences):
        if not isinstance(experience, dict):
            continue
        experience_ref = f"exp-{index}"
        bound_links = [link.model_dump() for link in skill_links if link.experience_ref == experience_ref]
        if not bound_links:
            continue
        experience["skill_links"] = bound_links
        existing_skills = experience.get("canonical_skills_used", []) or []
        existing_skill_labels = {
            str(item.get("label") or "").strip().lower()
            for item in existing_skills
            if isinstance(item, dict) and str(item.get("label") or "").strip()
        }
        for link in bound_links:
            skill = link.get("skill") or {}
            label = str(skill.get("label") or "").strip()
            if label and label.lower() not in existing_skill_labels:
                existing_skills.append({"label": label, "uri": skill.get("uri")})
                existing_skill_labels.add(label.lower())
        experience["canonical_skills_used"] = existing_skills

        existing_tools = _experience_tools_label(experience)
        mission_tools = [
            str(tool.get("label") or "").strip()
            for link in bound_links
            for tool in (link.get("tools") or [])
            if isinstance(tool, dict)
        ]
        experience["tools"] = _dedupe_strings([*existing_tools, *mission_tools])
        if not experience.get("autonomy_level"):
            autonomy = next(
                (
                    str(link.get("autonomy_level") or "").strip()
                    for link in bound_links
                    if str(link.get("autonomy_level") or "").strip()
                ),
                "",
            )
            if autonomy:
                experience["autonomy_level"] = autonomy


def _build_stub_patch(
    career_profile: Dict[str, Any],
    source_context: Dict[str, Any],
    skill_links: Sequence[ProfileUnderstandingSkillLink],
    open_signal: Dict[str, Any],
) -> Dict[str, Any]:
    proposed = dict(career_profile)
    pending = proposed.get("pending_skill_candidates", []) or []
    proposed["pending_skill_candidates"] = _dedupe_strings(pending)
    proposed.setdefault("education", [])
    proposed.setdefault("certifications", [])
    proposed.setdefault("experiences", [])
    proposed.setdefault("projects", [])
    experiences = proposed.get("experiences", []) or []
    _merge_skill_links_into_experiences(experiences, skill_links)
    return {"career_profile": proposed}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def get_profile_understanding_resources() -> Dict[str, Any]:
    canonical_store = get_canonical_store()
    certification_registry_path = _repo_root() / "apps" / "api" / "src" / "compass" / "registry" / "certifications_registry.json"
    try:
        certifications_registry = json.loads(certification_registry_path.read_text(encoding="utf-8"))
    except Exception:
        certifications_registry = {"certifications": []}

    canonical_skills: List[Dict[str, Any]] = []
    for skill in list(canonical_store.id_to_skill.values())[:40]:
        canonical_skills.append(
            {
                "canonical_skill_id": skill.get("canonical_skill_id"),
                "label": skill.get("label"),
                "skill_type": skill.get("skill_type"),
                "concept_type": skill.get("concept_type"),
                "tools": list(skill.get("tools") or [])[:5],
                "cluster_name": skill.get("cluster_name"),
            }
        )

    certifications = certifications_registry.get("certifications") or []
    certification_items: List[Dict[str, Any]] = []
    cert_iterable = certifications.values() if isinstance(certifications, dict) else certifications
    for item in list(cert_iterable)[:40]:
        if not isinstance(item, dict):
            continue
        certification_items.append(
            {
                "name": item.get("name") or item.get("canonical"),
                "issuer": item.get("issuer"),
                "aliases": list(item.get("aliases") or [])[:5],
                "cluster_hints": list(item.get("cluster_hints") or ([item.get("cluster_hint")] if item.get("cluster_hint") else []))[:5],
            }
        )

    return {
        "agent_runtime": {
            "external_runtime_expected": True,
            "provider_mode": os.getenv("ELEVIA_PROFILE_UNDERSTANDING_PROVIDER", "stub").strip().lower() or "stub",
            "resource_contract_version": "v3",
        },
        "resources": {
            "canonical_skills": canonical_skills,
            "known_tools": [{"label": label} for label in _KNOWN_TOOL_LABELS],
            "certifications": certification_items,
        },
        "conventions": {
            "entity_types": [
                "experience",
                "project",
                "education",
                "certification",
                "skill",
                "tool",
                "language",
                "role_signal",
            ],
            "block_types": ["experience", "project", "education", "certification", "other"],
            "understanding_statuses": [
                "understood",
                "partially_understood",
                "needs_confirmation",
                "rejected_by_deterministic",
                "unknown_to_canonical",
            ],
            "skill_link_shape": {
                "skill": "canonical or open skill reference",
                "tools": "tools used to exercise the skill",
                "context": "business or mission context",
                "autonomy_level": "execution|partial|autonomous|ownership",
            },
            "truth_priority": [
                "user_answer",
                "validated_parser_output",
                "evidence_backed_agent_inference",
                "weak_or_ambiguous_parser_signal",
            ],
        },
        "sources": {
            "canonical_store_path": str(_repo_root() / "audit" / "canonical_skills_core.json"),
            "certification_registry_path": str(certification_registry_path),
        },
    }


class ProfileUnderstandingService:
    def __init__(self) -> None:
        self.provider = os.getenv("ELEVIA_PROFILE_UNDERSTANDING_PROVIDER", "stub").strip().lower() or "stub"
        self.remote_url = os.getenv("ELEVIA_PROFILE_UNDERSTANDING_URL", "").strip()
        self.allow_stub_fallback = _env_flag("ELEVIA_PROFILE_UNDERSTANDING_ALLOW_STUB_FALLBACK", True)
        self.remote_timeout_seconds = float(
            os.getenv("ELEVIA_PROFILE_UNDERSTANDING_HTTP_TIMEOUT_SECONDS", "20").strip() or "20"
        )

    def create_session(
        self,
        payload: ProfileUnderstandingSessionRequest,
    ) -> ProfileUnderstandingSessionResponse:
        if self.provider == "http" and self.remote_url:
            try:
                return self._create_remote_session(payload)
            except Exception as exc:
                if not self.allow_stub_fallback:
                    raise RuntimeError("remote_provider_unavailable") from exc
                return self._create_stub_session(
                    payload,
                    fallback_reason="remote_provider_unavailable",
                    requested_provider="http",
                )
        return self._create_stub_session(payload, requested_provider=self.provider)

    def _create_remote_session(
        self,
        payload: ProfileUnderstandingSessionRequest,
    ) -> ProfileUnderstandingSessionResponse:
        request = urllib.request.Request(
            self.remote_url,
            data=json.dumps(payload.model_dump()).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.remote_timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"remote provider error: {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("remote provider unavailable") from exc

        if not isinstance(body, dict):
            raise RuntimeError("remote provider returned invalid payload")
        return ProfileUnderstandingSessionResponse(**body)

    def _create_stub_session(
        self,
        payload: ProfileUnderstandingSessionRequest,
        *,
        fallback_reason: str | None = None,
        requested_provider: str | None = None,
    ) -> ProfileUnderstandingSessionResponse:
        career_profile = _career_profile_from_request(payload.profile)
        understanding_input = build_understanding_input(
            cv_text=str(payload.source_context.get("cv_text") or ""),
            parse_payload={
                "profile": payload.profile,
                "filename": payload.source_context.get("filename"),
                "text_quality": payload.source_context.get("text_quality"),
                "extracted_text_length": payload.source_context.get("extracted_text_length"),
                "profile_fingerprint": payload.source_context.get("profile_fingerprint"),
                "language_hint": payload.source_context.get("language_hint"),
                "profile_summary": payload.source_context.get("profile_summary"),
                "profile_summary_skills": payload.source_context.get("profile_summary_skills"),
                "profile_intelligence": payload.source_context.get("profile_intelligence"),
                "structured_profile_version": payload.source_context.get("structured_profile_version"),
                "document_blocks_seed": payload.source_context.get("document_blocks_seed"),
                "structured_signal_units": payload.source_context.get("structured_signal_units"),
                "top_signal_units": payload.source_context.get("top_signal_units"),
                "secondary_signal_units": payload.source_context.get("secondary_signal_units"),
                "skill_proximity_links": payload.source_context.get("skill_proximity_links"),
                "canonical_skills": payload.source_context.get("canonical_skills"),
                "certifications": payload.source_context.get("certifications"),
                "validated_labels": payload.source_context.get("validated_labels") or [],
                "tight_candidates": payload.source_context.get("tight_candidates") or [],
                "rejected_tokens": payload.source_context.get("rejected_tokens") or [],
            },
        )
        document_blocks = _build_document_blocks(career_profile)
        mission_units = _build_mission_units(career_profile, payload.source_context, document_blocks)
        entity_classification = _build_entity_classification(career_profile, payload.source_context, document_blocks)
        skill_links = _build_skill_links_from_missions(career_profile, payload.source_context, mission_units)
        open_signal = _build_open_signal(mission_units, payload.source_context)
        canonical_signal = _build_canonical_signal(entity_classification, skill_links)
        understanding_status = _build_understanding_status(document_blocks, mission_units, payload.source_context, "stub")
        questions = _default_stub_questions(career_profile, mission_units, payload.source_context)
        evidence_map = _build_evidence_map(skill_links, mission_units, payload.source_context)
        confidence_map = _build_confidence_map(
            document_blocks,
            mission_units,
            entity_classification,
            skill_links,
            payload.source_context,
        )
        patch = _build_stub_patch(career_profile, payload.source_context, skill_links, open_signal)

        return ProfileUnderstandingSessionResponse(
            session_id=f"pus_{uuid.uuid4().hex[:12]}",
            status="ready",
            provider="stub",
            trace_summary={
                "mode": "repo_stub_adapter",
                "external_runtime_expected": True,
                "requested_provider": requested_provider or self.provider,
                "fallback_reason": fallback_reason,
                "block_count": len(document_blocks),
                "mission_count": len(mission_units),
                "question_count": len(questions),
                "experience_count": len(career_profile.get("experiences", []) or []),
                "entity_count": sum(len(items) for items in entity_classification.values()),
                "skill_link_count": len(skill_links),
            },
            understanding_input=understanding_input,
            document_blocks=document_blocks,
            mission_units=mission_units,
            open_signal=open_signal,
            canonical_signal=canonical_signal,
            understanding_status=understanding_status,
            entity_classification=entity_classification,
            proposed_profile_patch=patch,
            skill_links=skill_links,
            evidence_map=evidence_map,
            confidence_map=confidence_map,
            questions=questions,
        )
