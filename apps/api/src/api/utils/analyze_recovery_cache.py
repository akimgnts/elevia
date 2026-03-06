"""
analyze_recovery_cache.py — Persistent cache for Analyze AI recovery.

Stores only hashes + recovered skills (no raw CV text).
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DEFAULT_DB = Path(__file__).parent.parent.parent.parent / "data" / "db" / "context.db"
_DB_LOCK = threading.Lock()

# Embed the LLM prompt version so any prompt change → new fingerprint → cache miss.
# To invalidate the entire cache: bump LLM_PROMPT_VERSION in analyze_skill_recovery.py.
from compass.analyze_skill_recovery import LLM_PROMPT_VERSION as _LLM_PROMPT_VERSION

PIPELINE_VERSION = f"analyze_recovery_v1_prompt_{_LLM_PROMPT_VERSION}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _db_path() -> Path:
    override = os.getenv("ELEVIA_ANALYZE_RECOVERY_DB", "").strip()
    if override:
        return Path(override)
    return _DEFAULT_DB


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analyze_recovery_cache (
            profile_fingerprint TEXT NOT NULL,
            request_hash TEXT NOT NULL,
            recovered_json TEXT NOT NULL,
            recovered_count INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (profile_fingerprint, request_hash)
        )
        """
    )


def _get_conn() -> sqlite3.Connection:
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=2)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=2000;")
    _ensure_schema(conn)
    return conn


def get_cached_recovery(profile_fingerprint: str, request_hash: str) -> Optional[list[dict]]:
    if not profile_fingerprint or not request_hash:
        return None
    with _DB_LOCK:
        conn = _get_conn()
        try:
            row = conn.execute(
                """
                SELECT recovered_json FROM analyze_recovery_cache
                WHERE profile_fingerprint = ? AND request_hash = ?
                """,
                (profile_fingerprint, request_hash),
            ).fetchone()
            if not row:
                return None
            payload = json.loads(row["recovered_json"])
            if isinstance(payload, list):
                return payload
            return None
        finally:
            conn.close()


def store_recovery_cache(
    profile_fingerprint: str,
    request_hash: str,
    recovered_skills: list[dict],
) -> None:
    if not profile_fingerprint or not request_hash:
        return
    if not isinstance(recovered_skills, list):
        return
    with _DB_LOCK:
        conn = _get_conn()
        try:
            conn.execute(
                """
                INSERT INTO analyze_recovery_cache (
                    profile_fingerprint, request_hash, recovered_json, recovered_count, created_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(profile_fingerprint, request_hash) DO UPDATE SET
                    recovered_json = excluded.recovered_json,
                    recovered_count = excluded.recovered_count,
                    created_at = excluded.created_at
                """,
                (
                    profile_fingerprint,
                    request_hash,
                    json.dumps(recovered_skills, ensure_ascii=False),
                    len(recovered_skills),
                    _utc_now(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
