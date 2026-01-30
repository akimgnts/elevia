#!/usr/bin/env python3
"""
enrich_offers_with_rome.py - Read-only ROME enrichment for France Travail offers.

Creates and populates offer_rome_link table by extracting ROME codes
from fact_offers.payload_json and linking to dim_rome_metier.

This script is additive: it does NOT modify fact_offers.
"""

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

API_ROOT = Path(__file__).parent.parent
DATA_DIR = API_ROOT / "data"
DB_PATH = DATA_DIR / "db" / "offers.db"

ROME_CODE_PATTERN = re.compile(r"^[A-Z]\\d{4}$")

# Explicit paths to check first (deterministic).
ROME_CODE_PATHS: Tuple[Tuple[str, ...], ...] = (
    ("romeCode",),
    ("codeRome",),
    ("code_rome",),
    ("rome_code",),
    ("code_metier",),
    ("metierRome", "code"),
    ("metierRome", "codeRome"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iter_dict_items(obj: Any) -> Iterable[Tuple[str, Any]]:
    if isinstance(obj, dict):
        return obj.items()
    return []


def _get_by_path(payload: Dict[str, Any], path: Tuple[str, ...]) -> Optional[Any]:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        if key not in current:
            return None
        current = current[key]
    return current


def _is_valid_rome_code(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    code = value.strip().upper()
    if ROME_CODE_PATTERN.match(code):
        return code
    return None


def extract_rome_code(payload: Dict[str, Any]) -> Optional[str]:
    """
    Extract the first valid ROME code from payload_json.
    Deterministic order:
    1) Explicit known paths
    2) Any key containing 'rome' with value matching format
    """
    if not isinstance(payload, dict):
        return None

    # 1) Explicit paths
    for path in ROME_CODE_PATHS:
        value = _get_by_path(payload, path)
        code = _is_valid_rome_code(value)
        if code:
            return code

    # 2) Recursive search for keys containing "rome"
    stack = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in _iter_dict_items(current):
                if isinstance(value, (dict, list)):
                    stack.append(value)
                if isinstance(key, str) and "rome" in key.lower():
                    code = _is_valid_rome_code(value)
                    if code:
                        return code
        elif isinstance(current, list):
            for item in current:
                if isinstance(item, (dict, list)):
                    stack.append(item)

    return None


def ensure_link_table(conn: sqlite3.Connection) -> None:
    """Create offer_rome_link table if it doesn't exist."""
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS offer_rome_link (
            offer_id   TEXT PRIMARY KEY,
            rome_code  TEXT NULL,
            rome_label TEXT NULL,
            linked_at  TEXT NOT NULL,
            FOREIGN KEY (offer_id) REFERENCES fact_offers(id),
            FOREIGN KEY (rome_code) REFERENCES dim_rome_metier(rome_code)
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_offer_rome_code ON offer_rome_link(rome_code);")
    conn.commit()


def _lookup_rome_label(conn: sqlite3.Connection, rome_code: str) -> Optional[str]:
    row = conn.execute(
        "SELECT rome_label FROM dim_rome_metier WHERE rome_code = ?",
        (rome_code,),
    ).fetchone()
    return row[0] if row else None


def enrich_offers(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Populate offer_rome_link for France Travail offers.
    Returns counters for logging.
    """
    conn.execute("PRAGMA foreign_keys = ON;")
    ensure_link_table(conn)

    rows = conn.execute(
        "SELECT id, payload_json FROM fact_offers WHERE source = 'france_travail'"
    ).fetchall()

    scanned = 0
    linked = 0
    skipped = 0
    now = _utc_now()

    for offer_id, payload_json in rows:
        scanned += 1
        rome_code = None
        rome_label = None

        try:
            payload = json.loads(payload_json) if payload_json else {}
        except json.JSONDecodeError:
            payload = {}

        candidate = extract_rome_code(payload)
        if candidate:
            label = _lookup_rome_label(conn, candidate)
            if label:
                rome_code = candidate
                rome_label = label
                linked += 1
            else:
                skipped += 1
        else:
            skipped += 1

        conn.execute(
            """
            INSERT INTO offer_rome_link (offer_id, rome_code, rome_label, linked_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(offer_id) DO UPDATE SET
                rome_code = excluded.rome_code,
                rome_label = excluded.rome_label,
                linked_at = excluded.linked_at
            """,
            (offer_id, rome_code, rome_label, now),
        )

    conn.commit()

    return {
        "scanned": scanned,
        "linked": linked,
        "skipped": skipped,
    }


def main() -> int:
    if not DB_PATH.exists():
        print(f"[ERROR] Database not found at {DB_PATH}")
        return 1

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    try:
        stats = enrich_offers(conn)
    finally:
        conn.close()

    print(
        f"[ROME_LINK] scanned={stats['scanned']} linked={stats['linked']} skipped={stats['skipped']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
