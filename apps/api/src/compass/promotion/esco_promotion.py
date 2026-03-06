"""
esco_promotion.py — strict ESCO promotion mapping (Sprint 6 Step 2).

Promotes candidate labels into ESCO URIs when ELEVIA_PROMOTE_ESCO=1.
Deterministic: same input -> same output ordering.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, Iterable, List, Optional, Tuple

from esco.mapper import map_skill

from .aliases import ALIAS_TO_CANONICAL_RAW
from .cluster_policy import is_allowed_uri
from .normalize import normalize_skill_label

logger = logging.getLogger(__name__)

_MAX_PROMOTED_DEFAULT = 20

# Generic / noise tokens to reject
_GENERIC_BLACKLIST = {
    "experience", "experiences", "skill", "skills", "competence", "competences",
    "communication", "leadership", "autonomie", "autonome", "rigueur",
    "business", "strategy", "management", "project", "projects", "team",
    "paris", "london", "berlin", "madrid", "barcelona",
    "anglais", "english", "francais", "french", "espagnol", "spanish",
}

_SHORT_ALLOWLIST = {
    "ml", "ai", "bi", "sql", "r", "c++", "c#", ".net", "ci/cd",
}

def _promote_enabled(override: Optional[bool] = None) -> bool:
    if override is not None:
        return override
    return os.getenv("ELEVIA_PROMOTE_ESCO", "").lower() in {"1", "true", "yes"}


def _promo_debug_enabled() -> bool:
    return os.getenv("ELEVIA_DEBUG_PROMOTION", "").lower() in {"1", "true", "yes"}


def _promo_log(msg: str, *args) -> None:
    if _promo_debug_enabled():
        logger.warning(msg, *args)
    else:
        logger.debug(msg, *args)


def _build_alias_map() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for raw, canon in ALIAS_TO_CANONICAL_RAW.items():
        key = normalize_skill_label(raw)
        if not key:
            continue
        out[key] = canon
    return out


_ALIAS_TO_CANONICAL = _build_alias_map()


def _candidate_iter(values: Iterable) -> Iterable[str]:
    for v in values or []:
        if isinstance(v, str):
            yield v


def _reject_reason(norm: str) -> Optional[str]:
    if not norm:
        return "empty"
    if norm in _GENERIC_BLACKLIST:
        return "generic"
    if len(norm) < 3 and norm not in _SHORT_ALLOWLIST:
        return "too_short"
    return None


def promote_esco_skills(
    candidate_labels: Iterable,
    base_skills_uri: Iterable[str],
    *,
    cluster: Optional[str] = None,
    _promote_override: Optional[bool] = None,
    max_promoted: int = _MAX_PROMOTED_DEFAULT,
) -> List[str]:
    """
    Deterministically map candidate labels to ESCO URIs.

    Returns a stable-sorted list of promoted URIs (lexicographic).
    """
    if not _promote_enabled(_promote_override):
        return []

    base_set = {
        str(uri).strip()
        for uri in (base_skills_uri or [])
        if isinstance(uri, str) and str(uri).strip()
    }

    seen_labels = set()
    promoted: List[str] = []
    promoted_set = set()
    rejected: Dict[str, int] = {}
    rejected_labels: Dict[str, int] = {}

    for raw_label in _candidate_iter(candidate_labels):
        norm = normalize_skill_label(raw_label)
        if not norm or norm in seen_labels:
            continue
        seen_labels.add(norm)

        alias = _ALIAS_TO_CANONICAL.get(norm)
        if alias:
            candidate = alias
        else:
            reason = _reject_reason(norm)
            if reason:
                rejected[reason] = rejected.get(reason, 0) + 1
                continue
            candidate = norm

        result = map_skill(candidate, enable_fuzzy=False)
        if not result:
            rejected["unmapped"] = rejected.get("unmapped", 0) + 1
            continue

        canonical_label = str(result.get("label") or candidate).strip()
        uri = str(result.get("esco_id") or "").strip()
        if not is_allowed_uri(uri, cluster):
            rejected["cluster_disallow"] = rejected.get("cluster_disallow", 0) + 1
            if canonical_label:
                rejected_labels[canonical_label] = rejected_labels.get(canonical_label, 0) + 1
            continue
        if not uri:
            rejected["no_uri"] = rejected.get("no_uri", 0) + 1
            continue

        if uri in base_set or uri in promoted_set:
            rejected["duplicate_uri"] = rejected.get("duplicate_uri", 0) + 1
            continue

        promoted.append(uri)
        promoted_set.add(uri)
        if len(promoted) >= max_promoted:
            rejected["cap"] = rejected.get("cap", 0) + 1
            break

    promoted_sorted = sorted(promoted)

    _promo_log(
        "ESCO_PROMOTION cluster=%s candidates_in=%d promoted_out=%d rejected=%d",
        (cluster or "none"),
        len(seen_labels),
        len(promoted_sorted),
        sum(rejected.values()),
    )
    if rejected_labels:
        top = sorted(rejected_labels.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        _promo_log("ESCO_PROMOTION cluster=%s disallowed_top=%s", (cluster or "none"), top)

    return promoted_sorted
