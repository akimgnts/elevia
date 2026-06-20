"""
profiles_db.py - Profile persistence utilities for PostgreSQL.

Handles:
- Saving parsed profiles to DB
- Fetching profiles by ID
- Profile versioning
"""

import json
import logging
from typing import Optional, Dict, Any
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_SQLITE_DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "db" / "offers.db"


def _get_database_url() -> str:
    """Get DATABASE_URL from environment."""
    return os.getenv("DATABASE_URL", "").strip()


def _sqlite_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_SQLITE_DB_PATH), timeout=2)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=2000;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            profile_data TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    return conn


def _save_profile_sqlite(profile_id: str, profile_data: Dict[str, Any], user_id: Optional[str]) -> bool:
    try:
        conn = _sqlite_conn()
        try:
            conn.execute(
                """
                INSERT INTO profiles (id, user_id, profile_data)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE
                SET user_id = excluded.user_id,
                    profile_data = excluded.profile_data,
                    updated_at = datetime('now')
                """,
                (profile_id, user_id, json.dumps(profile_data, ensure_ascii=False)),
            )
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as e:
        logger.error("[profiles_db] SQLite fallback save failed: %s", e)
        return False


def _get_profile_sqlite(profile_id: str) -> Optional[Dict[str, Any]]:
    try:
        conn = _sqlite_conn()
        try:
            row = conn.execute(
                """
                SELECT profile_data
                FROM profiles
                WHERE id = ?
                """,
                (profile_id,),
            ).fetchone()
        finally:
            conn.close()
    except Exception as e:
        logger.error("[profiles_db] SQLite fallback fetch failed: %s", e)
        return None

    if not row:
        return None
    raw = row["profile_data"]
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception as e:
        logger.error("[profiles_db] SQLite fallback payload decode failed: %s", e)
        return None


def save_profile(profile_id: str, profile_data: Dict[str, Any], user_id: Optional[str] = None) -> bool:
    """
    Save or update profile in database.

    Args:
        profile_id: Unique profile identifier
        profile_data: Profile object (parsed from CV)
        user_id: Optional user identifier

    Returns:
        True if saved, False if error
    """
    database_url = _get_database_url()
    if not database_url:
        logger.warning("[profiles_db] DATABASE_URL not set — using SQLite fallback")
        return _save_profile_sqlite(profile_id, profile_data, user_id)

    try:
        import psycopg

        with psycopg.connect(database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                # Upsert: insert or update
                cur.execute("""
                    INSERT INTO profiles (id, user_id, profile_data)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO UPDATE
                    SET profile_data = EXCLUDED.profile_data,
                        updated_at = now()
                """, (profile_id, user_id, json.dumps(profile_data)))
            conn.commit()

        logger.info("[profiles_db] Profile saved: profile_id=%s user_id=%s", profile_id, user_id)
        return True

    except Exception as e:
        logger.error("[profiles_db] Failed to save profile to PostgreSQL: %s", e)
        return _save_profile_sqlite(profile_id, profile_data, user_id)


def get_profile(profile_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch profile from database.

    Args:
        profile_id: Profile identifier

    Returns:
        Profile data dict or None if not found
    """
    database_url = _get_database_url()
    if not database_url:
        logger.debug("[profiles_db] DATABASE_URL not set — using SQLite fallback")
        return _get_profile_sqlite(profile_id)

    try:
        import psycopg

        with psycopg.connect(database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT profile_data
                    FROM profiles
                    WHERE id = %s
                """, (profile_id,))
                row = cur.fetchone()

        if row:
            logger.debug("[profiles_db] Profile found: profile_id=%s", profile_id)
            return row[0]  # JSONB returned as dict by psycopg

        logger.debug("[profiles_db] Profile not found: profile_id=%s", profile_id)
        return None

    except Exception as e:
        logger.error("[profiles_db] Failed to fetch profile from PostgreSQL: %s", e)
        return _get_profile_sqlite(profile_id)


def profile_exists(profile_id: str) -> bool:
    """Check if profile exists in database."""
    profile = get_profile(profile_id)
    return profile is not None
