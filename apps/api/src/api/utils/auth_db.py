"""
auth_db.py - SQLite persistence for MVP authentication.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "db" / "auth.db"
SESSION_TTL_DAYS = 30
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


def _expires_at_iso(days: int = SESSION_TTL_DAYS) -> str:
    return (_utc_now() + timedelta(days=days)).isoformat().replace("+00:00", "Z")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=2)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=2000;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            revoked_at TEXT,
            FOREIGN KEY(user_id) REFERENCES auth_users(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_auth_users_email ON auth_users(email)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_profiles (
            user_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES auth_users(id)
        )
        """
    )
    conn.commit()

    return conn


def normalize_email(email: str) -> str:
    return email.strip().lower()


def has_bootstrapped_users() -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM auth_users WHERE is_active = 1"
        ).fetchone()
        return bool(row and row["count"] > 0)
    finally:
        conn.close()


def get_user_by_email(email: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id, email, password_hash, role, is_active FROM auth_users WHERE email = ?",
            (normalize_email(email),),
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id, email, password_hash, role, is_active FROM auth_users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def upsert_user(email: str, password_hash: str, *, role: str = "admin", is_active: bool = True) -> sqlite3.Row:
    normalized_email = normalize_email(email)
    now = _utc_now_iso()
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM auth_users WHERE email = ?",
            (normalized_email,),
        ).fetchone()
        if existing:
            user_id = existing["id"]
            conn.execute(
                """
                UPDATE auth_users
                SET password_hash = ?, role = ?, is_active = ?, updated_at = ?
                WHERE id = ?
                """,
                (password_hash, role, 1 if is_active else 0, now, user_id),
            )
        else:
            user_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO auth_users (id, email, password_hash, role, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, normalized_email, password_hash, role, 1 if is_active else 0, now, now),
            )
        conn.commit()
        row = conn.execute(
            "SELECT id, email, role, is_active FROM auth_users WHERE id = ?",
            (user_id,),
        ).fetchone()
        assert row is not None
        return row
    finally:
        conn.close()


def create_session(user_id: str, token_hash: str) -> sqlite3.Row:
    session_id = str(uuid.uuid4())
    created_at = _utc_now_iso()
    expires_at = _expires_at_iso()
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO auth_sessions (id, user_id, token_hash, created_at, expires_at, last_seen_at, revoked_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL)
            """,
            (session_id, user_id, token_hash, created_at, expires_at, created_at),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT s.id, s.user_id, s.expires_at, u.email, u.role, u.is_active
            FROM auth_sessions s
            JOIN auth_users u ON u.id = s.user_id
            WHERE s.id = ?
            """,
            (session_id,),
        ).fetchone()
        assert row is not None
        return row
    finally:
        conn.close()


def get_session_by_token_hash(token_hash: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    try:
        return conn.execute(
            """
            SELECT
                s.id,
                s.user_id,
                s.token_hash,
                s.created_at,
                s.expires_at,
                s.last_seen_at,
                s.revoked_at,
                u.email,
                u.role,
                u.is_active
            FROM auth_sessions s
            JOIN auth_users u ON u.id = s.user_id
            WHERE s.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
    finally:
        conn.close()


def touch_session(session_id: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE auth_sessions SET last_seen_at = ? WHERE id = ?",
            (_utc_now_iso(), session_id),
        )
        conn.commit()
    finally:
        conn.close()


def revoke_session(session_id: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE auth_sessions SET revoked_at = ? WHERE id = ?",
            (_utc_now_iso(), session_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_profile(user_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT payload, updated_at FROM auth_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "profile": json.loads(str(row["payload"])),
            "updated_at": str(row["updated_at"]),
        }
    finally:
        conn.close()


def upsert_profile(user_id: str, profile: dict) -> dict:
    now = _utc_now_iso()
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO auth_profiles (user_id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (user_id, json.dumps(profile, ensure_ascii=False), now),
        )
        conn.commit()
        return {"profile": profile, "updated_at": now}
    finally:
        conn.close()
