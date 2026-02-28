"""
generic_skill_stats.py - Deterministic global skill frequencies + signal score.

Read-only against offers DB. Caches in-memory by DB path.
No randomness. No external calls.
"""
from __future__ import annotations

import json
import logging
import math
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, Tuple

from api.utils.db import DB_PATH

logger = logging.getLogger("uvicorn.error")

_CACHE: Dict[str, Tuple[Dict[str, int], int]] = {}


def _db_path_key(db_path: str | Path | None) -> str:
    path = Path(db_path) if db_path else DB_PATH
    return str(path.resolve())


def clear_generic_skill_cache() -> None:
    _CACHE.clear()


def load_generic_skill_table(db_path: str | Path | None = None) -> Dict[str, int]:
    """
    Return {skill_label: offer_count} using DISTINCT offer_id.
    Caches results per DB path.
    """
    key = _db_path_key(db_path)
    if key in _CACHE:
        return _CACHE[key][0]

    path = Path(key)
    if not path.exists():
        logger.warning("GENERIC_SKILL_TABLE_BUILT %s", json.dumps({
            "event": "GENERIC_SKILL_TABLE_BUILT",
            "offers_n": 0,
            "unique_skills_n": 0,
            "top5_skills_by_freq": [],
            "max_freq": 0,
            "note": "db_missing",
        }))
        _CACHE[key] = ({}, 0)
        return {}

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        offer_count = conn.execute("SELECT COUNT(*) AS cnt FROM fact_offers").fetchone()[0]
        rows = conn.execute(
            "SELECT skill, COUNT(DISTINCT offer_id) AS cnt FROM fact_offer_skills GROUP BY skill"
        ).fetchall()
        freq: Dict[str, int] = {row["skill"]: int(row["cnt"]) for row in rows if row["skill"]}
    finally:
        conn.close()

    _CACHE[key] = (freq, int(offer_count))

    # Log summary once per cache build
    top5 = sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:5]
    max_freq = top5[0][1] if top5 else 0
    logger.info("GENERIC_SKILL_TABLE_BUILT %s", json.dumps({
        "event": "GENERIC_SKILL_TABLE_BUILT",
        "offers_n": int(offer_count),
        "unique_skills_n": len(freq),
        "top5_skills_by_freq": [label for label, _ in top5],
        "max_freq": int(max_freq),
    }))

    return freq


def get_offer_count(db_path: str | Path | None = None) -> int:
    key = _db_path_key(db_path)
    if key not in _CACHE:
        load_generic_skill_table(db_path)
    return _CACHE.get(key, ({}, 0))[1]


def compute_weight(freq: int, total_offers: int) -> float:
    """
    weight(skill) = clamp(log((N+1)/(freq+1)), 0, 3)
    """
    if total_offers <= 0 or freq <= 0:
        return 0.0
    value = math.log((total_offers + 1) / (freq + 1))
    if value < 0:
        value = 0.0
    if value > 3:
        value = 3.0
    return round(value, 4)


def signal_score(matched_skills: Iterable[str], freq_table: Dict[str, int], total_offers: int) -> float:
    """
    Sum of weights for matched skill labels.
    Dedupe skills deterministically.
    """
    if not matched_skills or not freq_table or total_offers <= 0:
        return 0.0

    seen = set()
    total = 0.0
    for skill in matched_skills:
        if not isinstance(skill, str):
            continue
        if skill in seen:
            continue
        seen.add(skill)
        freq = freq_table.get(skill)
        if freq:
            total += compute_weight(freq, total_offers)
    return round(total, 4)
