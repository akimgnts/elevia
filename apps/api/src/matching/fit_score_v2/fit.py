"""Fit score — weighted CORE/SECONDARY/CONTEXT skill match × domain × title.

Deterministic, AI-free. Reads V1's match_debug.skills tier breakdown when
available; otherwise falls back to a flat skills-intersection ratio.

base_skill_fit = w_core * core_match + w_sec * sec_match + w_ctx * ctx_match - missing_core_penalty
fit_score      = clamp(base_skill_fit) * domain_multiplier * title_multiplier

Profile and offer skills_uri lists are NEVER mutated.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from api.utils.generic_skills_filter import HARD_GENERIC_URIS
except Exception:  # pragma: no cover — import-time fallback
    HARD_GENERIC_URIS = frozenset()


WEIGHT_CORE: float = 1.0
WEIGHT_SECONDARY: float = 0.5
WEIGHT_CONTEXT: float = 0.2
MISSING_CORE_PENALTY_CAP: float = 0.10
MISSING_CORE_PENALTY_PER_ITEM: float = 0.05

DOMAIN_MULTIPLIERS: Dict[str, float] = {
    "aligned": 1.10,
    "adjacent": 1.00,
    "distant": 0.85,
    "neutral": 1.00,
}
TITLE_MULTIPLIER_HIT: float = 1.05
TITLE_MULTIPLIER_MISS: float = 1.00


def _profile_skills_uri(profile: Any) -> List[str]:
    raw = getattr(profile, "skills_uri", None)
    if raw is None and isinstance(profile, dict):
        raw = profile.get("skills_uri")
    if not raw:
        return []
    if isinstance(raw, (list, tuple, set, frozenset)):
        return [str(u) for u in raw if isinstance(u, str)]
    return []


def _offer_skills_uri(offer: Dict[str, Any]) -> List[str]:
    raw = offer.get("skills_uri")
    if not raw:
        return []
    if isinstance(raw, (list, tuple, set, frozenset)):
        return [str(u) for u in raw if isinstance(u, str)]
    return []


def _filter_generic_offer_uris(uris: List[str]) -> List[str]:
    if not uris or not HARD_GENERIC_URIS:
        return list(uris)
    return [u for u in uris if u not in HARD_GENERIC_URIS]


def _tier_counts_from_match_debug(
    match_debug: Optional[Dict[str, Any]],
) -> Optional[Dict[str, int]]:
    """Extract CORE/SECONDARY/CONTEXT matched/missing counts from V1 match_debug."""
    if not match_debug or not isinstance(match_debug, dict):
        return None
    skills = match_debug.get("skills") if isinstance(match_debug.get("skills"), dict) else None
    if not skills:
        return None
    keys = (
        "matched_core",
        "missing_core",
        "matched_secondary",
        "missing_secondary",
        "matched_context",
        "missing_context",
    )
    if not any(k in skills for k in keys):
        return None
    out = {k: len(skills.get(k) or []) for k in keys}
    if sum(out.values()) == 0:
        return None
    return out


def _compute_tier_match_ratio(matched: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, matched / total))


def _compute_base_skill_fit(
    tier_counts: Optional[Dict[str, int]],
    fallback_match_ratio: float,
) -> Tuple[float, Dict[str, Any]]:
    """Return (base_skill_fit clamped to [0,1], explain dict)."""
    if tier_counts is None:
        # Flat fallback: treat as one SECONDARY bucket.
        weighted = WEIGHT_SECONDARY * fallback_match_ratio
        max_weighted = WEIGHT_SECONDARY * 1.0
        base = weighted / max_weighted if max_weighted > 0 else 0.0
        return max(0.0, min(1.0, base)), {
            "mode": "flat",
            "match_ratio": round(fallback_match_ratio, 4),
            "missing_core_penalty": 0.0,
        }

    core_total = tier_counts["matched_core"] + tier_counts["missing_core"]
    sec_total = tier_counts["matched_secondary"] + tier_counts["missing_secondary"]
    ctx_total = tier_counts["matched_context"] + tier_counts["missing_context"]

    core_ratio = _compute_tier_match_ratio(tier_counts["matched_core"], core_total)
    sec_ratio = _compute_tier_match_ratio(tier_counts["matched_secondary"], sec_total)
    ctx_ratio = _compute_tier_match_ratio(tier_counts["matched_context"], ctx_total)

    weighted = (
        WEIGHT_CORE * core_ratio
        + WEIGHT_SECONDARY * sec_ratio
        + WEIGHT_CONTEXT * ctx_ratio
    )
    max_weighted = (
        (WEIGHT_CORE if core_total > 0 else 0.0)
        + (WEIGHT_SECONDARY if sec_total > 0 else 0.0)
        + (WEIGHT_CONTEXT if ctx_total > 0 else 0.0)
    )
    base = weighted / max_weighted if max_weighted > 0 else 0.0

    missing_core_penalty = min(
        MISSING_CORE_PENALTY_CAP,
        MISSING_CORE_PENALTY_PER_ITEM * tier_counts["missing_core"],
    )
    base_after_penalty = max(0.0, base - missing_core_penalty)
    base_clamped = max(0.0, min(1.0, base_after_penalty))

    return base_clamped, {
        "mode": "weighted_tier",
        "core": {"matched": tier_counts["matched_core"], "total": core_total, "ratio": round(core_ratio, 4)},
        "secondary": {"matched": tier_counts["matched_secondary"], "total": sec_total, "ratio": round(sec_ratio, 4)},
        "context": {"matched": tier_counts["matched_context"], "total": ctx_total, "ratio": round(ctx_ratio, 4)},
        "weighted_raw": round(base, 4),
        "missing_core_penalty": round(missing_core_penalty, 4),
        "base_after_penalty": round(base_clamped, 4),
    }


def _resolve_domain_multiplier(domain_affinity: Optional[str]) -> Tuple[float, str]:
    if not domain_affinity:
        return 1.00, "none"
    label = str(domain_affinity).strip().lower()
    return DOMAIN_MULTIPLIERS.get(label, 1.00), label


def _resolve_title_multiplier(
    cv_domain: Optional[str],
    offer_domain: Optional[str],
    domain_affinity: Optional[str],
) -> Tuple[float, bool]:
    if not cv_domain or not offer_domain:
        return TITLE_MULTIPLIER_MISS, False
    affinity_label = (domain_affinity or "").strip().lower()
    if str(cv_domain).strip().lower() == str(offer_domain).strip().lower() and affinity_label == "aligned":
        return TITLE_MULTIPLIER_HIT, True
    return TITLE_MULTIPLIER_MISS, False


def compute_fit_score(
    profile: Any,
    offer: Dict[str, Any],
    *,
    match_debug: Optional[Dict[str, Any]] = None,
    domain_affinity: Optional[str] = None,
    offer_domain: Optional[str] = None,
    cv_domain: Optional[str] = None,
) -> Tuple[Optional[int], Dict[str, Any]]:
    """Return (fit_score 0..100 or None, explain).

    fit_score is None only when no skills information at all is available
    (offer has no skills AND match_debug is absent).
    """
    profile_uris: Set[str] = set(_profile_skills_uri(profile))
    offer_uris_raw = _offer_skills_uri(offer)
    offer_uris_filtered = _filter_generic_offer_uris(offer_uris_raw)

    tier_counts = _tier_counts_from_match_debug(match_debug)

    # Fallback flat ratio (used when match_debug is absent or has no tiers).
    if offer_uris_filtered and profile_uris:
        offer_set = set(offer_uris_filtered)
        intersection = offer_set & profile_uris
        fallback_ratio = len(intersection) / max(1, len(offer_set))
    else:
        fallback_ratio = 0.0

    # If neither tiered info nor any skills overlap → score is undefined.
    if tier_counts is None and not offer_uris_filtered:
        explain: Dict[str, Any] = {
            "fit_score": None,
            "skill_fit": {"mode": "unscoreable", "reason": "offer has no scorable skills"},
            "domain_multiplier": {"label": "n/a", "value": 1.00},
            "title_multiplier": {"hit": False, "value": 1.00},
        }
        return None, explain

    base, skill_explain = _compute_base_skill_fit(tier_counts, fallback_ratio)

    domain_mult, domain_label = _resolve_domain_multiplier(domain_affinity)
    title_mult, title_hit = _resolve_title_multiplier(cv_domain, offer_domain, domain_affinity)

    raw = base * domain_mult * title_mult
    raw_clamped = max(0.0, min(1.0, raw))
    fit_score = int(round(100 * raw_clamped))

    explain = {
        "fit_score": fit_score,
        "skill_fit": skill_explain,
        "domain_multiplier": {"label": domain_label, "value": domain_mult},
        "title_multiplier": {"hit": title_hit, "value": title_mult},
        "raw": round(raw, 4),
        "raw_clamped": round(raw_clamped, 4),
        "offer_uri_count": len(offer_uris_raw),
        "offer_uri_count_after_generic_filter": len(offer_uris_filtered),
        "profile_uri_count": len(profile_uris),
    }
    return fit_score, explain
