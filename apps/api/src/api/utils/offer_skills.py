"""
offer_skills.py - Read-only utility for offer skills storage and lookup.
"""

import sqlite3
from typing import Dict, Iterable, List

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fact_offer_skills (
    offer_id   TEXT NOT NULL,
    skill      TEXT NOT NULL,
    source     TEXT NOT NULL CHECK(source IN ('france_travail', 'rome', 'esco', 'manual')),
    confidence REAL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (offer_id, skill)
);
CREATE INDEX IF NOT EXISTS idx_fact_offer_skills_offer_id ON fact_offer_skills(offer_id);
"""


def ensure_offer_skills_table(conn: sqlite3.Connection) -> None:
    """Create fact_offer_skills table if missing."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def get_offer_skills_by_offer_ids(
    conn: sqlite3.Connection,
    offer_ids: Iterable[str],
) -> Dict[str, List[str]]:
    """Return mapping offer_id -> list of skills for given offer_ids."""
    ids = [str(oid) for oid in offer_ids if oid]
    if not ids:
        return {}

    placeholders = ",".join("?" for _ in ids)
    try:
        rows = conn.execute(
            f"""
            SELECT offer_id, skill
            FROM fact_offer_skills
            WHERE offer_id IN ({placeholders})
            ORDER BY offer_id ASC, skill ASC
            """,
            ids,
        ).fetchall()
    except sqlite3.OperationalError:
        return {}

    mapping: Dict[str, List[str]] = {}
    for row in rows:
        mapping.setdefault(str(row[0]), []).append(row[1])
    return mapping
