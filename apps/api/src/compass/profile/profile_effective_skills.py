"""
profile_effective_skills.py — Promoted ESCO URI channel (Step 1 scaffold).

Introduces a safe "effective skills" abstraction between the pipeline output
and the matching layer, fully gated by ELEVIA_PROMOTE_ESCO=1.

Data model (Step 1 — no population yet):
  profile["skills_uri"]           — existing, canonical ESCO URIs from pipeline
  profile["skills_uri_promoted"]  — NEW, empty by default, populated by later steps
  profile["skills_uri_effective"] — derived, = union(skills_uri, skills_uri_promoted)
                                    ONLY when flag is ON; not stored in profile dict

Feature flag: ELEVIA_PROMOTE_ESCO=1  (default OFF)

When flag OFF → identical output to pre-Sprint-6 behavior (zero behavior change).
When flag ON + promoted empty → identical to flag OFF.
When flag ON + promoted non-empty → effective set is the union.

Frozen files: matching_v1.py, idf.py, weights_* are NEVER touched.
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


def _promote_esco_enabled(override: Optional[bool] = None) -> bool:
    """Read feature flag; injectable via override for tests."""
    if override is not None:
        return override
    return os.getenv("ELEVIA_PROMOTE_ESCO", "").lower() in {"1", "true", "yes"}


def build_effective_skills_uri(
    base_list: List[str],
    raw_profile: dict,
    _promote_override: Optional[bool] = None,
) -> frozenset:
    """
    Return the effective frozenset of ESCO URIs used for matching.

    Args:
        base_list:         Deduplicated list built by extractors.py from
                           profile["skills_uri"] + profile["domain_uris"].
                           This is the canonical pre-Sprint-6 input.
        raw_profile:       Raw profile dict (plain dict, not Pydantic).
        _promote_override: Injectable for tests (None = read env var).

    Returns:
        frozenset[str] — safe to pass directly to ExtractedProfile.skills_uri.

    Invariant:
        When flag OFF or promoted list is empty/absent → frozenset(base_list)
        (bit-for-bit identical to the pre-Sprint-6 path).
    """
    promote_enabled = _promote_esco_enabled(_promote_override)

    # Defensive: base_list must be iterable (extractors.py always passes a list,
    # but callers in tests or future steps may not).
    if not isinstance(base_list, (list, tuple, set, frozenset)):
        base_list = []

    if not promote_enabled:
        return frozenset(base_list)

    # Defensive: raw_profile must be a dict; any other type means "no promoted data".
    try:
        promoted_raw = raw_profile.get("skills_uri_promoted") if isinstance(raw_profile, dict) else None
    except Exception:  # pragma: no cover — belt-and-suspenders for unexpected proxy objects
        promoted_raw = None

    if not isinstance(promoted_raw, list) or not promoted_raw:
        # Flag ON but promoted set is empty/absent — still identical output
        return frozenset(base_list)

    base_set = set(base_list)
    added: List[str] = []
    for uri in promoted_raw:
        if not isinstance(uri, str):
            continue  # skip non-string entries (ints, dicts, None …)
        uri = uri.strip()
        if uri and uri not in base_set:
            added.append(uri)
            base_set.add(uri)  # prevent intra-promoted dupes

    effective = frozenset(base_list + added)

    logger.debug(
        "PROMOTE_ESCO_ACTIVE base=%d promoted_raw=%d added=%d effective=%d",
        len(base_list),
        len(promoted_raw),
        len(added),
        len(effective),
    )

    return effective


def get_promote_trace(
    base_list: List[str],
    raw_profile: dict,
    _promote_override: Optional[bool] = None,
) -> dict:
    """
    Return a debug trace dict (for explain/debug endpoints).
    Does NOT affect scoring — call only when debug mode is enabled.

    Returns:
        {
          "promote_enabled": bool,
          "promoted_count": int,    # URIs in skills_uri_promoted
          "effective_count": int,   # URIs in the effective set
          "added_count": int,       # net new URIs from promotion
        }
    """
    promote_enabled = _promote_esco_enabled(_promote_override)
    promoted_raw = raw_profile.get("skills_uri_promoted") or []
    if not isinstance(promoted_raw, list):
        promoted_raw = []

    base_set = set(base_list)
    added_count = sum(
        1 for uri in promoted_raw
        if isinstance(uri, str) and uri.strip() and uri.strip() not in base_set
    )
    effective_count = len(base_set) + (added_count if promote_enabled else 0)

    return {
        "promote_enabled": promote_enabled,
        "promoted_count": len(promoted_raw),
        "effective_count": effective_count,
        "added_count": added_count if promote_enabled else 0,
    }
