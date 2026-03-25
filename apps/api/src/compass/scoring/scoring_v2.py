"""Deterministic semantic scoring layer built on top of existing engine signals."""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Sequence
import re
import unicodedata


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
    result: set[str] = set()
    for value in values or []:
        key = _normalize(value)
        if key:
            result.add(key)
    return result


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
    if len(overlap) >= min(len(left_tokens), len(right_tokens)):
        return True
    return len(overlap) >= 2


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
) -> float:
    profile_role = _normalize(profile_intelligence.get("dominant_role_block"))
    offer_role = _normalize(offer_intelligence.get("dominant_role_block"))
    if not profile_role or not offer_role:
        return 0.2
    if profile_role == offer_role:
        return 1.0

    profile_secondary = _normalized_set(profile_intelligence.get("secondary_role_blocks"))
    offer_secondary = _normalized_set(offer_intelligence.get("secondary_role_blocks"))
    if (
        offer_role in profile_secondary
        or profile_role in offer_secondary
        or bool(profile_secondary & offer_secondary)
    ):
        return 0.6
    return 0.2


def _domain_alignment_score(
    profile_intelligence: Dict[str, Any],
    offer_intelligence: Dict[str, Any],
) -> float:
    profile_domains = [_normalize(item) for item in list(profile_intelligence.get("dominant_domains") or []) if _normalize(item)]
    offer_domains = [_normalize(item) for item in list(offer_intelligence.get("dominant_domains") or []) if _normalize(item)]
    shared = set(profile_domains) & set(offer_domains)
    if not shared:
        return 0.1
    if profile_domains and offer_domains and profile_domains[0] == offer_domains[0]:
        return 1.0
    if len(shared) >= 2:
        return 1.0
    return 0.5


def _gap_penalty(
    semantic_explainability: Dict[str, Any],
    offer_intelligence: Dict[str, Any],
) -> float:
    signal_alignment = semantic_explainability.get("signal_alignment")
    if not isinstance(signal_alignment, dict):
        return 0.0

    missing_signals = [
        str(item).strip()
        for item in list(signal_alignment.get("missing_core_signals") or semantic_explainability.get("missing_signals") or [])
        if str(item).strip()
    ]
    if not missing_signals:
        return 0.0

    required_skills = [
        str(item).strip()
        for item in list(offer_intelligence.get("required_skills") or [])
        if str(item).strip()
    ]
    if not required_skills:
        return round(_clamp(min(len(missing_signals), 3) * 0.12), 4)

    critical_missing = 0
    for missing in missing_signals:
        if any(_signals_match(missing, required) for required in required_skills):
            critical_missing += 1

    critical_ratio = critical_missing / max(len(required_skills), 1)
    secondary_missing = max(len(missing_signals) - critical_missing, 0)
    secondary_ratio = min(secondary_missing, 3) / 3.0
    penalty = (0.75 * critical_ratio) + (0.25 * secondary_ratio)
    return round(_clamp(penalty), 4)


def build_scoring_v2(
    *,
    profile_intelligence: Optional[Dict[str, Any]],
    offer_intelligence: Optional[Dict[str, Any]],
    semantic_explainability: Optional[Dict[str, Any]],
    matching_score: Any,
) -> Optional[Dict[str, Any]]:
    if not isinstance(profile_intelligence, dict) or not isinstance(offer_intelligence, dict):
        return None
    if not isinstance(semantic_explainability, dict):
        return None

    role_alignment = _role_alignment_score(profile_intelligence, offer_intelligence)
    domain_alignment = _domain_alignment_score(profile_intelligence, offer_intelligence)
    matching_base = _normalize_matching_score(matching_score)
    gap_penalty = _gap_penalty(semantic_explainability, offer_intelligence)

    score = _clamp(
        (0.35 * role_alignment)
        + (0.25 * domain_alignment)
        + (0.30 * matching_base)
        - (0.10 * gap_penalty)
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
    }
