"""
canonical_mapper.py — Map raw skill strings to canonical skill IDs.

Strategy precedence (deterministic):
  1. synonym_match  — exact alias match (lower) in alias_to_id index
  2. tool_match     — exact tool match (lower) in tool_to_ids index
                      yields the FIRST canonical_id (primary mapping)
  3. unresolved     — no match found

Input:
  raw_labels: List[str]   — skill labels from tight_candidates or baseline

Output:
  List[CanonicalMapping]  — one entry per matched raw label (unresolved are included)

Contract:
  - Deterministic: same input → same output (stable insertion order, dedupe by lower)
  - Silent on unresolved: no exception, just strategy="unresolved"
  - No LLM, no fuzzy, no external calls
  - Skills never silently dropped (unresolved entries still returned)
  - Score invariance: reads only, never writes to skills_uri

Observability:
  - Structured log: CANONICAL_MAPPING raw=N mapped=N unresolved=N
  - Controlled by ELEVIA_DEBUG_CANONICAL env var
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

from .canonical_store import CanonicalStore, get_canonical_store, normalize_canonical_key

logger = logging.getLogger(__name__)


def _canonical_debug_enabled() -> bool:
    return os.getenv("ELEVIA_DEBUG_CANONICAL", "").lower() in {"1", "true", "yes"}


def _clog(msg: str, *args) -> None:
    if _canonical_debug_enabled():
        logger.warning(msg, *args)
    else:
        logger.debug(msg, *args)


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class CanonicalMapping:
    """Result of mapping a single raw label to the canonical ontology."""
    raw: str                    # original input (original casing)
    canonical_id: str           # e.g. "skill:data_analysis" — empty if unresolved
    label: str                  # canonical human label — empty if unresolved
    strategy: str               # "synonym_match" | "tool_match" | "unresolved"
    confidence: float           # 1.0 synonym / 0.8 tool / 0.0 unresolved
    cluster_name: str = ""      # cluster of the canonical skill (informational)
    genericity_score: float = 0.0  # from ontology entry


@dataclass
class MappingResult:
    """Aggregate result from map_to_canonical()."""
    mappings: List[CanonicalMapping] = field(default_factory=list)
    matched_count: int = 0
    unresolved_count: int = 0
    synonym_count: int = 0
    tool_count: int = 0


# ── Core logic ────────────────────────────────────────────────────────────────

def _map_single(raw: str, store: CanonicalStore) -> CanonicalMapping:
    key = normalize_canonical_key(raw)
    if not key:
        return CanonicalMapping(
            raw=raw, canonical_id="", label="",
            strategy="unresolved", confidence=0.0,
        )

    # 1. Synonym / alias match
    cid = store.alias_to_id.get(key)
    if cid:
        skill_entry = store.id_to_skill.get(cid, {})
        return CanonicalMapping(
            raw=raw,
            canonical_id=cid,
            label=skill_entry.get("label", cid),
            strategy="synonym_match",
            confidence=1.0,
            cluster_name=skill_entry.get("cluster_name", ""),
            genericity_score=float(skill_entry.get("genericity_score", 0.0)),
        )

    # 2. Tool match (primary canonical_id = first in list)
    tool_targets = store.tool_to_ids.get(key)
    if tool_targets:
        cid = tool_targets[0]
        skill_entry = store.id_to_skill.get(cid, {})
        return CanonicalMapping(
            raw=raw,
            canonical_id=cid,
            label=skill_entry.get("label", cid),
            strategy="tool_match",
            confidence=0.8,
            cluster_name=skill_entry.get("cluster_name", ""),
            genericity_score=float(skill_entry.get("genericity_score", 0.0)),
        )

    # 3. Unresolved
    return CanonicalMapping(
        raw=raw, canonical_id="", label="",
        strategy="unresolved", confidence=0.0,
    )


def map_to_canonical(
    raw_labels: List[str],
    cluster: Optional[str] = None,
    store: Optional[CanonicalStore] = None,
) -> MappingResult:
    """
    Map a list of raw skill labels to canonical skill IDs.

    Args:
        raw_labels:  Raw strings from tight_candidates or baseline skills.
        cluster:     Dominant cluster hint (informational; not used for filtering).
        store:       CanonicalStore instance (uses singleton if not provided).

    Returns:
        MappingResult with all mappings (including unresolved).

    Invariant:
        Never raises. Returns empty MappingResult if store is not loaded.
    """
    if store is None:
        store = get_canonical_store()

    if not store.is_loaded():
        _clog("CANONICAL_MAPPING store_not_loaded cluster=%s", cluster or "none")
        return MappingResult()

    if not raw_labels:
        return MappingResult()

    seen_lower: set = set()
    mappings: List[CanonicalMapping] = []
    matched = 0
    unresolved = 0
    synonym_c = 0
    tool_c = 0

    for raw in raw_labels:
        if not isinstance(raw, str):
            continue
        key = normalize_canonical_key(raw)
        if not key or key in seen_lower:
            continue
        seen_lower.add(key)

        m = _map_single(raw, store)
        mappings.append(m)

        if m.strategy == "unresolved":
            unresolved += 1
        else:
            matched += 1
            if m.strategy == "synonym_match":
                synonym_c += 1
            else:
                tool_c += 1

    result = MappingResult(
        mappings=mappings,
        matched_count=matched,
        unresolved_count=unresolved,
        synonym_count=synonym_c,
        tool_count=tool_c,
    )

    _clog(
        "CANONICAL_MAPPING cluster=%s raw_in=%d matched=%d synonym=%d tool=%d unresolved=%d",
        cluster or "none",
        len(seen_lower),
        matched,
        synonym_c,
        tool_c,
        unresolved,
    )

    return result
