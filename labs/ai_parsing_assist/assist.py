from __future__ import annotations

import json
import os
from typing import Any, Mapping, Sequence

from api.utils.env import get_llm_api_key
from compass.canonical.canonical_store import normalize_canonical_key
from documents.llm_client import call_llm_json

from .gating import gate_ai_enrichment

_ALLOWED_DOMAINS = [
    "data",
    "finance",
    "sales",
    "hr",
    "marketing",
    "supply_chain",
    "project",
    "software",
    "legal",
    "general",
]
_OBVIOUS_TOOLS = {
    "sql",
    "python",
    "power bi",
    "sap",
    "salesforce",
    "excel",
    "tms",
}
_WEAK_ACTIONS = {"monitoring", "management", "maintenance", "operations", "development", "coordination"}
_SEGMENT_WORD_MIN = 4
_SEGMENT_WORD_MAX = 24
_MAX_TRIGGERED_SEGMENTS_PER_PROFILE = 2


def ai_parsing_assist_enabled() -> bool:
    raw = os.getenv("ELEVIA_ENABLE_AI_PARSING_ASSIST", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _normalize(value: Any) -> str:
    return normalize_canonical_key(str(value or ""))


def _should_skip_candidate(candidate: Mapping[str, Any]) -> tuple[bool, str]:
    raw_text = str(candidate.get("raw_text") or "")
    source_section = str(candidate.get("source_section") or "")
    word_count = len(raw_text.split())
    object_quality = float(candidate.get("object_quality_score") or 0.0)
    domain = _normalize(candidate.get("domain"))
    action = _normalize(candidate.get("action"))
    object_text = _normalize(candidate.get("object"))
    tools = [_normalize(tool) for tool in list(candidate.get("tools") or [])]

    if candidate.get("segment_skip_reason"):
        return True, str(candidate.get("segment_skip_reason"))
    if source_section == "education":
        return True, "education_segment"
    if word_count < _SEGMENT_WORD_MIN or word_count > _SEGMENT_WORD_MAX:
        return True, "segment_length"
    if any(tool in _OBVIOUS_TOOLS for tool in tools) and object_quality >= 0.82 and domain != "unknown":
        return True, "obvious_tool_segment"
    if action and object_text and domain != "unknown" and object_quality >= 0.84 and len(object_text.split()) <= 4:
        return True, "high_confidence_structured_unit"
    if source_section == "skills":
        return True, "skills_section"
    return False, "candidate"


def _should_trigger_candidate(candidate: Mapping[str, Any]) -> tuple[bool, str]:
    object_quality = float(candidate.get("object_quality_score") or 0.0)
    domain = _normalize(candidate.get("domain"))
    action = _normalize(candidate.get("action"))
    object_text = _normalize(candidate.get("object"))
    actions = list(candidate.get("actions") or [])

    if domain == "unknown":
        return True, "unknown_domain"
    if object_quality < 0.82:
        return True, "low_object_quality"
    if len(object_text.split()) > 4:
        return True, "long_narrative_object"
    if action in _WEAK_ACTIONS:
        return True, "weak_action"
    if len(actions) > 1:
        return True, "multiple_actions"
    return False, "strong_enough"


def _trigger_priority(candidate: Mapping[str, Any], trigger_reason: str) -> tuple[float, float, int]:
    object_quality = float(candidate.get("object_quality_score") or 0.0)
    object_len = len(_normalize(candidate.get("object")).split())
    weak_reason_bonus = {
        "unknown_domain": 0.7,
        "long_narrative_object": 0.6,
        "low_object_quality": 0.5,
        "multiple_actions": 0.35,
        "weak_action": 0.25,
    }.get(trigger_reason, 0.0)
    return (
        -(weak_reason_bonus + (1.0 - object_quality)),
        -object_len,
        int(candidate.get("segment_index") or 0),
    )


def _build_prompt_input(
    *,
    candidate: Mapping[str, Any],
    previous_segment: str,
    next_segment: str,
) -> dict[str, Any]:
    return {
        "segment_text": str(candidate.get("raw_text") or ""),
        "neighbor_context": [item for item in [previous_segment, next_segment] if item][:2],
        "deterministic_hints": {
            "existing_action": candidate.get("action") or "",
            "existing_object": candidate.get("object") or "",
            "existing_domain": candidate.get("domain") or "",
            "detected_tools": list(candidate.get("tools") or [])[:5],
        },
        "allowed_domains": list(_ALLOWED_DOMAINS),
    }


def _build_prompts(prompt_input: Mapping[str, Any]) -> tuple[str, str]:
    system_prompt = (
        "You are a strict CV parsing assist. "
        "Use only the provided segment and local context. "
        "Return JSON only with keys: should_enrich, action, object, domain, tools, semantic_label, confidence, evidence_span, reasoning. "
        "Do not predict roles. Do not map to canonical skills. Do not invent tools or domains outside the allowed list."
    )
    user_prompt = (
        "Task:\n"
        "1. Decide if the segment should be enriched.\n"
        "2. If yes, extract one bounded business-task interpretation.\n"
        "3. Keep action normalized and domain inside allowed_domains.\n"
        "4. Keep confidence conservative.\n"
        "5. Use only evidence present in the segment or neighbor_context.\n\n"
        f"Input JSON:\n{json.dumps(prompt_input, ensure_ascii=False)}"
    )
    return system_prompt, user_prompt


def run_ai_parsing_assist(
    *,
    candidate_units: Sequence[Mapping[str, Any]],
    segments: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    enabled = ai_parsing_assist_enabled()
    if not enabled:
        return {
            "enabled": False,
            "triggered_segment_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "abstention_count": 0,
            "accepted_enrichments": [],
            "rejected_enrichments": [],
            "abstentions": [],
            "segment_results": [],
        }

    if not get_llm_api_key():
        return {
            "enabled": True,
            "triggered_segment_count": 0,
            "accepted_count": 0,
            "rejected_count": 0,
            "abstention_count": 0,
            "accepted_enrichments": [],
            "rejected_enrichments": [],
            "abstentions": [],
            "segment_results": [],
            "gate_reason": "llm_unavailable",
        }

    accepted_enrichments: list[dict[str, Any]] = []
    rejected_enrichments: list[dict[str, Any]] = []
    abstentions: list[dict[str, Any]] = []
    segment_results: list[dict[str, Any]] = []

    triggered_candidates: list[tuple[int, Mapping[str, Any], str]] = []
    for idx, candidate in enumerate(candidate_units):
        skip, skip_reason = _should_skip_candidate(candidate)
        if skip:
            continue
        trigger, trigger_reason = _should_trigger_candidate(candidate)
        if not trigger:
            continue
        triggered_candidates.append((idx, candidate, trigger_reason))

    triggered_candidates = sorted(
        triggered_candidates,
        key=lambda item: _trigger_priority(item[1], item[2]),
    )[:_MAX_TRIGGERED_SEGMENTS_PER_PROFILE]

    for idx, candidate, trigger_reason in triggered_candidates:
        previous_segment = str(segments[idx - 1].get("raw_text") or "") if idx > 0 and idx - 1 < len(segments) else ""
        next_segment = str(segments[idx + 1].get("raw_text") or "") if idx + 1 < len(segments) else ""
        prompt_input = _build_prompt_input(
            candidate=candidate,
            previous_segment=previous_segment,
            next_segment=next_segment,
        )
        system_prompt, user_prompt = _build_prompts(prompt_input)

        try:
            raw_response, _, _, _ = call_llm_json(system_prompt=system_prompt, user_prompt=user_prompt)
            accepted, gate_reason, parsed = gate_ai_enrichment(
                enrichment=raw_response,
                segment_text=str(candidate.get("raw_text") or ""),
                deterministic_hints=prompt_input["deterministic_hints"],
                allowed_tool_labels=prompt_input["deterministic_hints"]["detected_tools"],
            )
            row = {
                "segment_index": idx,
                "segment_text": candidate.get("raw_text"),
                "trigger_reason": trigger_reason,
                "raw_proposal": raw_response,
                "parsed_proposal": parsed,
                "accepted": accepted,
                "gate_reason": gate_reason,
            }
            segment_results.append(row)
            if accepted:
                accepted_row = dict(parsed)
                accepted_row.update({
                    "segment_index": idx,
                    "segment_text": candidate.get("raw_text"),
                    "trigger_reason": trigger_reason,
                })
                accepted_enrichments.append(accepted_row)
            elif gate_reason == "abstain":
                abstentions.append(row)
            else:
                rejected_enrichments.append(row)
        except Exception as exc:
            row = {
                "segment_index": idx,
                "segment_text": candidate.get("raw_text"),
                "trigger_reason": trigger_reason,
                "raw_proposal": None,
                "parsed_proposal": None,
                "accepted": False,
                "gate_reason": f"llm_error:{str(exc)}",
            }
            segment_results.append(row)
            rejected_enrichments.append(row)

    return {
        "enabled": True,
        "triggered_segment_count": len(segment_results),
        "accepted_count": len(accepted_enrichments),
        "rejected_count": len(rejected_enrichments),
        "abstention_count": len(abstentions),
        "accepted_enrichments": accepted_enrichments,
        "rejected_enrichments": rejected_enrichments,
        "abstentions": abstentions,
        "segment_results": segment_results,
    }
