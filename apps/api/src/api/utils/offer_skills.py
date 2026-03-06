"""
offer_skills.py - Read-only utility for offer skills storage and lookup.
"""

import sqlite3
from typing import Dict, Iterable, List

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fact_offer_skills (
    offer_id   TEXT NOT NULL,
    skill      TEXT NOT NULL,
    skill_uri  TEXT,
    source     TEXT NOT NULL CHECK(source IN ('france_travail', 'rome', 'esco', 'manual')),
    confidence REAL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (offer_id, skill)
);
"""


def ensure_offer_skills_table(conn: sqlite3.Connection) -> None:
    """Create fact_offer_skills table if missing and add skill_uri column if absent."""
    conn.executescript(SCHEMA_SQL)

    # Add skill_uri column if missing (safe, idempotent)
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(fact_offer_skills)").fetchall()
    }
    if "skill_uri" not in columns:
        conn.execute("ALTER TABLE fact_offer_skills ADD COLUMN skill_uri TEXT")

    # Indexes
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fact_offer_skills_offer_id ON fact_offer_skills(offer_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fact_offer_skills_offer_id_skill_uri "
        "ON fact_offer_skills(offer_id, skill_uri)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fact_offer_skills_skill_uri ON fact_offer_skills(skill_uri)"
    )
    conn.commit()


def get_esco_skills_for_offer(
    conn: sqlite3.Connection,
    offer_id: str,
    limit: int = 12,
) -> List[str]:
    """Return ESCO skill labels for a single offer, sorted alphabetically."""
    try:
        rows = conn.execute(
            """
            SELECT skill FROM fact_offer_skills
            WHERE offer_id = ? AND source = 'esco'
            ORDER BY skill ASC
            LIMIT ?
            """,
            (str(offer_id), limit),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [row[0] for row in rows]


def get_offer_skills_by_offer_ids(
    conn: sqlite3.Connection,
    offer_ids: Iterable[str],
) -> Dict[str, Dict[str, List[str]]]:
    """Return mapping offer_id -> {skills, skills_uri} for given offer_ids."""
    ids = [str(oid) for oid in offer_ids if oid]
    if not ids:
        return {}

    placeholders = ",".join("?" for _ in ids)
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(fact_offer_skills)").fetchall()
    }
    has_uri = "skill_uri" in columns

    try:
        if has_uri:
            rows = conn.execute(
                f"""
                SELECT offer_id, skill, skill_uri
                FROM fact_offer_skills
                WHERE offer_id IN ({placeholders})
                ORDER BY offer_id ASC, skill ASC
                """,
                ids,
            ).fetchall()
        else:
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

    mapping: Dict[str, Dict[str, List[str]]] = {}
    for row in rows:
        offer_id = str(row[0])
        entry = mapping.setdefault(offer_id, {"skills": [], "skills_uri": []})
        entry["skills"].append(row[1])
        if has_uri and row[2]:
            entry["skills_uri"].append(row[2])
    return mapping
