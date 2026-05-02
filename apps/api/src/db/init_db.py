#!/usr/bin/env python3
"""
init_db.py - Initialize SQLite database for offers
Sprint: Live Data Switch

Creates the fact_offers table with WAL mode for concurrency safety.
Runnable directly: python3 apps/api/src/db/init_db.py
"""

import sqlite3
from pathlib import Path

# Database path (relative to repo root when run from apps/api/)
DB_DIR = Path(__file__).parent.parent.parent / "data" / "db"
DB_PATH = DB_DIR / "offers.db"


def init_database() -> None:
    """
    Initialize SQLite database with fact_offers table.

    - Sets WAL mode for concurrency safety
    - Creates table if not exists
    - Creates indexes for common queries
    """
    # Ensure directory exists
    DB_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[init_db] Initializing database at: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    cursor = conn.cursor()

    try:
        # WAL mode for better concurrency (reads don't block writes)
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")

        # Create fact_offers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fact_offers (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL CHECK(source IN ('france_travail', 'business_france')),
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                company TEXT,
                city TEXT,
                country TEXT,
                publication_date TEXT,
                contract_duration INTEGER,
                start_date TEXT,
                payload_json TEXT NOT NULL,
                last_updated TEXT NOT NULL
            )
        """)

        # Index for common queries (newest first)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fact_offers_pubdate
            ON fact_offers(publication_date DESC)
        """)

        # Index for source filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fact_offers_source
            ON fact_offers(source)
        """)

        # Create canonical_skills table (phase 2 skill dictionary)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS canonical_skills (
                canonical_id TEXT PRIMARY KEY,
                label TEXT NOT NULL UNIQUE,
                skill_type TEXT NOT NULL,
                domain_tag TEXT NOT NULL,
                occurrences INTEGER NOT NULL,
                aliases_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

        # Index for label lookup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_canonical_skills_label
            ON canonical_skills(label)
        """)

        # Index for domain filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_canonical_skills_domain
            ON canonical_skills(domain_tag)
        """)

        # Create canonical_aliases table (maps raw labels to canonical_ids)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS canonical_aliases (
                alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
                alias TEXT NOT NULL UNIQUE,
                canonical_id TEXT NOT NULL,
                language TEXT DEFAULT 'en',
                normalization_type TEXT DEFAULT 'normalized',
                created_at TEXT NOT NULL,
                FOREIGN KEY (canonical_id) REFERENCES canonical_skills(canonical_id) ON DELETE CASCADE
            )
        """)

        # Index for alias lookup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_canonical_aliases_alias
            ON canonical_aliases(alias)
        """)

        # Index for canonical_id lookup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_canonical_aliases_canonical_id
            ON canonical_aliases(canonical_id)
        """)

        conn.commit()

        # Verify
        cursor.execute("SELECT COUNT(*) FROM fact_offers")
        offers_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM canonical_skills")
        skills_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM canonical_aliases")
        aliases_count = cursor.fetchone()[0]

        print(f"[init_db] Database initialized successfully")
        print(f"[init_db] Table fact_offers exists with {offers_count} rows")
        print(f"[init_db] Table canonical_skills exists with {skills_count} rows")
        print(f"[init_db] Table canonical_aliases exists with {aliases_count} rows")
        print(f"[init_db] WAL mode enabled for concurrency safety")

    except Exception as e:
        print(f"[init_db] ERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    init_database()
