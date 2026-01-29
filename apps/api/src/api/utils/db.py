"""
db.py - SQLite connection utility for inbox decisions.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "db" / "offers.db"

_initialized = False


def get_connection() -> sqlite3.Connection:
    """Return a sqlite3 connection with Row factory. Creates offer_decisions table on first call."""
    global _initialized
    conn = sqlite3.connect(str(DB_PATH), timeout=2)
    conn.row_factory = sqlite3.Row

    if not _initialized:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS offer_decisions (
                profile_id TEXT NOT NULL,
                offer_id   TEXT NOT NULL,
                status     TEXT NOT NULL CHECK(status IN ('SHORTLISTED', 'DISMISSED')),
                note       TEXT,
                decided_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (profile_id, offer_id)
            )
        """)
        conn.commit()
        _initialized = True

    return conn
