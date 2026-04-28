"""Preference score — country / education / language / contract.

Separate from fit_score: a candidate fit can be high while preference is
low (and vice-versa). Never mixed into fit_score.

Weights:
  language    0.40
  education   0.25
  country     0.20
  contract    0.15

All inputs read-only. Returns (preference_score 0..100, explain).
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Set, Tuple

try:
    from matching.extractors import canonize_country, parse_education_level
except Exception:  # pragma: no cover — defensive fallback
    def canonize_country(v: str) -> str:
        return (v or "").strip().lower()

    def parse_education_level(v: Optional[str]) -> int:
        return 0


WEIGHT_LANGUAGE: float = 0.40
WEIGHT_EDUCATION: float = 0.25
WEIGHT_COUNTRY: float = 0.20
WEIGHT_CONTRACT: float = 0.15


def _languages_set(value: Any) -> Set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        items = [s.strip() for s in value.split(",") if s.strip()]
    elif isinstance(value, (set, frozenset, list, tuple)):
        items = []
        for v in value:
            if isinstance(v, str) and v.strip():
                items.append(v)
            elif isinstance(v, dict):
                code = v.get("code") or v.get("name") or v.get("label")
                if isinstance(code, str) and code.strip():
                    items.append(code)
    else:
        return set()
    return {s.lower().strip() for s in items if s}


def _profile_languages(profile: Any) -> Set[str]:
    raw = getattr(profile, "languages", None)
    if raw is None and isinstance(profile, dict):
        raw = profile.get("languages")
    return _languages_set(raw)


def _offer_languages(offer: Dict[str, Any]) -> Set[str]:
    return _languages_set(offer.get("languages"))


def _language_score(profile: Any, offer: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    offer_langs = _offer_languages(offer)
    if not offer_langs:
        return 1.0, {"matched": True, "reason": "offer has no required languages"}
    profile_langs = _profile_languages(profile)
    if not profile_langs:
        return 0.5, {"matched": None, "reason": "profile declares no languages"}
    overlap = offer_langs & profile_langs
    if overlap:
        return 1.0, {"matched": True, "overlap": sorted(overlap)}
    return 0.0, {"matched": False, "missing": sorted(offer_langs - profile_langs)}


def _education_score(profile: Any, offer: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    required_raw = offer.get("education") or offer.get("education_required")
    required = parse_education_level(required_raw)
    if required == 0:
        return 1.0, {"matched": True, "reason": "no education requirement"}
    profile_level = getattr(profile, "education_level", None)
    if profile_level is None and isinstance(profile, dict):
        profile_level = profile.get("education_level")
    profile_level = int(profile_level or 0)
    if profile_level >= required:
        return 1.0, {"matched": True, "profile_level": profile_level, "required": required}
    return 0.0, {"matched": False, "profile_level": profile_level, "required": required}


def _country_score(profile: Any, offer: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    preferred = getattr(profile, "preferred_countries", None)
    if preferred is None and isinstance(profile, dict):
        preferred = profile.get("preferred_countries") or []
    preferred_set: Set[str] = set()
    if isinstance(preferred, (set, frozenset, list, tuple)):
        preferred_set = {canonize_country(str(c)) for c in preferred if c}
    if not preferred_set:
        return 1.0, {"matched": True, "reason": "no country preferences"}
    offer_country_raw = offer.get("country") or offer.get("pays") or ""
    offer_country = canonize_country(str(offer_country_raw))
    if offer_country in preferred_set:
        return 1.0, {"matched": True, "country": offer_country}
    return 0.5, {"matched": False, "country": offer_country, "preferred": sorted(preferred_set)}


def _contract_score(profile: Any, offer: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """Neutral 1.0 — no contract preference signal in V1 profile schema yet."""
    return 1.0, {"matched": True, "reason": "no contract preference signal in profile (neutral)"}


def compute_preference_score(
    profile: Any, offer: Dict[str, Any]
) -> Tuple[int, Dict[str, Any]]:
    lang, lang_explain = _language_score(profile, offer)
    edu, edu_explain = _education_score(profile, offer)
    country, country_explain = _country_score(profile, offer)
    contract, contract_explain = _contract_score(profile, offer)

    raw = (
        WEIGHT_LANGUAGE * lang
        + WEIGHT_EDUCATION * edu
        + WEIGHT_COUNTRY * country
        + WEIGHT_CONTRACT * contract
    )
    raw_clamped = max(0.0, min(1.0, raw))
    score = int(round(100 * raw_clamped))

    explain = {
        "preference_score": score,
        "language": {"weight": WEIGHT_LANGUAGE, "score": lang, **lang_explain},
        "education": {"weight": WEIGHT_EDUCATION, "score": edu, **edu_explain},
        "country": {"weight": WEIGHT_COUNTRY, "score": country, **country_explain},
        "contract": {"weight": WEIGHT_CONTRACT, "score": contract, **contract_explain},
        "raw": round(raw, 4),
    }
    return score, explain
