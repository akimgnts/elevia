"""
apply_promotion.py — shared helper to populate skills_uri_promoted.

Used by parse routes; centralizes candidate selection and promotion.
"""
from __future__ import annotations

from typing import Iterable, List, Optional

import logging
import os

from .esco_promotion import promote_esco_skills

_MAX_CANDIDATES_DEFAULT = 60

logger = logging.getLogger(__name__)


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for v in values or []:
        if not isinstance(v, str):
            continue
        s = v.strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _promo_debug_enabled() -> bool:
    return os.getenv("ELEVIA_DEBUG_PROMOTION", "").lower() in {"1", "true", "yes"}


def _promo_log(msg: str, *args) -> None:
    if _promo_debug_enabled():
        logger.warning(msg, *args)
    else:
        logger.debug(msg, *args)


def apply_profile_esco_promotion(
    raw_profile: dict,
    base_skills_uri: Iterable[str],
    *,
    tight_candidates: Optional[Iterable[str]] = None,
    filtered_tokens: Optional[Iterable[str]] = None,
    cluster: Optional[str] = None,
    max_candidates: int = _MAX_CANDIDATES_DEFAULT,
    _promote_override: Optional[bool] = None,
) -> List[str]:
    """
    Populate raw_profile["skills_uri_promoted"] (flag-gated).

    Candidate source (strict):
      - tight_candidates if present and non-empty
      - else filtered_tokens
    """
    if not isinstance(raw_profile, dict):
        return []

    candidates: List[str] = []
    tight = list(tight_candidates or [])
    filtered = list(filtered_tokens or [])

    if tight:
        candidates = _dedupe_preserve_order(tight)
    else:
        candidates = _dedupe_preserve_order(filtered)

    if max_candidates and len(candidates) > max_candidates:
        candidates = candidates[:max_candidates]

    promoted = promote_esco_skills(
        candidates,
        base_skills_uri,
        cluster=cluster,
        _promote_override=_promote_override,
    )

    if promoted:
        raw_profile["skills_uri_promoted"] = promoted

    _promo_log(
        "ESCO_PROMO_PROFILE cluster=%s candidates_in=%d promoted_out=%d",
        (cluster or "none"),
        len(candidates),
        len(promoted),
    )

    return promoted


def apply_offer_esco_promotion(
    offer: dict,
    base_skills_uri: Iterable[str],
    *,
    candidate_labels: Optional[Iterable[str]] = None,
    cluster: Optional[str] = None,
    max_candidates: int = _MAX_CANDIDATES_DEFAULT,
    _promote_override: Optional[bool] = None,
) -> List[str]:
    if not isinstance(offer, dict):
        return []

    if candidate_labels is None:
        candidate_labels = offer.get("skills_unmapped") or []

    candidates = _dedupe_preserve_order(candidate_labels)
    if max_candidates and len(candidates) > max_candidates:
        candidates = candidates[:max_candidates]

    promoted = promote_esco_skills(
        candidates,
        base_skills_uri,
        cluster=cluster,
        _promote_override=_promote_override,
    )

    if promoted:
        offer["skills_uri_promoted"] = promoted
        merged = _dedupe_preserve_order((offer.get("skills_uri") or []) + promoted)
        offer["skills_uri"] = merged
        offer["skills_uri_count"] = len(merged)

    _promo_log(
        "ESCO_PROMO_OFFER cluster=%s candidates_in=%d promoted_out=%d",
        (cluster or "none"),
        len(candidates),
        len(promoted),
    )

    return promoted
