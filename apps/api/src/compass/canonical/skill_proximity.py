"""
skill_proximity.py — Explicit, deterministic proximity rules for canonical skills.

Safe by default:
  - If the JSON file is missing or malformed, returns empty results.
  - No impact on scoring core (read-only, display/debug only).
  - Exact matches are never treated as proximity links.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[5]
_DEFAULT_PROXIMITY_PATH = _REPO_ROOT / "audit" / "canonical_skill_proximity.json"


def _resolve_proximity_path() -> Path:
    env_path = os.getenv("ELEVIA_CANONICAL_PROXIMITY_PATH", "").strip()
    if env_path:
        return Path(env_path)
    return _DEFAULT_PROXIMITY_PATH


class ProximityStore:
    def __init__(self) -> None:
        self.loaded: bool = False
        self.rules_by_source: Dict[str, List[dict]] = {}

    def is_loaded(self) -> bool:
        return self.loaded


def _build_store(data: dict) -> ProximityStore:
    store = ProximityStore()
    rules = data.get("proximity_rules") or []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        status = str(rule.get("status", "active")).strip().lower()
        if status and status != "active":
            continue
        source = str(rule.get("source", "")).strip()
        target = str(rule.get("target", "")).strip()
        if not source or not target:
            continue
        relation = str(rule.get("relation", "")).strip() or "adjacent_to"
        try:
            strength = float(rule.get("strength", 0.0))
        except Exception:
            strength = 0.0
        entry = {
            "source": source,
            "target": target,
            "relation": relation,
            "strength": strength,
        }
        store.rules_by_source.setdefault(source, []).append(entry)

    # Deterministic order per source
    for source, entries in store.rules_by_source.items():
        store.rules_by_source[source] = sorted(
            entries,
            key=lambda r: (r.get("target", ""), r.get("relation", ""), -r.get("strength", 0.0)),
        )

    store.loaded = True
    return store


def _load_store() -> ProximityStore:
    path = _resolve_proximity_path()
    if not path.exists():
        logger.warning("SKILL_PROXIMITY path_not_found path=%s", path)
        return ProximityStore()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning("SKILL_PROXIMITY load_failed path=%s error=%s", path, type(exc).__name__)
        return ProximityStore()

    store = _build_store(data)
    logger.debug(
        "SKILL_PROXIMITY loaded sources=%d rules=%d",
        len(store.rules_by_source),
        sum(len(v) for v in store.rules_by_source.values()),
    )
    return store


_store: Optional[ProximityStore] = None


def get_proximity_store() -> ProximityStore:
    global _store
    if _store is None:
        _store = _load_store()
    return _store


def reset_proximity_store() -> None:
    global _store
    _store = None


def compute_skill_proximity(
    source_skill_ids: List[str],
    target_skill_ids: List[str],
    *,
    store: Optional[ProximityStore] = None,
) -> dict:
    """
    Compute proximity links between source and target canonical skill IDs.

    Returns:
      {
        "links": [ {source_id, target_id, relation, strength}, ... ],
        "summary": {
            "source_covered_by_proximity": int,
            "target_covered_by_proximity": int,
            "match_count": int,
            "max_strength": float,
            "avg_strength": float
        }
      }
    """
    store = store or get_proximity_store()
    if not store.loaded:
        return {"links": [], "summary": _empty_summary()}

    source_ids = sorted({str(s) for s in source_skill_ids if isinstance(s, str) and s})
    target_set = {str(t) for t in target_skill_ids if isinstance(t, str) and t}
    if not source_ids or not target_set:
        return {"links": [], "summary": _empty_summary()}

    links: List[dict] = []
    seen = set()
    for source_id in source_ids:
        for rule in store.rules_by_source.get(source_id, []):
            target_id = rule.get("target")
            if not target_id or target_id == source_id:
                continue
            if target_id not in target_set:
                continue
            key = (source_id, target_id, rule.get("relation", ""))
            if key in seen:
                continue
            seen.add(key)
            links.append(
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "relation": rule.get("relation", "adjacent_to"),
                    "strength": float(rule.get("strength", 0.0)),
                }
            )

    links = sorted(
        links,
        key=lambda r: (r.get("source_id", ""), r.get("target_id", ""), r.get("relation", ""), -r.get("strength", 0.0)),
    )

    strengths = [float(l.get("strength", 0.0)) for l in links]
    match_count = len(links)
    max_strength = max(strengths) if strengths else 0.0
    avg_strength = round(sum(strengths) / match_count, 4) if strengths else 0.0

    summary = {
        "source_covered_by_proximity": len({l["source_id"] for l in links}),
        "target_covered_by_proximity": len({l["target_id"] for l in links}),
        "match_count": match_count,
        "max_strength": max_strength,
        "avg_strength": avg_strength,
    }

    if match_count:
        logger.info(
            json.dumps(
                {
                    "event": "SKILL_PROXIMITY_STATS",
                    "source_skills": len(source_ids),
                    "target_skills": len(target_set),
                    "proximity_links": match_count,
                    "max_strength": max_strength,
                    "avg_strength": avg_strength,
                }
            )
        )

    return {"links": links, "summary": summary}


def _empty_summary() -> dict:
    return {
        "source_covered_by_proximity": 0,
        "target_covered_by_proximity": 0,
        "match_count": 0,
        "max_strength": 0.0,
        "avg_strength": 0.0,
    }
