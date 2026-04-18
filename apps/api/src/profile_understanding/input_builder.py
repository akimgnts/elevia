from __future__ import annotations

from typing import Any, Dict, List, Sequence

from .schemas import ProfileUnderstandingInput


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


def _dedupe_strings(values: Sequence[Any]) -> List[str]:
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


def _coerce_rejected_tokens(values: Sequence[Any]) -> List[Dict[str, Any]]:
    rejected: List[Dict[str, Any]] = []
    for item in values or []:
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("token") or "").strip()
            if not label:
                continue
            rejected.append(
                {
                    "label": label,
                    "reason": str(item.get("reason") or "rejected_by_parser").strip() or "rejected_by_parser",
                    "raw": item,
                }
            )
            continue
        label = str(item or "").strip()
        if label:
            rejected.append({"label": label, "reason": "rejected_by_parser", "raw": item})
    return rejected


def build_understanding_input(*, cv_text: str, parse_payload: Dict[str, Any]) -> Dict[str, Any]:
    validated_labels = _dedupe_strings(parse_payload.get("validated_labels") or [])
    tight_candidates = _dedupe_strings(parse_payload.get("tight_candidates") or [])
    rejected_tokens = _coerce_rejected_tokens(parse_payload.get("rejected_tokens") or [])

    ambiguous_candidates = [
        label for label in tight_candidates if label.lower() not in {item.lower() for item in validated_labels}
    ]
    unmapped_but_promising = [
        item for item in rejected_tokens if "unmapped" in str(item.get("reason") or "").lower()
    ]
    strict_rejected = [item for item in rejected_tokens if item not in unmapped_but_promising]

    profile = parse_payload.get("profile") or {}
    career_profile_seed = profile.get("career_profile") if isinstance(profile, dict) else {}

    understanding_input = ProfileUnderstandingInput(
        document_context={
            "cv_text": cv_text,
            "source_filename": parse_payload.get("filename"),
            "text_quality": parse_payload.get("text_quality") or "unknown",
            "extracted_text_length": parse_payload.get("extracted_text_length") or len(cv_text or ""),
            "profile_fingerprint": parse_payload.get("profile_fingerprint"),
            "language_hint": parse_payload.get("language_hint"),
        },
        deterministic_profile_seed={
            "career_profile_seed": career_profile_seed or {},
            "profile_summary": parse_payload.get("profile_summary")
            or {"skills": parse_payload.get("profile_summary_skills") or []},
            "profile_intelligence": parse_payload.get("profile_intelligence") or {},
            "structured_profile_version": parse_payload.get("structured_profile_version") or "profile_structured_v1",
        },
        document_structure_seed={
            "document_blocks_seed": parse_payload.get("document_blocks_seed") or [],
            "structured_signal_units": parse_payload.get("structured_signal_units") or [],
            "top_signal_units": parse_payload.get("top_signal_units") or [],
            "secondary_signal_units": parse_payload.get("secondary_signal_units") or [],
            "skill_proximity_links": parse_payload.get("skill_proximity_links") or [],
        },
        reference_context={
            "canonical_skills": parse_payload.get("canonical_skills") or [],
            "known_tools": [{"label": label} for label in _KNOWN_TOOL_LABELS],
            "certifications": parse_payload.get("certifications") or [],
            "allowed_block_types": ["experience", "project", "education", "certification", "other"],
            "allowed_understanding_statuses": [
                "understood",
                "partially_understood",
                "needs_confirmation",
                "rejected_by_deterministic",
                "unknown_to_canonical",
            ],
        },
        signal_buckets={
            "accepted_signal": {"validated_labels": validated_labels},
            "ambiguous_signal": {"tight_candidates": ambiguous_candidates},
            "rejected_signal": strict_rejected,
            "unmapped_but_promising_signal": unmapped_but_promising,
        },
        agent_constraints={
            "no_invention": True,
            "require_contextual_evidence_for_rejected_signal": True,
            "auto_fill_requires_confidence_threshold": 0.7,
            "questions_only_for_unresolved_high_value_gaps": True,
        },
    )
    return understanding_input.model_dump()
