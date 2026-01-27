"""
mapper.py - Deterministic Skill Mapper
Sprint 24 - Phase 1

Maps raw skill strings to ESCO skill URIs using:
1. Exact match on preferred labels
2. Exact match on alt/hidden labels
3. Optional fuzzy matching (difflib.SequenceMatcher)
"""

from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from .loader import EscoStore, get_esco_store
from .normalize import canon


# Fuzzy matching threshold (ratio >= this is considered a match)
FUZZY_THRESHOLD = 0.92


def _fuzzy_match(
    canon_skill: str,
    preferred_index: Dict[str, str],
    uri_to_preferred: Dict[str, str],
    threshold: float = FUZZY_THRESHOLD,
) -> Optional[tuple[str, str, float]]:
    """
    Find best fuzzy match using SequenceMatcher.

    Args:
        canon_skill: Canonicalized skill to match
        preferred_index: canon label -> URI index
        uri_to_preferred: URI -> preferred label (for result)
        threshold: Minimum ratio for match

    Returns:
        (uri, preferred_label, ratio) if match found, None otherwise
    """
    best_uri = None
    best_label = None
    best_ratio = 0.0

    for canon_label, uri in preferred_index.items():
        ratio = SequenceMatcher(None, canon_skill, canon_label).ratio()
        if ratio >= threshold and ratio > best_ratio:
            best_ratio = ratio
            best_uri = uri
            best_label = uri_to_preferred.get(uri, canon_label)

    if best_uri:
        return (best_uri, best_label, best_ratio)

    return None


def map_skill(
    raw_skill: str,
    store: Optional[EscoStore] = None,
    enable_fuzzy: bool = True,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
) -> Optional[Dict[str, Any]]:
    """
    Map a single skill to ESCO.

    Args:
        raw_skill: Raw skill string
        store: EscoStore (uses singleton if not provided)
        enable_fuzzy: Enable fuzzy matching as fallback
        fuzzy_threshold: Minimum ratio for fuzzy match

    Returns:
        Mapping dict if found, None otherwise:
        {
            "raw_skill": str,
            "canonical": str,
            "esco_id": str,
            "label": str,
            "confidence": float,
            "method": str
        }
    """
    if store is None:
        store = get_esco_store()

    if not raw_skill or not raw_skill.strip():
        return None

    canon_skill = canon(raw_skill)
    if not canon_skill:
        return None

    # 1. Exact match on preferred label
    if canon_skill in store.preferred_to_uri:
        uri = store.preferred_to_uri[canon_skill]
        return {
            "raw_skill": raw_skill,
            "canonical": canon_skill,
            "esco_id": uri,
            "label": store.uri_to_preferred.get(uri, canon_skill),
            "confidence": 1.0,
            "method": "preferred_label",
        }

    # 2. Exact match on alt/hidden label
    if canon_skill in store.alt_to_uri:
        uri = store.alt_to_uri[canon_skill]
        return {
            "raw_skill": raw_skill,
            "canonical": canon_skill,
            "esco_id": uri,
            "label": store.uri_to_preferred.get(uri, canon_skill),
            "confidence": 0.95,
            "method": "dictionary_alt_label",
        }

    # 3. Fuzzy match on preferred labels (optional)
    if enable_fuzzy:
        fuzzy_result = _fuzzy_match(
            canon_skill,
            store.preferred_to_uri,
            store.uri_to_preferred,
            threshold=fuzzy_threshold,
        )
        if fuzzy_result:
            uri, label, ratio = fuzzy_result
            return {
                "raw_skill": raw_skill,
                "canonical": canon_skill,
                "esco_id": uri,
                "label": label,
                "confidence": round(ratio, 3),
                "method": "fuzzy_strict",
            }

    return None


def map_skills(
    raw_skills: List[str],
    store: Optional[EscoStore] = None,
    max_results_per_skill: int = 1,
    enable_fuzzy: bool = True,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
) -> Dict[str, Any]:
    """
    Map a list of raw skills to ESCO.

    Args:
        raw_skills: List of raw skill strings
        store: EscoStore (uses singleton if not provided)
        max_results_per_skill: Max mappings per skill (currently only 1 supported)
        enable_fuzzy: Enable fuzzy matching as fallback
        fuzzy_threshold: Minimum ratio for fuzzy match

    Returns:
        {
            "mapped": [
                {
                    "raw_skill": str,
                    "canonical": str,
                    "esco_id": str,
                    "label": str,
                    "confidence": float,
                    "method": str
                }
            ],
            "unmapped": [str]
        }
    """
    if store is None:
        store = get_esco_store()

    mapped = []
    unmapped = []

    seen_uris = set()  # Deduplicate by URI

    for raw_skill in raw_skills:
        if not raw_skill or not raw_skill.strip():
            continue

        result = map_skill(
            raw_skill,
            store=store,
            enable_fuzzy=enable_fuzzy,
            fuzzy_threshold=fuzzy_threshold,
        )

        if result:
            # Deduplicate by URI
            if result["esco_id"] not in seen_uris:
                mapped.append(result)
                seen_uris.add(result["esco_id"])
        else:
            unmapped.append(raw_skill)

    return {
        "mapped": mapped,
        "unmapped": unmapped,
    }


def get_related_skills(
    esco_id: str,
    store: Optional[EscoStore] = None,
) -> List[str]:
    """
    Get related skill URIs for a given skill.

    Args:
        esco_id: ESCO skill URI
        store: EscoStore (uses singleton if not provided)

    Returns:
        List of related skill URIs
    """
    if store is None:
        store = get_esco_store()

    return store.skill_relations.get(esco_id, [])


def get_skill_label(
    esco_id: str,
    store: Optional[EscoStore] = None,
) -> Optional[str]:
    """
    Get preferred label for a skill URI.

    Args:
        esco_id: ESCO skill URI
        store: EscoStore (uses singleton if not provided)

    Returns:
        Preferred label or None if not found
    """
    if store is None:
        store = get_esco_store()

    return store.uri_to_preferred.get(esco_id)
