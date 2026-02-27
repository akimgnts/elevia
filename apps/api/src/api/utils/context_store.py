"""
context_store.py — SQLite storage for OfferContext / ProfileContext.

Deterministic cache only. Never logs raw text content.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "db" / "context.db"
_DB_LOCK = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS offer_contexts (
            offer_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS profile_contexts (
            profile_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=2)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=2000;")
    _ensure_schema(conn)
    return conn


def store_offer_context(offer_id: str, payload: dict) -> None:
    if not offer_id or not isinstance(payload, dict):
        return
    with _DB_LOCK:
        conn = _get_conn()
        try:
            conn.execute(
                """
                INSERT INTO offer_contexts (offer_id, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(offer_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (offer_id, json.dumps(payload, ensure_ascii=False), _utc_now()),
            )
            conn.commit()
        finally:
            conn.close()


def get_offer_context(offer_id: str) -> Optional[dict]:
    if not offer_id:
        return None
    with _DB_LOCK:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT payload FROM offer_contexts WHERE offer_id = ?",
                (offer_id,),
            ).fetchone()
            if not row:
                return None
            return json.loads(row["payload"])
        finally:
            conn.close()


def store_profile_context(profile_id: str, payload: dict) -> None:
    if not profile_id or not isinstance(payload, dict):
        return
    with _DB_LOCK:
        conn = _get_conn()
        try:
            conn.execute(
                """
                INSERT INTO profile_contexts (profile_id, payload, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (profile_id, json.dumps(payload, ensure_ascii=False), _utc_now()),
            )
            conn.commit()
        finally:
            conn.close()


def get_profile_context(profile_id: str) -> Optional[dict]:
    if not profile_id:
        return None
    with _DB_LOCK:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT payload FROM profile_contexts WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
            if not row:
                return None
            return json.loads(row["payload"])
        finally:
            conn.close()

