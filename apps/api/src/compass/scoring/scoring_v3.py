"""Calibrated deterministic semantic scoring layer built on top of the frozen engine."""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Sequence
import re
import unicodedata

_ROLE_ADJACENCY = {
    "data_analytics": {"business_analysis", "finance_ops", "software_it"},
    "business_analysis": {"data_analytics", "finance_ops", "project_ops", "supply_chain_ops", "sales_business_dev", "marketing_communication"},
    "finance_ops": {"business_analysis", "legal_compliance", "data_analytics"},
    "legal_compliance": {"finance_ops"},
    "sales_business_dev": {"marketing_communication", "business_analysis"},
    "marketing_communication": {"sales_business_dev", "business_analysis"},
    "hr_ops": {"project_ops"},
    "supply_chain_ops": {"project_ops", "business_analysis"},
    "project_ops": {"business_analysis", "supply_chain_ops", "hr_ops"},
    "software_it": {"data_analytics"},
    "generalist_other": set(),
}

_ROLE_FAMILIES = {
    "data_analytics": "data",
    "software_it": "data",
    "business_analysis": "business",
    "finance_ops": "finance",
    "legal_compliance": "finance",
    "sales_business_dev": "go_to_market",
    "marketing_communication": "go_to_market",
    "supply_chain_ops": "operations",
    "project_ops": "operations",
    "hr_ops": "people",
    "generalist_other": "generalist",
}

_ROLE_LABELS = {
    "high": "Alignement métier fort",
    "medium": "Alignement métier partiel",
    "low": "Alignement métier faible",
}

_DOMAIN_LABELS = {
    "high": "domaines cohérents",
    "medium": "domaines partiellement cohérents",
    "low": "domaines peu alignés",
}

_GAP_LABELS = {
    "low": "gaps limités",
    "medium": "gaps modérés",
    "high": "gaps critiques",
}


def _normalize(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return re.sub(r"\s+", " ", text)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _normalized_set(values: Iterable[Any] | None) -> set[str]:
    return {_normalize(value) for value in values or [] if _normalize(value)}


def _token_set(value: str) -> set[str]:
    return {token for token in _normalize(value).split() if token}


def _signals_match(left: str, right: str) -> bool:
    left_key = _normalize(left)
    right_key = _normalize(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True
    if left_key in right_key or right_key in left_key:
        return True
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens or not right_tokens:
        return False
    overlap = left_tokens & right_tokens
    return len(overlap) >= min(len(left_tokens), len(right_tokens)) or len(overlap) >= 2


def _normalize_matching_score(score: Any) -> float:
    if score is None:
        return 0.0
    try:
        value = float(score)
    except (TypeError, ValueError):
        return 0.0
    if value > 1.0:
        value = value / 100.0
    return round(_clamp(value), 4)


def _role_alignment_score(
    profile_intelligence: Dict[str, Any],
    offer_intelligence: Dict[str, Any],
    semantic_explainability: Dict[str, Any],
) -> float:
    profile_role = _normalize(profile_intelligence.get("dominant_role_block"))
    offer_role = _normalize(offer_intelligence.get("dominant_role_block"))
    if not profile_role or not offer_role:
        return 0.2
    if profile_role == offer_role:
        return 1.0

    profile_secondary = _normalized_set(profile_intelligence.get("secondary_role_blocks"))
    offer_secondary = _normalized_set(offer_intelligence.get("secondary_role_blocks"))
    if offer_role in profile_secondary or profile_role in offer_secondary:
        return 0.78
    if profile_secondary & offer_secondary:
        return 0.68
    if offer_role in _ROLE_ADJACENCY.get(profile_role, set()) or profile_role in _ROLE_ADJACENCY.get(offer_role, set()):
        return 0.55

    alignment = _normalize((semantic_explainability.get("role_alignment") or {}).get("alignment"))
    if alignment == "medium":
        return 0.5

    family_left = _ROLE_FAMILIES.get(profile_role)
    family_right = _ROLE_FAMILIES.get(offer_role)
    if family_left and family_right and family_left == family_right:
        return 0.35
    return 0.05


def _domain_alignment_score(
    profile_intelligence: Dict[str, Any],
    offer_intelligence: Dict[str, Any],
    semantic_explainability: Dict[str, Any],
) -> float:
    domain_alignment = semantic_explainability.get("domain_alignment") or {}
    shared = [_normalize(item) for item in list(domain_alignment.get("shared_domains") or []) if _normalize(item)]
    profile_only = [_normalize(item) for item in list(domain_alignment.get("profile_only_domains") or []) if _normalize(item)]
    offer_only = [_normalize(item) for item in list(domain_alignment.get("offer_only_domains") or []) if _normalize(item)]
    if not shared:
        profile_domains = _normalized_set(profile_intelligence.get("dominant_domains"))
        offer_domains = _normalized_set(offer_intelligence.get("dominant_domains"))
        shared = sorted(profile_domains & offer_domains)
        profile_only = sorted(profile_domains - offer_domains)
        offer_only = sorted(offer_domains - profile_domains)

    if not shared:
        return 0.3 if _normalize(profile_intelligence.get("dominant_role_block")) == _normalize(offer_intelligence.get("dominant_role_block")) else 0.1

    if len(shared) >= 2:
        return 1.0
    if not profile_only and not offer_only:
        return 1.0
    if len(shared) == 1 and (len(profile_only) + len(offer_only) <= 1):
        return 0.82
    return 0.62


def _semantic_strength(role_alignment: float, domain_alignment: float) -> float:
    return round(_clamp((0.62 * role_alignment) + (0.38 * domain_alignment)), 4)


def _matching_base(
    matching_score: Any,
    *,
    role_alignment: float,
    domain_alignment: float,
) -> float:
    raw = _normalize_matching_score(matching_score)
    semantic_strength = _semantic_strength(role_alignment, domain_alignment)

    if semantic_strength >= 0.8 and raw < semantic_strength:
        adjusted = (0.72 * raw) + (0.28 * semantic_strength)
    elif semantic_strength >= 0.62 and raw < semantic_strength:
        adjusted = (0.82 * raw) + (0.18 * semantic_strength)
    elif semantic_strength <= 0.25 and raw >= 0.55:
        adjusted = (0.78 * raw) + (0.22 * semantic_strength)
    else:
        adjusted = raw
    return round(_clamp(adjusted), 4)


def _gap_penalty(
    *,
    semantic_explainability: Dict[str, Any],
    offer_intelligence: Dict[str, Any],
    explanation: Optional[Dict[str, Any]],
    role_alignment: float,
    domain_alignment: float,
) -> float:
    signal_alignment = semantic_explainability.get("signal_alignment") or {}
    missing_signals = [
        str(item).strip()
        for item in list(signal_alignment.get("missing_core_signals") or semantic_explainability.get("missing_signals") or [])
        if str(item).strip()
    ]
    blockers = [str(item).strip() for item in list((explanation or {}).get("blockers") or []) if str(item).strip()]
    gaps = [str(item).strip() for item in list((explanation or {}).get("gaps") or []) if str(item).strip()]

    required_skills = [
        str(item).strip()
        for item in list(offer_intelligence.get("required_skills") or [])
        if str(item).strip()
    ]
    optional_skills = [
        str(item).strip()
        for item in list(offer_intelligence.get("optional_skills") or [])
        if str(item).strip()
    ]

    critical_missing = 0
    moderate_missing = 0
    seen_missing: set[str] = set()
    for missing in missing_signals + blockers + gaps:
        key = _normalize(missing)
        if not key or key in seen_missing:
            continue
        seen_missing.add(key)
        if any(_signals_match(missing, required) for required in required_skills):
            critical_missing += 1
        elif any(_signals_match(missing, optional) for optional in optional_skills):
            moderate_missing += 1
        else:
            moderate_missing += 1

    if not critical_missing and not moderate_missing:
        return 0.0

    required_base = max(len(required_skills), 1)
    critical_ratio = critical_missing / required_base
    moderate_ratio = min(moderate_missing, 3) / 3.0
    penalty = (0.72 * critical_ratio) + (0.28 * moderate_ratio)

    semantic_strength = _semantic_strength(role_alignment, domain_alignment)
    if semantic_strength >= 0.82 and critical_missing <= 1:
        penalty *= 0.72
    elif semantic_strength >= 0.68 and critical_missing <= 1:
        penalty *= 0.82
    elif semantic_strength <= 0.25 and critical_missing:
        penalty *= 1.08

    return round(_clamp(penalty), 4)


def _level(value: float) -> str:
    if value >= 0.8:
        return "high"
    if value >= 0.5:
        return "medium"
    return "low"


def _summary(*, role_alignment: float, domain_alignment: float, matching_base: float, gap_penalty: float) -> str:
    role_label = _ROLE_LABELS[_level(role_alignment)]
    domain_label = _DOMAIN_LABELS[_level(domain_alignment)]
    if matching_base >= 0.78:
        base_label = "matching de base solide"
    elif matching_base >= 0.55:
        base_label = "matching de base correct"
    else:
        base_label = "matching de base limité"
    gap_level = "high" if gap_penalty >= 0.55 else "medium" if gap_penalty >= 0.28 else "low"
    gap_label = _GAP_LABELS[gap_level]
    return f"{role_label}, {domain_label}, {base_label}, {gap_label}."


def build_scoring_v3(
    *,
    profile_intelligence: Optional[Dict[str, Any]],
    offer_intelligence: Optional[Dict[str, Any]],
    semantic_explainability: Optional[Dict[str, Any]],
    matching_score: Any,
    explanation: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if not isinstance(profile_intelligence, dict) or not isinstance(offer_intelligence, dict):
        return None
    if not isinstance(semantic_explainability, dict):
        return None

    role_alignment = _role_alignment_score(profile_intelligence, offer_intelligence, semantic_explainability)
    domain_alignment = _domain_alignment_score(profile_intelligence, offer_intelligence, semantic_explainability)
    matching_base = _matching_base(matching_score, role_alignment=role_alignment, domain_alignment=domain_alignment)
    gap_penalty = _gap_penalty(
        semantic_explainability=semantic_explainability,
        offer_intelligence=offer_intelligence,
        explanation=explanation,
        role_alignment=role_alignment,
        domain_alignment=domain_alignment,
    )

    score = _clamp(
        (0.40 * role_alignment)
        + (0.24 * domain_alignment)
        + (0.28 * matching_base)
        - (0.08 * gap_penalty)
    )
    score = round(score, 4)

    return {
        "score": score,
        "score_pct": int(round(score * 100)),
        "components": {
            "role_alignment": round(role_alignment, 4),
            "domain_alignment": round(domain_alignment, 4),
            "matching_base": round(matching_base, 4),
            "gap_penalty": round(gap_penalty, 4),
        },
        "summary": _summary(
            role_alignment=role_alignment,
            domain_alignment=domain_alignment,
            matching_base=matching_base,
            gap_penalty=gap_penalty,
        ),
    }
