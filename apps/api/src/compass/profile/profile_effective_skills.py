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

Boundary note:
  Parsing and enrichment layers may populate `skills_uri_promoted`, but the
  merge into the effective matching input only happens here.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EffectiveSkillsView:
    """
    Explicit matching-preparation view.

    This is the single place where the final skill URI set used by matching is
    derived from:
    - baseline ESCO URIs
    - domain URIs
    - promoted ESCO URIs

    Extraction/canonical/enrichment layers may populate input channels, but the
    effective matching set is only derived here.
    """

    promote_enabled: bool
    base_uris: tuple[str, ...]
    domain_uris: tuple[str, ...]
    promoted_uris: tuple[str, ...]
    effective_uris: FrozenSet[str]
    added_domain_uris: tuple[str, ...]
    added_promoted_uris: tuple[str, ...]
    provenance: Dict[str, tuple[str, ...]]


def _promote_esco_enabled(override: Optional[bool] = None) -> bool:
    """Read feature flag; injectable via override for tests."""
    if override is not None:
        return override
    return os.getenv("ELEVIA_PROMOTE_ESCO", "").lower() in {"1", "true", "yes"}


def _debug_effective_enabled() -> bool:
    return os.getenv("ELEVIA_DEBUG_PROFILE_EFFECTIVE", "").lower() in {"1", "true", "yes"}


def _add_source(provenance: Dict[str, Set[str]], uri: str, source: str) -> None:
    if uri not in provenance:
        provenance[uri] = set()
    provenance[uri].add(source)


def _clean_uri_list(raw_value) -> List[str]:
    if not isinstance(raw_value, list):
        return []
    return [
        str(uri).strip()
        for uri in raw_value
        if isinstance(uri, str) and str(uri).strip()
    ]


def build_effective_skills_view(
    base_list: List[str],
    raw_profile: dict,
    _promote_override: Optional[bool] = None,
) -> EffectiveSkillsView:
    """
    Build the explicit matching-preparation view for a profile.

    This function is intentionally pure with respect to matching behavior:
    same inputs -> same view.
    """
    promote_enabled = _promote_esco_enabled(_promote_override)

    if not isinstance(base_list, (list, tuple, set, frozenset)):
        base_list = []

    base_uris = [
        str(uri).strip()
        for uri in base_list
        if isinstance(uri, str) and str(uri).strip()
    ]
    base_set = set(base_uris)

    try:
        promoted_raw = raw_profile.get("skills_uri_promoted") if isinstance(raw_profile, dict) else None
        domain_raw = raw_profile.get("domain_uris") if isinstance(raw_profile, dict) else None
    except Exception:  # pragma: no cover
        promoted_raw = None
        domain_raw = None

    promoted_uris = _clean_uri_list(promoted_raw)
    domain_uris = _clean_uri_list(domain_raw)

    provenance: Dict[str, Set[str]] = {}
    for uri in base_uris:
        _add_source(provenance, uri, "base_uri")

    effective_ordered: List[str] = list(base_uris)
    added_domain: List[str] = []
    for uri in domain_uris:
        _add_source(provenance, uri, "domain_uri")
        if uri not in base_set:
            base_set.add(uri)
            effective_ordered.append(uri)
            added_domain.append(uri)

    added_promoted: List[str] = []
    if promote_enabled and promoted_uris:
        for uri in promoted_uris:
            _add_source(provenance, uri, "esco_promotion")
            if uri not in base_set:
                base_set.add(uri)
                effective_ordered.append(uri)
                added_promoted.append(uri)
            else:
                _add_source(provenance, uri, "base_uri")

    return EffectiveSkillsView(
        promote_enabled=promote_enabled,
        base_uris=tuple(base_uris),
        domain_uris=tuple(domain_uris),
        promoted_uris=tuple(promoted_uris),
        effective_uris=frozenset(effective_ordered),
        added_domain_uris=tuple(added_domain),
        added_promoted_uris=tuple(added_promoted),
        provenance={
            uri: tuple(sorted(sources))
            for uri, sources in provenance.items()
        },
    )


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
    view = build_effective_skills_view(
        base_list,
        raw_profile,
        _promote_override=_promote_override,
    )
    effective = view.effective_uris

    if _debug_effective_enabled() and isinstance(raw_profile, dict):
        total_raw = len(view.base_uris) + len(view.promoted_uris) + len(view.domain_uris)
        debug = {
            "total_raw_skills": total_raw,
            "unique_canonical_skills": len(effective),
            "duplicates_removed": max(total_raw - len(effective), 0),
            "provenance": dict(view.provenance),
        }
        raw_profile["profile_effective_skills_debug"] = debug

    if view.promote_enabled:
        logger.debug(
            "PROMOTE_ESCO_ACTIVE base=%d promoted_raw=%d added=%d effective=%d",
            len(view.base_uris),
            len(view.promoted_uris),
            len(view.added_promoted_uris),
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
    view = build_effective_skills_view(
        base_list,
        raw_profile,
        _promote_override=_promote_override,
    )

    return {
        "promote_enabled": view.promote_enabled,
        "base_count": len(view.base_uris),
        "domain_count": len(view.domain_uris),
        "promoted_count": len(view.promoted_uris),
        "effective_count": len(view.effective_uris),
        "added_domain_count": len(view.added_domain_uris),
        "added_promoted_count": len(view.added_promoted_uris) if view.promote_enabled else 0,
        "added_count": len(view.added_promoted_uris) if view.promote_enabled else 0,
        "input_channels": ["base_uri", "domain_uri", "esco_promotion"],
        "provenance": dict(view.provenance),
    }
