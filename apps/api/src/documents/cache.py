"""
cache.py — SQLite document cache for CV Generator.

Table: document_cache (idempotent creation at runtime, no Alembic).
Cache key: SHA-256 of (profile_fingerprint + offer_id + prompt_version).

Latency target: cache hit < 50ms.
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# documents/ → src/ → apps/api/  (3 levels, shallower than api/utils/ which is 4)
_DB_PATH = Path(__file__).parent.parent.parent / "data" / "db" / "offers.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS document_cache (
    key                 TEXT PRIMARY KEY,
    doc_type            TEXT NOT NULL,
    offer_id            TEXT NOT NULL,
    profile_fingerprint TEXT NOT NULL,
    prompt_version      TEXT NOT NULL,
    payload_json        TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    last_accessed_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_doc_cache_offer ON document_cache(offer_id);
CREATE INDEX IF NOT EXISTS idx_doc_cache_fp ON document_cache(profile_fingerprint);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _connect() -> sqlite3.Connection:
    """Open DB connection and ensure cache table exists (idempotent)."""
    conn = sqlite3.connect(str(_DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=3000;")
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    return conn


def make_cache_key(
    profile_fingerprint: str,
    offer_id: str,
    prompt_version: str,
) -> str:
    """
    Deterministic cache key for CV documents.

    Uses SHA-256 truncated to 40 hex chars — collision-safe for our scale.
    Same inputs always → same key.
    """
    raw = f"cv:{profile_fingerprint}:{offer_id}:{prompt_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def make_letter_cache_key(
    profile_fingerprint: str,
    offer_id: str,
    template_version: str,
) -> str:
    """
    Deterministic cache key for cover letter documents.

    Uses "letter:" prefix to guarantee no collision with CV keys.
    Same inputs always → same key.
    """
    raw = f"letter:{profile_fingerprint}:{offer_id}:{template_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def cache_get(key: str) -> Optional[dict]:
    """
    Retrieve cached document payload by key.

    Returns parsed dict or None (on miss or any error).
    Updates last_accessed_at on hit (non-blocking best-effort).
    """
    try:
        conn = _connect()
        row = conn.execute(
            "SELECT payload_json FROM document_cache WHERE key = ?",
            (key,),
        ).fetchone()

        if row:
            # Best-effort touch (don't fail if this errors)
            try:
                conn.execute(
                    "UPDATE document_cache SET last_accessed_at = ? WHERE key = ?",
                    (_utc_now(), key),
                )
                conn.commit()
            except Exception:
                pass
            conn.close()
            return json.loads(row[0])

        conn.close()
        return None

    except Exception as exc:
        logger.warning('{"event":"DOC_CACHE_GET_ERROR","error_class":"%s"}', type(exc).__name__)
        return None


def cache_set(
    key: str,
    doc_type: str,
    offer_id: str,
    profile_fingerprint: str,
    prompt_version: str,
    payload: dict,
) -> bool:
    """
    Store document payload in cache.

    Idempotent (INSERT OR REPLACE). Returns True on success.
    Never logs payload content.
    """
    try:
        conn = _connect()
        now = _utc_now()
        conn.execute(
            """
            INSERT OR REPLACE INTO document_cache
            (key, doc_type, offer_id, profile_fingerprint, prompt_version,
             payload_json, created_at, last_accessed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                doc_type,
                offer_id,
                profile_fingerprint,
                prompt_version,
                json.dumps(payload, ensure_ascii=False),
                now,
                now,
            ),
        )
        conn.commit()
        conn.close()
        return True

    except Exception as exc:
        logger.warning(
            '{"event":"DOC_CACHE_SET_ERROR","error_class":"%s"}',
            type(exc).__name__,
        )
        return False
