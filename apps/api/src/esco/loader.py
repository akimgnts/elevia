"""
loader.py - ESCO CSV Loader
Sprint 24 - Phase 1

Loads ESCO CSVs and builds indices for skill lookup.
Uses only stdlib (csv module).
"""

import csv
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from .normalize import canon
# Constants
ESCO_VERSION = "v1.2.1-fr"
ESCO_LOCALE = "fr"

# Default data path (relative to this file)
_DEFAULT_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "esco" / "v1_2_1" / "fr"


@dataclass
class EscoStore:
    """
    ESCO data store with lookup indices.

    Indices:
    - preferred_to_uri: canonical preferred label -> skill URI
    - alt_to_uri: canonical alt/hidden label -> skill URI
    - uri_to_preferred: skill URI -> preferred label
    - uri_to_skill_type: skill URI -> skill type (skill/competence, knowledge, etc.)
    - skill_relations: skill URI -> list of related skill URIs
    - hierarchy: skill URI -> parent URIs
    """
    preferred_to_uri: Dict[str, str] = field(default_factory=dict)
    alt_to_uri: Dict[str, str] = field(default_factory=dict)
    uri_to_preferred: Dict[str, str] = field(default_factory=dict)
    uri_to_skill_type: Dict[str, str] = field(default_factory=dict)
    skill_relations: Dict[str, List[str]] = field(default_factory=dict)
    hierarchy: Dict[str, Set[str]] = field(default_factory=dict)

    # Stats
    total_skills: int = 0
    total_alt_labels: int = 0


# Singleton store
_store: Optional[EscoStore] = None


def _read_csv(filepath: Path) -> List[Dict[str, str]]:
    """
    Read CSV with robust encoding handling.
    Tries utf-8, then utf-8-sig (BOM), then latin-1.
    """
    encodings = ["utf-8", "utf-8-sig", "latin-1"]

    for encoding in encodings:
        try:
            with open(filepath, "r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                return list(reader)
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Could not read {filepath} with any supported encoding")


def _canon_for_index(text: str) -> str:
    """
    Canonicalize labels for index building.
    Uses the same normalization as the mapper to avoid mismatches.
    """
    return canon(text)


def _parse_alt_labels(alt_labels_str: str) -> List[str]:
    """
    Parse alt labels from CSV field.
    ESCO uses newline-separated values within the field.
    Also handles comma-separated for robustness.
    """
    if not alt_labels_str:
        return []

    labels = []
    # Split by newline first (ESCO standard)
    for line in alt_labels_str.split("\n"):
        line = line.strip()
        if line:
            labels.append(line)

    return labels


def _load_skills(data_path: Path, store: EscoStore) -> None:
    """Load skills_fr.csv and build primary indices."""
    filepath = data_path / "skills_fr.csv"
    if not filepath.exists():
        raise FileNotFoundError(f"skills_fr.csv not found at {filepath}")

    rows = _read_csv(filepath)

    # Detect column names from first row (if any)
    if not rows:
        return

    # Expected columns (case-insensitive matching)
    col_map = {}
    sample_keys = rows[0].keys()
    for key in sample_keys:
        key_lower = key.lower().strip()
        if "concepturi" in key_lower or key_lower == "uri":
            col_map["uri"] = key
        elif "preferredlabel" in key_lower or key_lower == "preflabel":
            col_map["preferred"] = key
        elif "altlabels" in key_lower:
            col_map["alt"] = key
        elif "hiddenlabels" in key_lower:
            col_map["hidden"] = key
        elif "skilltype" in key_lower:
            col_map["type"] = key

    uri_col = col_map.get("uri", "conceptUri")
    pref_col = col_map.get("preferred", "preferredLabel")
    alt_col = col_map.get("alt", "altLabels")
    hidden_col = col_map.get("hidden", "hiddenLabels")
    type_col = col_map.get("type", "skillType")

    for row in rows:
        uri = row.get(uri_col, "").strip()
        preferred = row.get(pref_col, "").strip()
        alt_labels_raw = row.get(alt_col, "")
        hidden_labels_raw = row.get(hidden_col, "")
        skill_type = row.get(type_col, "").strip()

        if not uri or not preferred:
            continue

        # Build indices
        canon_pref = _canon_for_index(preferred)
        if canon_pref:
            store.preferred_to_uri[canon_pref] = uri

        store.uri_to_preferred[uri] = preferred

        if skill_type:
            store.uri_to_skill_type[uri] = skill_type

        # Parse and index alt labels
        alt_labels = _parse_alt_labels(alt_labels_raw)
        hidden_labels = _parse_alt_labels(hidden_labels_raw)

        for label in alt_labels + hidden_labels:
            canon_alt = _canon_for_index(label)
            if canon_alt and canon_alt not in store.alt_to_uri:
                store.alt_to_uri[canon_alt] = uri
                store.total_alt_labels += 1

        store.total_skills += 1


def _load_skill_relations(data_path: Path, store: EscoStore) -> None:
    """Load skill_skill_relations_fr.csv for skill relationships."""
    filepath = data_path / "skill_skill_relations_fr.csv"
    if not filepath.exists():
        return  # Optional file

    rows = _read_csv(filepath)
    if not rows:
        return

    # Detect columns
    sample_keys = rows[0].keys()
    orig_col = None
    related_col = None

    for key in sample_keys:
        key_lower = key.lower().strip()
        if "originalskilluri" in key_lower:
            orig_col = key
        elif "relatedskilluri" in key_lower:
            related_col = key

    if not orig_col or not related_col:
        return

    for row in rows:
        orig_uri = row.get(orig_col, "").strip()
        related_uri = row.get(related_col, "").strip()

        if orig_uri and related_uri:
            if orig_uri not in store.skill_relations:
                store.skill_relations[orig_uri] = []
            store.skill_relations[orig_uri].append(related_uri)


def _load_hierarchy(data_path: Path, store: EscoStore) -> None:
    """Load skills_hierarchy_fr.csv for skill hierarchy."""
    filepath = data_path / "skills_hierarchy_fr.csv"
    if not filepath.exists():
        return  # Optional file

    rows = _read_csv(filepath)
    if not rows:
        return

    # Hierarchy CSV has Level 0-3 URIs
    for row in rows:
        level_uris = []
        for i in range(4):
            uri_key = f"Level {i} URI"
            uri = row.get(uri_key, "").strip()
            if uri:
                level_uris.append(uri)

        # Build parent relationships
        for i, uri in enumerate(level_uris):
            if uri not in store.hierarchy:
                store.hierarchy[uri] = set()
            # Add all parent URIs
            for parent_uri in level_uris[:i]:
                store.hierarchy[uri].add(parent_uri)


def get_esco_store(data_path: Optional[Path] = None, force_reload: bool = False) -> EscoStore:
    """
    Get or create the ESCO store singleton.

    Args:
        data_path: Optional custom path to ESCO data directory
        force_reload: Force reload even if already loaded

    Returns:
        EscoStore with loaded indices
    """
    global _store

    if _store is not None and not force_reload:
        return _store

    if data_path is None:
        data_path = _DEFAULT_DATA_PATH

    store = EscoStore()

    # Load in order
    _load_skills(data_path, store)
    _load_skill_relations(data_path, store)
    _load_hierarchy(data_path, store)

    _store = store
    return _store


def validate_columns(data_path: Optional[Path] = None) -> Dict[str, List[str]]:
    """
    Validate and return detected column names for each CSV.
    Useful for debugging and verification.
    """
    if data_path is None:
        data_path = _DEFAULT_DATA_PATH

    result = {}

    csv_files = [
        "skills_fr.csv",
        "skill_skill_relations_fr.csv",
        "skills_hierarchy_fr.csv",
    ]

    for filename in csv_files:
        filepath = data_path / filename
        if filepath.exists():
            rows = _read_csv(filepath)
            if rows:
                result[filename] = list(rows[0].keys())

    return result


if __name__ == "__main__":
    # Validation mode - print column info
    print(f"ESCO Version: {ESCO_VERSION}")
    print(f"ESCO Locale: {ESCO_LOCALE}")
    print(f"Data path: {_DEFAULT_DATA_PATH}")
    print()

    print("=== Column Validation ===")
    cols = validate_columns()
    for filename, columns in cols.items():
        print(f"\n{filename}:")
        for col in columns:
            print(f"  - {col}")

    print("\n=== Loading Store ===")
    store = get_esco_store(force_reload=True)
    print(f"Total skills: {store.total_skills}")
    print(f"Total alt labels indexed: {store.total_alt_labels}")
    print(f"Preferred label index size: {len(store.preferred_to_uri)}")
    print(f"Alt label index size: {len(store.alt_to_uri)}")
    print(f"Skill relations: {len(store.skill_relations)} skills with relations")
    print(f"Hierarchy entries: {len(store.hierarchy)}")
