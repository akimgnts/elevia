"""
esco_grouping.py — ESCO collection-based skill grouping.

Groups validated skills by ESCO collection membership:
  Priority order:
    1. Numérique         (digital_skills_collection_fr.csv)
    2. Vert & Durabilité (green_skills_collection_fr.csv)
    3. Langues           (language_skills_collection_fr.csv)
    4. Transversales     (transversal_skills_collection_fr.csv)
    5. Recherche         (research_skills_collection_fr.csv)
    6. Connaissances     (skillType = knowledge, not in above)
    7. Aptitudes & Compétences (skill/competence, not in above)
    8. Autre             (no skillType info)

Grouping is:
  - Deterministic: same input → same group assignment
  - Display/debug only: does NOT affect scoring
  - No external APIs required
"""
from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

sys.path.insert(0, str(Path(__file__).parent.parent))

from esco.loader import get_esco_store

logger = logging.getLogger(__name__)

# Path to ESCO data files
_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "esco" / "v1_2_1" / "fr"

# Ordered collection definitions (priority: first match wins)
_COLLECTION_DEFS = [
    ("Numérique",          "digital_skills_collection_fr.csv"),
    ("Vert & Durabilité",  "green_skills_collection_fr.csv"),
    ("Langues",            "language_skills_collection_fr.csv"),
    ("Transversales",      "transversal_skills_collection_fr.csv"),
    ("Recherche",          "research_skills_collection_fr.csv"),
]

# Fallback group names from skillType field
_SKILLTYPE_GROUPS = {
    "knowledge":         "Connaissances",
    "skill/competence":  "Aptitudes & Compétences",
}
_GROUP_OTHER = "Autres"

# Stable group display order (determines sort in output)
_GROUP_ORDER: List[str] = [
    "Numérique",
    "Aptitudes & Compétences",
    "Connaissances",
    "Transversales",
    "Vert & Durabilité",
    "Langues",
    "Recherche",
    _GROUP_OTHER,
]


# ── Singleton cache ────────────────────────────────────────────────────────────

_collection_index: Optional[List[tuple[str, Set[str]]]] = None


def _get_collection_index() -> List[tuple[str, Set[str]]]:
    """
    Lazily build and cache an ordered list of (group_name, uri_set) tuples.
    Each uri_set contains all skill URIs belonging to that collection.
    """
    global _collection_index
    if _collection_index is not None:
        return _collection_index

    index: List[tuple[str, Set[str]]] = []
    if not _DATA_DIR.exists():
        logger.warning("[esco_grouping] data dir not found: %s", _DATA_DIR)
        _collection_index = [(name, set()) for name, _ in _COLLECTION_DEFS]
        return _collection_index
    for group_name, fname in _COLLECTION_DEFS:
        filepath = _DATA_DIR / fname
        if not filepath.exists():
            logger.warning("[esco_grouping] collection file not found: %s", fname)
            index.append((group_name, set()))
            continue
        uris: Set[str] = set()
        try:
            with open(filepath, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    uri = row.get("conceptUri", "").strip()
                    if uri:
                        uris.add(uri)
        except Exception as exc:
            logger.error("[esco_grouping] failed to load %s: %s", fname, exc)
        index.append((group_name, uris))
        logger.debug("[esco_grouping] loaded %s → %d URIs", group_name, len(uris))

    _collection_index = index
    return _collection_index


def _assign_group(uri: str) -> str:
    """Return the display group name for a given ESCO skill URI."""
    index = _get_collection_index()
    # Priority: first collection match wins
    for group_name, uri_set in index:
        if uri in uri_set:
            return group_name

    # Fallback: use skillType from ESCO store
    store = get_esco_store()
    skill_type = store.uri_to_skill_type.get(uri, "")
    for key, group in _SKILLTYPE_GROUPS.items():
        if key in skill_type:
            return group

    return _GROUP_OTHER


def group_validated_items(
    validated_items: List[Dict[str, str]],
) -> List[Dict]:
    """
    Group validated skill items by ESCO collection membership.

    Args:
        validated_items: List of {uri, label} dicts from strict_filter_skills().

    Returns:
        List of group dicts, stable-ordered:
        [
            {
                "group": "Numérique",
                "count": 5,
                "items": ["python (programmation informatique)", ...]
            },
            ...
        ]
        Groups with zero items are omitted.
    """
    if not validated_items:
        return []

    groups: Dict[str, List[str]] = {}
    try:
        for item in validated_items:
            uri = item.get("uri", "")
            label = item.get("label", "") or uri
            group = _assign_group(uri)
            groups.setdefault(group, []).append(label)
    except Exception as exc:
        logger.error("[esco_grouping] grouping failed: %s", exc)
        labels = sorted(
            [item.get("label") or item.get("uri") or "" for item in validated_items if item]
        )
        return [{
            "group": _GROUP_OTHER,
            "count": len(labels),
            "items": labels,
        }]

    # Sort within each group for determinism
    for g in groups:
        groups[g].sort()

    # Order groups by _GROUP_ORDER, then alphabetically for any extras
    ordered: List[Dict] = []
    seen: Set[str] = set()
    for group_name in _GROUP_ORDER:
        if group_name in groups:
            ordered.append({
                "group": group_name,
                "count": len(groups[group_name]),
                "items": groups[group_name],
            })
            seen.add(group_name)

    # Any groups not in _GROUP_ORDER (shouldn't happen, but be safe)
    for group_name in sorted(groups):
        if group_name not in seen:
            ordered.append({
                "group": group_name,
                "count": len(groups[group_name]),
                "items": groups[group_name],
            })

    return ordered
