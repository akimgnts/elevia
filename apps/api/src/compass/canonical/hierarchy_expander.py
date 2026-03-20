"""
hierarchy_expander.py — Minimal 1-level parent expansion for canonical skills.

Rules:
  - Explicit relations only (from canonical_store.hierarchy)
  - No probabilistic inference
  - No propagation beyond 1 level (no grandparents, no transitive closure)
  - No double-counting: parents added only if not already in input set
  - Deterministic: same input → same output (insertion order preserved)

Input:
  canonical_ids: List[str]   — canonical_skill_ids from canonical_mapper output

Output:
  ExpandedResult with:
    expanded_ids   — original IDs + newly added parents (order preserved)
    added_parents  — IDs that were added (not in original)
    expansion_map  — {child_id: parent_id} for tracing

Score invariance:
  Read-only. Never touches skills_uri.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .canonical_store import CanonicalStore, get_canonical_store

logger = logging.getLogger(__name__)


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class ExpandedResult:
    expanded_ids: List[str]              # original + parents (deduped, ordered)
    added_parents: List[str]             # parent IDs newly introduced
    expansion_map: Dict[str, str]        # child_id -> parent_id (for trace)


# ── Core logic ────────────────────────────────────────────────────────────────

def expand_hierarchy(
    canonical_ids: List[str],
    store: Optional[CanonicalStore] = None,
) -> ExpandedResult:
    """
    Expand canonical_ids by 1 level using explicit hierarchy relations.

    Args:
        canonical_ids:  Canonical skill IDs (e.g. ["skill:deep_learning", ...])
        store:          CanonicalStore (singleton if not provided)

    Returns:
        ExpandedResult

    Invariant:
        - Input IDs are never removed
        - Expansion bounded to 1 level
        - Empty hierarchy → ExpandedResult(expanded_ids=canonical_ids, added=[])
        - Never raises
    """
    if store is None:
        store = get_canonical_store()

    input_set = dict.fromkeys(canonical_ids)  # preserve order, dedupe
    base_ids = list(input_set)

    if not store.is_loaded() or not store.hierarchy:
        return ExpandedResult(
            expanded_ids=base_ids,
            added_parents=[],
            expansion_map={},
        )

    added: List[str] = []
    expansion_map: Dict[str, str] = {}
    seen = set(base_ids)

    for cid in base_ids:
        parent = store.hierarchy.get(cid)
        if parent and parent not in seen:
            added.append(parent)
            seen.add(parent)
            expansion_map[cid] = parent

    expanded = base_ids + added

    if added:
        logger.debug(
            "HIERARCHY_EXPAND input=%d added=%d expansions=%s",
            len(base_ids),
            len(added),
            list(expansion_map.items())[:5],
        )

    return ExpandedResult(
        expanded_ids=expanded,
        added_parents=added,
        expansion_map=expansion_map,
    )
