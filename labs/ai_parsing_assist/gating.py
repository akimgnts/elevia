from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from compass.canonical.canonical_store import normalize_canonical_key
from compass.extraction.object_quality_filter import evaluate_object_quality, is_generic_object

_THIS = Path(__file__).resolve()
_VERB_LEXICON_PATH = _THIS.parents[2] / "apps" / "api" / "src" / "compass" / "extraction" / "verb_lexicon_fr_en.json"
_ALLOWED_DOMAINS = {
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
    "operations",
    "business",
    "communication",
    "it",
}
_CONFIDENCE_THRESHOLD = 0.75
_BANNED_ABSTRACTIONS = {
    "machine learning",
    "data science",
    "advanced analytics",
}
_DATA_ANCHORS = {
    "sql",
    "power bi",
    "python",
    "dashboard",
    "dashboards",
    "business intelligence",
    "etl",
    "data",
    "donnees",
    "données",
}
_GENERIC_OBJECTS = {
    "communication",
    "organisation",
    "project management",
    "gestion de projet",
    "coordination",
    "analyse",
    "analysis",
    "gestion",
    "suivi",
    "reporting",
}


@lru_cache(maxsize=1)
def allowed_actions() -> set[str]:
    try:
        payload = json.loads(_VERB_LEXICON_PATH.read_text(encoding="utf-8"))
    except Exception:
        return set()
    return {normalize_canonical_key(value) for value in payload.values() if value}


def normalize_text(value: Any) -> str:
    return normalize_canonical_key(str(value or ""))


def parse_ai_enrichment(raw: Mapping[str, Any]) -> dict[str, Any]:
    tools = []
    for item in list(raw.get("tools") or []):
        text = str(item or "").strip()
        if text and text not in tools:
            tools.append(text)
    return {
        "should_enrich": bool(raw.get("should_enrich")),
        "action": normalize_text(raw.get("action")),
        "object": str(raw.get("object") or "").strip(),
        "domain": normalize_text(raw.get("domain")),
        "tools": tools[:5],
        "semantic_label": str(raw.get("semantic_label") or "").strip(),
        "confidence": float(raw.get("confidence") or 0.0),
        "evidence_span": str(raw.get("evidence_span") or "").strip(),
        "reasoning": str(raw.get("reasoning") or "").strip(),
    }


def gate_ai_enrichment(
    *,
    enrichment: Mapping[str, Any],
    segment_text: str,
    deterministic_hints: Mapping[str, Any],
    allowed_tool_labels: Sequence[str],
) -> tuple[bool, str, dict[str, Any]]:
    parsed = parse_ai_enrichment(enrichment)
    if not parsed["should_enrich"]:
        return False, "abstain", parsed
    if parsed["confidence"] < _CONFIDENCE_THRESHOLD:
        return False, "low_confidence", parsed
    if not parsed["evidence_span"]:
        return False, "missing_evidence_span", parsed

    segment_key = normalize_text(segment_text)
    evidence_key = normalize_text(parsed["evidence_span"])
    if not evidence_key or evidence_key not in segment_key:
        return False, "evidence_not_in_segment", parsed

    if parsed["action"] not in allowed_actions():
        return False, "invalid_action", parsed
    if parsed["domain"] not in _ALLOWED_DOMAINS:
        return False, "invalid_domain", parsed

    accepted_object, object_score, object_reasons = evaluate_object_quality(parsed["object"])
    parsed["object_quality_score"] = object_score
    parsed["object_quality_reasons"] = object_reasons
    if not accepted_object:
        return False, "low_object_quality", parsed
    if is_generic_object(parsed["object"]):
        return False, "generic_object", parsed

    semantic_key = normalize_text(parsed["semantic_label"])
    if semantic_key in _BANNED_ABSTRACTIONS:
        return False, "banned_abstraction", parsed
    if semantic_key in _GENERIC_OBJECTS:
        return False, "generic_semantic_label", parsed
    if parsed["domain"] == "data" and not any(anchor in segment_key for anchor in _DATA_ANCHORS):
        return False, "unsupported_data_jump", parsed

    allowed_tools = {normalize_text(item) for item in allowed_tool_labels if normalize_text(item)}
    for tool in parsed["tools"]:
        if normalize_text(tool) not in allowed_tools:
            return False, "unsupported_tool", parsed

    hint_action = normalize_text(deterministic_hints.get("existing_action"))
    hint_object = normalize_text(deterministic_hints.get("existing_object"))
    hint_domain = normalize_text(deterministic_hints.get("existing_domain"))
    if (
        parsed["action"] == hint_action
        and normalize_text(parsed["object"]) == hint_object
        and parsed["domain"] == hint_domain
    ):
        return False, "duplicate_baseline", parsed

    return True, "accepted", parsed
