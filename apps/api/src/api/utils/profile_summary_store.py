"""
profile_summary_store.py — SQLite + in-memory cache for ProfileSummaryV1.

Deterministic cache only. No raw CV text stored.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "db" / "context.db"
_DB_LOCK = threading.Lock()
_CACHE_LOCK = threading.Lock()
_CACHE_MAX = 128
_CACHE: "OrderedDict[str, dict]" = OrderedDict()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS profile_summaries (
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


def _cache_put(profile_id: str, payload: dict) -> None:
    if not profile_id or not isinstance(payload, dict):
        return
    with _CACHE_LOCK:
        if profile_id in _CACHE:
            _CACHE.move_to_end(profile_id)
        _CACHE[profile_id] = payload
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)


def _cache_get(profile_id: str) -> Optional[dict]:
    if not profile_id:
        return None
    with _CACHE_LOCK:
        payload = _CACHE.get(profile_id)
        if payload is not None:
            _CACHE.move_to_end(profile_id)
        return payload


def store_profile_summary(profile_id: str, payload: dict) -> None:
    if not profile_id or not isinstance(payload, dict):
        return
    with _DB_LOCK:
        conn = _get_conn()
        try:
            conn.execute(
                """
                INSERT INTO profile_summaries (profile_id, payload, updated_at)
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
    _cache_put(profile_id, payload)


def get_profile_summary(profile_id: str) -> Optional[dict]:
    cached = _cache_get(profile_id)
    if cached is not None:
        return cached
    if not profile_id:
        return None
    with _DB_LOCK:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT payload FROM profile_summaries WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
            if not row:
                return None
            payload = json.loads(row["payload"])
        finally:
            conn.close()
    if isinstance(payload, dict):
        _cache_put(profile_id, payload)
        return payload
    return None
