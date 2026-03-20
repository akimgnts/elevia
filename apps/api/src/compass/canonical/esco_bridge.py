"""
esco_bridge.py — Canonical skill IDs → ESCO URIs bridge (Sprint 0700 Step 3).

Uses verified French ESCO labels stored as `esco_fr_label` in canonical_skills_core.json
to look up ESCO URIs directly. Bypasses cluster_policy allowlist (the canonical ontology
itself provides cluster segmentation).

Strategy:
  1. For each resolved canonical_id, read esco_fr_label from CanonicalStore.id_to_skill
  2. Call map_skill(esco_fr_label, enable_fuzzy=False) — exact French ESCO match only
  3. Collect ESCO URIs; skip if already in base_skills_uri
  4. Return deduped, sorted list of promoted URIs

Gate: ELEVIA_PROMOTE_ESCO=1  (default OFF)

Observability:
  ESCO_PROMOTION_STATS event logged as JSON at INFO when at least 1 canonical_id resolved.

Fallback:
  Any exception → returns [] — never raises, never breaks the request.

Score invariance:
  Only writes ESCO URIs (http://data.europa.eu/esco/...) — never canonical IDs (skill:xxx).
  Never touches matching_v1.py, idf.py, or weights_*.json.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Dict, List, Optional

from esco.mapper import map_skill

from .canonical_store import CanonicalStore, get_canonical_store

logger = logging.getLogger(__name__)

_MAX_BRIDGE_PROMOTED = 20


def _bridge_enabled(override: Optional[bool] = None) -> bool:
    if override is not None:
        return override
    return os.getenv("ELEVIA_PROMOTE_ESCO", "").lower() in {"1", "true", "yes"}


def _build_esco_fr_index(store: CanonicalStore) -> Dict[str, str]:
    """Return {canonical_id: esco_fr_label} for skills that have esco_fr_label set."""
    index: Dict[str, str] = {}
    for cid, entry in store.id_to_skill.items():
        fr_label = entry.get("esco_fr_label", "")
        if fr_label and isinstance(fr_label, str) and fr_label.strip():
            index[cid] = fr_label.strip()
    return index


def build_canonical_esco_promoted(
    resolved_canonical_ids: List[str],
    base_skills_uri: Optional[List[str]] = None,
    cluster: Optional[str] = None,
    store: Optional[CanonicalStore] = None,
    _promote_override: Optional[bool] = None,
    max_promoted: int = _MAX_BRIDGE_PROMOTED,
) -> List[str]:
    """
    Map resolved canonical skill IDs to ESCO URIs.

    Args:
        resolved_canonical_ids:  List of canonical_skill_ids (e.g. ["skill:machine_learning"])
        base_skills_uri:         Already-present ESCO URIs — promoted URIs must not duplicate
        cluster:                 Cluster hint (for logging only; no filtering applied)
        store:                   CanonicalStore (uses singleton if None)
        _promote_override:       Injectable for tests (None = read ELEVIA_PROMOTE_ESCO)
        max_promoted:            Cap on number of promoted URIs

    Returns:
        Sorted list of ESCO URIs promoted from canonical IDs.
        Empty list when: flag OFF, no resolved_canonical_ids, no esco_fr_label matches,
        or any exception.

    Invariants:
        - Only ESCO URIs in output (never "skill:xxx" IDs)
        - Deduped against base_skills_uri
        - Deterministic: same input → same output
        - Never raises
    """
    if not _bridge_enabled(_promote_override):
        return []

    if not resolved_canonical_ids:
        return []

    try:
        if store is None:
            store = get_canonical_store()

        if not store.is_loaded():
            return []

        base_set = {
            str(u).strip()
            for u in (base_skills_uri or [])
            if isinstance(u, str) and str(u).strip()
        }

        fr_index = _build_esco_fr_index(store)

        promoted: List[str] = []
        promoted_set: set = set()
        stats = {
            "promoted_from_canonical": 0,
            "unresolved_no_fr_label": 0,
            "esco_miss": 0,
            "duplicate_base": 0,
            "cap": 0,
        }

        for cid in resolved_canonical_ids:
            if len(promoted) >= max_promoted:
                stats["cap"] += 1
                break

            fr_label = fr_index.get(cid)
            if not fr_label:
                stats["unresolved_no_fr_label"] += 1
                continue

            result = map_skill(fr_label, enable_fuzzy=False)
            if not result or not result.get("esco_id"):
                stats["esco_miss"] += 1
                continue

            uri = str(result["esco_id"]).strip()
            if not uri:
                stats["esco_miss"] += 1
                continue

            if uri in base_set or uri in promoted_set:
                stats["duplicate_base"] += 1
                continue

            promoted.append(uri)
            promoted_set.add(uri)
            stats["promoted_from_canonical"] += 1

        promoted_sorted = sorted(promoted)

        if stats["promoted_from_canonical"] > 0 or stats["esco_miss"] > 0:
            logger.info(
                json.dumps({
                    "event": "ESCO_PROMOTION_STATS",
                    "cluster": cluster or "none",
                    "canonical_ids_in": len(resolved_canonical_ids),
                    "promoted_from_canonical": stats["promoted_from_canonical"],
                    "unresolved_no_fr_label": stats["unresolved_no_fr_label"],
                    "esco_miss": stats["esco_miss"],
                    "duplicate_base": stats["duplicate_base"],
                    "cap": stats["cap"],
                })
            )

        return promoted_sorted

    except Exception as exc:
        logger.warning("ESCO_BRIDGE failed: %s", type(exc).__name__)
        return []
