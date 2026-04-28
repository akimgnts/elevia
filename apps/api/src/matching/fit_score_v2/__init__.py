"""fit_score_v2 — shadow scoring module.

Deterministic, AI-free, behind ELEVIA_FIT_SCORE_V2_SHADOW=1.
Does NOT modify matching_v1.py, idf.py, weights_*. Does NOT change ranking.

Single public entry point: score_offer_v2(profile, offer, *, ...).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .types import EligibilityStatus, FitScoreV2Result
from .eligibility import evaluate_eligibility
from .fit import compute_fit_score
from .preference import compute_preference_score


def score_offer_v2(
    profile: Any,
    offer: Dict[str, Any],
    *,
    domain_affinity: Optional[str] = None,
    offer_domain: Optional[str] = None,
    cv_domain: Optional[str] = None,
    match_debug: Optional[Dict[str, Any]] = None,
) -> FitScoreV2Result:
    """Compute v2 shadow scoring for one (profile, offer) pair.

    Profile may be an ExtractedProfile or a dict; only read access is performed.
    Offer is a dict; never mutated.

    Returns a FitScoreV2Result. fit_score and preference_score are None when the
    offer is not eligible (short-circuit) — eligibility_status.reasons explains why.
    """
    eligibility = evaluate_eligibility(profile, offer)
    if not eligibility.ok:
        return FitScoreV2Result(
            eligibility_status=eligibility,
            fit_score=None,
            preference_score=None,
            explain={
                "eligibility": {"ok": False, "reasons": list(eligibility.reasons)},
            },
        )

    fit_score, fit_explain = compute_fit_score(
        profile,
        offer,
        match_debug=match_debug,
        domain_affinity=domain_affinity,
        offer_domain=offer_domain,
        cv_domain=cv_domain,
    )
    preference_score, preference_explain = compute_preference_score(profile, offer)

    return FitScoreV2Result(
        eligibility_status=eligibility,
        fit_score=fit_score,
        preference_score=preference_score,
        explain={
            "eligibility": {"ok": True, "reasons": []},
            "fit": fit_explain,
            "preference": preference_explain,
        },
    )


__all__ = [
    "score_offer_v2",
    "FitScoreV2Result",
    "EligibilityStatus",
]
