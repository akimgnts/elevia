import sqlite3
from pathlib import Path
from typing import Optional
import threading
import numpy as np
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "db" / "embeddings.db"
_DB_LOCK = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS embeddings_cache (
            key TEXT NOT NULL,
            kind TEXT NOT NULL,
            model_version TEXT NOT NULL,
            vector BLOB NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (key, model_version, kind)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_embeddings_key_model ON embeddings_cache (key, model_version)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS profile_text_cache (
            profile_id TEXT PRIMARY KEY,
            text_hash TEXT NOT NULL,
            snippet TEXT,
            model_version TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    # Ensure model_version column exists (for older DBs)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(profile_text_cache)").fetchall()}
    if "model_version" not in cols:
        conn.execute("ALTER TABLE profile_text_cache ADD COLUMN model_version TEXT")


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=2)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=2000;")
    _ensure_schema(conn)
    return conn


def get_embedding(key: str, model_version: str, kind: str) -> Optional[np.ndarray]:
    if not key or not model_version or not kind:
        return None
    with _DB_LOCK:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT vector FROM embeddings_cache WHERE key = ? AND model_version = ? AND kind = ?",
                (key, model_version, kind),
            ).fetchone()
            if not row:
                return None
            blob = row["vector"]
            return np.frombuffer(blob, dtype=np.float32)
        finally:
            conn.close()


def store_embedding(key: str, model_version: str, kind: str, vector: np.ndarray) -> None:
    if not key or not model_version or not kind or vector is None:
        return
    arr = np.asarray(vector, dtype=np.float32)
    blob = arr.tobytes()
    with _DB_LOCK:
        conn = _get_conn()
        try:
            conn.execute(
                """
                INSERT INTO embeddings_cache (key, kind, model_version, vector, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key, model_version, kind) DO UPDATE SET
                    vector = excluded.vector,
                    created_at = excluded.created_at
                """,
                (key, kind, model_version, sqlite3.Binary(blob), _utc_now()),
            )
            conn.commit()
        finally:
            conn.close()


def store_profile_text_info(profile_id: str, text_hash: str, snippet: str, model_version: Optional[str]) -> None:
    if not profile_id or not text_hash:
        return
    with _DB_LOCK:
        conn = _get_conn()
        try:
            conn.execute(
                """
                INSERT INTO profile_text_cache (profile_id, text_hash, snippet, model_version, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                    text_hash = excluded.text_hash,
                    snippet = excluded.snippet,
                    model_version = excluded.model_version,
                    created_at = excluded.created_at
                """,
                (profile_id, text_hash, snippet, model_version, _utc_now()),
            )
            conn.commit()
        finally:
            conn.close()


def get_profile_text_info(profile_id: str) -> Optional[dict]:
    if not profile_id:
        return None
    with _DB_LOCK:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT text_hash, snippet, model_version, created_at FROM profile_text_cache WHERE profile_id = ?",
                (profile_id,),
            ).fetchone()
            if not row:
                return None
            return {
                "text_hash": row["text_hash"],
                "snippet": row["snippet"],
                "model_version": row["model_version"],
                "created_at": row["created_at"],
            }
        finally:
            conn.close()
