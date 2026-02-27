"""
esco_aliases.py — Deterministic ESCO alias loader (FR v0).

Provides a versioned alias table that maps common French CV vocabulary
to ESCO URIs, bridging the gap between how candidates write skills and
how ESCO labels them.

Architecture:
- Data file: apps/api/data/aliases/esco_alias_fr_v0.jsonl
- Lookup key: alias_key(alias) — canon() + accent strip (deterministic)
- Deduplication: by ESCO URI (same as validated_items)

Rules:
- Aliases ONLY map to verified ESCO URIs. validated_items remains ESCO-only.
- Never modifies scoring core. Display-only improvement.
- Deterministic: same input → same output.
- Graceful: any load error → empty alias map (never blocks baseline).

Adding a new alias (record format):
  {
    "alias": "gestion budgetaire",     # FR token as it appears in CVs (lowercase)
    "esco_label": "gérer les budgets", # ESCO preferred label (verified)
    "esco_uri": "http://data.europa.eu/esco/skill/<uuid>",  # verified URI
    "lang": "fr",
    "source": "manual",                # or "llm_suggestion" (not auto-applied)
    "confidence": 1.0                  # 0.8–1.0, informational only
  }
"""
from __future__ import annotations

import json
import logging
import unicodedata
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Versioned alias file
# Path(__file__) = .../apps/api/src/profile/esco_aliases.py
# parents[2]     = .../apps/api/
_ALIAS_FILE_V0_PRIMARY = (
    Path(__file__).resolve().parents[2]
    / "data" / "esco_alias_fr_v0.jsonl"
)
_ALIAS_FILE_V0_FALLBACK = (
    Path(__file__).resolve().parents[2]
    / "data" / "aliases" / "esco_alias_fr_v0.jsonl"
)

# Alias entry shape: alias_key → {uri, label, confidence, alias, source}
AliasEntry = Dict[str, object]

# Singleton
_alias_map: Optional[Dict[str, AliasEntry]] = None


def _strip_accents(text: str) -> str:
    """Remove accents while keeping base characters."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def alias_key(value: str) -> str:
    """
    Normalize alias for lookup key (accent-insensitive).
    Uses canon() from ESCO mapper, then strips accents.
    """
    try:
        from ..esco.normalize import canon
    except ImportError:
        import importlib
        canon = importlib.import_module("esco.normalize").canon
    return _strip_accents(canon(str(value)))


def load_alias_map(force_reload: bool = False) -> Dict[str, AliasEntry]:
    """
    Load and return the canonical alias map (singleton).

    Returns: dict[canonical_alias_str] → {"uri": str, "label": str, "confidence": float}

    Always returns a dict (empty on any error — graceful fallback).
    """
    global _alias_map

    if _alias_map is not None and not force_reload:
        return _alias_map

    alias_path = _ALIAS_FILE_V0_PRIMARY if _ALIAS_FILE_V0_PRIMARY.exists() else _ALIAS_FILE_V0_FALLBACK
    if not alias_path.exists():
        logger.warning("[esco_aliases] alias file not found: %s", alias_path)
        _alias_map = {}
        return _alias_map

    result: Dict[str, AliasEntry] = {}
    skipped = 0
    duplicates = 0

    try:
        lines = alias_path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("[esco_aliases] line %d: JSON parse error: %s", i, exc)
                skipped += 1
                continue

            alias_raw = rec.get("alias", "")
            uri = rec.get("esco_uri", "")
            label = rec.get("esco_label", "")

            if not alias_raw or not uri or not label:
                logger.warning("[esco_aliases] line %d: missing alias/uri/label — skip", i)
                skipped += 1
                continue

            key = alias_key(str(alias_raw))
            if not key:
                skipped += 1
                continue

            if key in result:
                existing = result[key]
                existing_uri = str(existing.get("uri", ""))
                if existing_uri != str(uri):
                    raise ValueError(
                        "[esco_aliases] alias key collision for key="
                        f"{key!r}: {existing.get('alias')!r} -> {existing_uri!r} "
                        f"conflicts with {str(alias_raw)!r} -> {str(uri)!r}"
                    )
                duplicates += 1
                continue

            # Keep first record for duplicate keys (same URI)
            result[key] = {
                "uri": str(uri),
                "label": str(label),
                "alias": str(alias_raw),
                "confidence": float(rec.get("confidence", 1.0)),
                "source": str(rec.get("source", "manual")),
            }

    except Exception as exc:
        logger.error("[esco_aliases] load error: %s — using empty alias map", exc)
        _alias_map = {}
        return _alias_map

    _alias_map = result
    logger.debug(
        "[esco_aliases] loaded %d aliases (%d skipped, %d duplicates) from %s",
        len(result), skipped, duplicates, alias_path.name,
    )
    return _alias_map


def alias_stats() -> Dict[str, object]:
    """
    Return alias table stats for health/observability.

    Returns:
        {"status": "ok"|"missing", "alias_count": int, "alias_file": str}
    """
    alias_path = _ALIAS_FILE_V0_PRIMARY if _ALIAS_FILE_V0_PRIMARY.exists() else _ALIAS_FILE_V0_FALLBACK
    if not alias_path.exists():
        return {"status": "missing", "alias_count": 0, "alias_file": str(alias_path)}

    amap = load_alias_map()
    return {
        "status": "ok",
        "alias_count": len(amap),
        "alias_file": alias_path.name,
    }


def validate_alias_targets_exist() -> None:
    """
    Validate that every alias URI exists in the ESCO index.

    Raises ValueError listing any broken URIs.
    Called at startup in dev mode or from health check.
    Graceful: if ESCO store unavailable, silently skips validation.
    """
    try:
        from ..esco.loader import get_esco_store
    except ImportError:
        import importlib
        get_esco_store = importlib.import_module("esco.loader").get_esco_store

    try:
        store = get_esco_store()
    except Exception as exc:
        logger.warning("[esco_aliases] validate: ESCO store unavailable: %s", exc)
        return

    amap = load_alias_map()
    broken = []
    for key, entry in amap.items():
        uri = entry["uri"]
        if uri not in store.uri_to_preferred:
            broken.append(f"  alias={key!r} → uri={uri!r} NOT IN ESCO index")

    if broken:
        raise ValueError(
            f"[esco_aliases] {len(broken)} alias(es) point to unknown ESCO URIs:\n"
            + "\n".join(broken)
        )

    logger.debug("[esco_aliases] validate: all %d alias URIs verified OK", len(amap))
