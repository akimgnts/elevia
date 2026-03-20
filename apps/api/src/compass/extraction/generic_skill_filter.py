from __future__ import annotations

from typing import Iterable, List, Tuple

from compass.canonical.canonical_store import normalize_canonical_key

_GENERIC_LABELS = {
    "communication",
    "teamwork",
    "travail en equipe",
    "organisation",
    "leadership",
    "problem solving",
    "resolution de problemes",
    "gestion de projet",
    "project management",
    "collaboration",
}


def is_generic_skill(value: str) -> bool:
    return normalize_canonical_key(value or "") in _GENERIC_LABELS


def filter_generic_mapping_inputs(mapping_inputs: Iterable[str], structured_units: Iterable[dict]) -> tuple[list[str], list[dict]]:
    contextual_generic = {
        normalize_canonical_key(unit.get("action_object_text") or "")
        for unit in structured_units
        if unit.get("object") and is_generic_skill(unit.get("object") or "")
    }
    kept: List[str] = []
    removed: List[dict] = []
    seen: set[str] = set()
    for item in mapping_inputs:
        if not isinstance(item, str):
            continue
        key = normalize_canonical_key(item)
        if not key or key in seen:
            continue
        seen.add(key)
        if key in _GENERIC_LABELS and key not in contextual_generic:
            removed.append({"value": item, "reason": "generic_without_context"})
            continue
        kept.append(item)
    return kept, removed


def filter_generic_structured_units(units: Iterable[dict]) -> tuple[list[dict], list[dict]]:
    kept: List[dict] = []
    removed: List[dict] = []
    for unit in units:
        obj = normalize_canonical_key(unit.get("object") or "")
        raw = normalize_canonical_key(unit.get("raw_text") or "")
        if obj in _GENERIC_LABELS and not unit.get("domain"):
            dropped = dict(unit)
            dropped["drop_reason"] = "generic_object_without_domain"
            removed.append(dropped)
            continue
        if raw in _GENERIC_LABELS and not unit.get("object"):
            dropped = dict(unit)
            dropped["drop_reason"] = "generic_raw_without_object"
            removed.append(dropped)
            continue
        kept.append(dict(unit))
    return kept, removed
