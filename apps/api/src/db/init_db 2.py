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

        conn.commit()

        # Verify
        cursor.execute("SELECT COUNT(*) FROM fact_offers")
        count = cursor.fetchone()[0]

        print(f"[init_db] Database initialized successfully")
        print(f"[init_db] Table fact_offers exists with {count} rows")
        print(f"[init_db] WAL mode enabled for concurrency safety")

    except Exception as e:
        print(f"[init_db] ERROR: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    init_database()
