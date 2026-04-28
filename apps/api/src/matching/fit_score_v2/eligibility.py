"""Eligibility evaluation — binary, short-circuits before fit scoring.

Reuses the same offer fields as matching_v1._hard_filter (without modifying it).
Adds required_languages check (ELIGIBILITY today is buried in V1 _score_languages).
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set

from .types import EligibilityStatus


def _profile_languages(profile: Any) -> Set[str]:
    raw = getattr(profile, "languages", None)
    if raw is None and isinstance(profile, dict):
        raw = profile.get("languages") or []
    if raw is None:
        return set()
    if isinstance(raw, str):
        raw = [s.strip() for s in raw.split(",") if s.strip()]
    if isinstance(raw, (set, frozenset)):
        return {str(x).lower().strip() for x in raw if isinstance(x, str)}
    if isinstance(raw, list):
        out: Set[str] = set()
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.add(item.lower().strip())
            elif isinstance(item, dict):
                code = item.get("code") or item.get("name") or item.get("label")
                if isinstance(code, str) and code.strip():
                    out.add(code.lower().strip())
        return out
    return set()


def _offer_required_languages(offer: Dict[str, Any]) -> Set[str]:
    raw = offer.get("languages") or []
    if isinstance(raw, str):
        raw = [s.strip() for s in raw.split(",") if s.strip()]
    if isinstance(raw, (set, frozenset)):
        return {str(x).lower().strip() for x in raw if isinstance(x, str)}
    if isinstance(raw, list):
        out: Set[str] = set()
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.add(item.lower().strip())
            elif isinstance(item, dict):
                code = item.get("code") or item.get("name") or item.get("label")
                if isinstance(code, str) and code.strip():
                    out.add(code.lower().strip())
        return out
    return set()


def evaluate_eligibility(profile: Any, offer: Dict[str, Any]) -> EligibilityStatus:
    """Check VIE eligibility + required offer fields + required languages."""
    reasons: List[str] = []

    if offer.get("is_vie") is not True:
        reasons.append("is_vie n'est pas True")

    if not (offer.get("country") or offer.get("pays")):
        reasons.append("pays manquant")

    if not (offer.get("title") or offer.get("job_title") or offer.get("intitule")):
        reasons.append("titre manquant")

    if not (offer.get("company") or offer.get("company_name") or offer.get("entreprise")):
        reasons.append("entreprise manquante")

    offer_langs = _offer_required_languages(offer)
    if offer_langs:
        profile_langs = _profile_languages(profile)
        # If profile has no language info we cannot decide → benefit of the doubt (eligible).
        # If profile declares languages and none overlap with the offer's required set → ineligible.
        if profile_langs and not (offer_langs & profile_langs):
            reasons.append(
                "langues requises non couvertes: " + ", ".join(sorted(offer_langs))
            )

    return EligibilityStatus(ok=not reasons, reasons=reasons)
