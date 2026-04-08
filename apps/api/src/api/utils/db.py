"""
db.py - SQLite connection utility for inbox decisions and application tracking.
"""

import sqlite3
from pathlib import Path

from .offer_skills import ensure_offer_skills_table

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "db" / "offers.db"

_initialized = False


def _migrate_application_tracker(conn: sqlite3.Connection) -> None:
    """
    Migrate application_tracker from v0 (no user_id, 3-status enum) to v2.
    Safe to call multiple times — idempotent.
    """
    existing_tables = {
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }

    if "application_tracker" in existing_tables:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(application_tracker)")}
        if "user_id" in cols:
            return  # already on v2 schema

        # Clean up any previous partial migration
        if "application_tracker_v0" in existing_tables:
            conn.execute("DROP TABLE application_tracker_v0")

        conn.execute(
            "ALTER TABLE application_tracker RENAME TO application_tracker_v0"
        )

    # Create new v2 table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS application_tracker (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            offer_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN (
                'saved','cv_ready','applied','follow_up',
                'interview','rejected','won','archived'
            )),
            source TEXT NOT NULL DEFAULT 'manual' CHECK(source IN (
                'manual','assisted','auto_draft'
            )),
            note TEXT,
            next_follow_up_date TEXT,
            current_cv_cache_key TEXT,
            current_letter_cache_key TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            applied_at TEXT,
            last_status_change_at TEXT,
            UNIQUE(user_id, offer_id)
        )
    """)

    # Migrate old rows if v0 backup exists
    if conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='application_tracker_v0'"
    ).fetchone():
        conn.execute("""
            INSERT INTO application_tracker
                (id, offer_id, status, note, next_follow_up_date, created_at, updated_at)
            SELECT
                id,
                offer_id,
                CASE status
                    WHEN 'shortlisted' THEN 'saved'
                    WHEN 'dismissed'   THEN 'archived'
                    ELSE status
                END,
                note,
                next_follow_up_date,
                created_at,
                updated_at
            FROM application_tracker_v0
        """)
        conn.execute("DROP TABLE application_tracker_v0")

    conn.commit()


def _migrate_add_strategy_hint(conn: sqlite3.Connection) -> None:
    """Add strategy_hint column to application_tracker if missing (v2.1)."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(application_tracker)")}
    if cols and "strategy_hint" not in cols:
        conn.execute(
            "ALTER TABLE application_tracker ADD COLUMN strategy_hint TEXT"
        )
        conn.commit()


def get_connection() -> sqlite3.Connection:
    """Return a sqlite3 connection with Row factory. Initialises schema on first call."""
    global _initialized
    conn = sqlite3.connect(str(DB_PATH), timeout=2)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=2000;")

    if not _initialized:
        # Run migrations before CREATE IF NOT EXISTS so the new schema wins
        _migrate_application_tracker(conn)
        _migrate_add_strategy_hint(conn)

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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS application_tracker (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                offer_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN (
                    'saved','cv_ready','applied','follow_up',
                    'interview','rejected','won','archived'
                )),
                source TEXT NOT NULL DEFAULT 'manual' CHECK(source IN (
                    'manual','assisted','auto_draft'
                )),
                note TEXT,
                next_follow_up_date TEXT,
                current_cv_cache_key TEXT,
                current_letter_cache_key TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                applied_at TEXT,
                last_status_change_at TEXT,
                strategy_hint TEXT,
                UNIQUE(user_id, offer_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS application_status_history (
                id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL,
                from_status TEXT,
                to_status TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                note TEXT,
                FOREIGN KEY(application_id) REFERENCES application_tracker(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS apply_pack_runs (
                id TEXT PRIMARY KEY,
                application_id TEXT,
                user_id TEXT,
                offer_id TEXT NOT NULL,
                profile_fingerprint TEXT,
                cv_cache_key TEXT,
                letter_cache_key TEXT,
                template_id TEXT,
                template_version TEXT,
                payload_summary_json TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_application_tracker_user_offer "
            "ON application_tracker(user_id, offer_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_application_tracker_status "
            "ON application_tracker(status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_application_status_history_app "
            "ON application_status_history(application_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_apply_pack_runs_offer "
            "ON apply_pack_runs(offer_id)"
        )
        ensure_offer_skills_table(conn)
        conn.commit()
        _initialized = True

    return conn
