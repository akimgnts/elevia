#!/usr/bin/env python3
"""
enrich_offers_with_rome.py - Link France Travail offers to ROME métiers
========================================================================

Read-only enrichment: reads fact_offers payload_json for FT offers,
extracts romeCode, validates against dim_rome_metier, and UPSERTs
into offer_rome_link.

Does NOT modify fact_offers or any existing table.
Does NOT call any external API (pure local DB job).

Usage:
    python3 apps/api/scripts/enrich_offers_with_rome.py
"""

import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

API_ROOT = Path(__file__).parent.parent
DB_PATH = API_ROOT / "data" / "db" / "offers.db"

ROME_CODE_RE = re.compile(r"^[A-Z]\d{4}$")

# Keys to check in payload_json, in priority order (top-level)
ROME_CODE_KEYS = ("romeCode", "codeRome")
# Nested keys where value is a dict with a "code" sub-key
ROME_NESTED_KEYS = ("metierRome", "appellationRome")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS offer_rome_link (
    offer_id   TEXT PRIMARY KEY,
    rome_code  TEXT,
    rome_label TEXT,
    linked_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_offer_rome_link_rome_code ON offer_rome_link(rome_code);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def extract_rome_code(payload: dict) -> str | None:
    """Extract a valid ROME code from FT payload. Returns None if not found.

    Checks top-level string keys first (romeCode, codeRome),
    then nested dict keys (metierRome.code, appellationRome.code).
    """
    for key in ROME_CODE_KEYS:
        val = payload.get(key)
        if isinstance(val, str) and ROME_CODE_RE.match(val.strip()):
            return val.strip()
    for key in ROME_NESTED_KEYS:
        val = payload.get(key)
        if isinstance(val, dict):
            code = val.get("code", "")
            if isinstance(code, str) and ROME_CODE_RE.match(code.strip()):
                return code.strip()
    return None


# Alias for external callers (test_rome_enrichment.py)
ensure_link_table = ensure_schema


def enrich_offers(conn: sqlite3.Connection) -> dict[str, int]:
    """Run enrichment on an open connection. Returns stats dict.

    Designed to be callable from tests without going through CLI main().
    """
    import json as _json
    from datetime import datetime as _dt, timezone as _tz

    now_iso = _dt.now(_tz.utc).isoformat()
    metiers = load_rome_metiers(conn)

    rows = conn.execute(
        "SELECT id, payload_json FROM fact_offers WHERE source = 'france_travail'"
    ).fetchall()

    scanned = linked = null_linked = errors = 0
    cursor = conn.cursor()

    for row in rows:
        offer_id = row["id"]
        scanned += 1

        try:
            payload = _json.loads(row["payload_json"])
        except (_json.JSONDecodeError, TypeError):
            errors += 1
            cursor.execute(
                """INSERT INTO offer_rome_link (offer_id, rome_code, rome_label, linked_at)
                   VALUES (?, NULL, NULL, ?)
                   ON CONFLICT(offer_id) DO UPDATE SET
                       rome_code=excluded.rome_code, rome_label=excluded.rome_label, linked_at=excluded.linked_at""",
                (offer_id, now_iso),
            )
            continue

        code = extract_rome_code(payload)

        if code:
            label = metiers.get(code) if metiers else None
            if label is None:
                label = (payload.get("romeLibelle") or "").strip() or None
            cursor.execute(
                """INSERT INTO offer_rome_link (offer_id, rome_code, rome_label, linked_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(offer_id) DO UPDATE SET
                       rome_code=excluded.rome_code, rome_label=excluded.rome_label, linked_at=excluded.linked_at""",
                (offer_id, code, label, now_iso),
            )
            linked += 1
        else:
            cursor.execute(
                """INSERT INTO offer_rome_link (offer_id, rome_code, rome_label, linked_at)
                   VALUES (?, NULL, NULL, ?)
                   ON CONFLICT(offer_id) DO UPDATE SET
                       rome_code=excluded.rome_code, rome_label=excluded.rome_label, linked_at=excluded.linked_at""",
                (offer_id, now_iso),
            )
            null_linked += 1

    conn.commit()
    return {"scanned": scanned, "linked": linked, "null_linked": null_linked, "errors": errors}


def load_rome_metiers(conn: sqlite3.Connection) -> dict[str, str]:
    """Load all ROME codes → labels from dim_rome_metier."""
    try:
        rows = conn.execute("SELECT rome_code, rome_label FROM dim_rome_metier").fetchall()
        return {r[0]: r[1] for r in rows}
    except sqlite3.OperationalError:
        # Table doesn't exist yet (ROME ingestion not run)
        return {}


def run_enrichment() -> None:
    print("=" * 60)
    print("ELEVIA — OFFER ↔ ROME LINK ENRICHMENT")
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    print(f"Started at: {now_iso}")
    print("=" * 60)

    if not DB_PATH.exists():
        print(f"[ERROR] Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_schema(conn)

    # Load ROME lookup
    metiers = load_rome_metiers(conn)
    print(f"[INFO] Loaded {len(metiers)} ROME métiers from dim_rome_metier")
    if not metiers:
        print("[WARN] dim_rome_metier is empty — codes won't be validated against it")
        print("[WARN] All extracted codes will still be linked (label from payload)")

    # Load FT offers
    rows = conn.execute(
        "SELECT id, payload_json FROM fact_offers WHERE source = 'france_travail'"
    ).fetchall()
    print(f"[INFO] Found {len(rows)} France Travail offers to process")

    scanned = 0
    linked = 0
    null_linked = 0
    errors = 0

    cursor = conn.cursor()
    for row in rows:
        offer_id = row["id"]
        scanned += 1

        try:
            payload = json.loads(row["payload_json"])
        except (json.JSONDecodeError, TypeError):
            errors += 1
            cursor.execute(
                """INSERT INTO offer_rome_link (offer_id, rome_code, rome_label, linked_at)
                   VALUES (?, NULL, NULL, ?)
                   ON CONFLICT(offer_id) DO UPDATE SET
                       rome_code = excluded.rome_code,
                       rome_label = excluded.rome_label,
                       linked_at = excluded.linked_at""",
                (offer_id, now_iso),
            )
            continue

        code = extract_rome_code(payload)

        if code and metiers:
            # Validate against dim_rome_metier
            if code in metiers:
                label = metiers[code]
                cursor.execute(
                    """INSERT INTO offer_rome_link (offer_id, rome_code, rome_label, linked_at)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(offer_id) DO UPDATE SET
                           rome_code = excluded.rome_code,
                           rome_label = excluded.rome_label,
                           linked_at = excluded.linked_at""",
                    (offer_id, code, label, now_iso),
                )
                linked += 1
            else:
                # Code found but not in dim_rome_metier — use payload label as fallback
                fallback_label = (payload.get("romeLibelle") or "").strip() or None
                cursor.execute(
                    """INSERT INTO offer_rome_link (offer_id, rome_code, rome_label, linked_at)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(offer_id) DO UPDATE SET
                           rome_code = excluded.rome_code,
                           rome_label = excluded.rome_label,
                           linked_at = excluded.linked_at""",
                    (offer_id, code, fallback_label, now_iso),
                )
                linked += 1
        elif code and not metiers:
            # No dim_rome_metier loaded — use payload label
            fallback_label = (payload.get("romeLibelle") or "").strip() or None
            cursor.execute(
                """INSERT INTO offer_rome_link (offer_id, rome_code, rome_label, linked_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(offer_id) DO UPDATE SET
                       rome_code = excluded.rome_code,
                       rome_label = excluded.rome_label,
                       linked_at = excluded.linked_at""",
                (offer_id, code, fallback_label, now_iso),
            )
            linked += 1
        else:
            # No rome code found
            cursor.execute(
                """INSERT INTO offer_rome_link (offer_id, rome_code, rome_label, linked_at)
                   VALUES (?, NULL, NULL, ?)
                   ON CONFLICT(offer_id) DO UPDATE SET
                       rome_code = excluded.rome_code,
                       rome_label = excluded.rome_label,
                       linked_at = excluded.linked_at""",
                (offer_id, now_iso),
            )
            null_linked += 1

    conn.commit()
    conn.close()

    print("\n" + "=" * 60)
    print("ENRICHMENT SUMMARY")
    print("=" * 60)
    print(f"  Scanned:     {scanned}")
    print(f"  Linked:      {linked}")
    print(f"  Null-linked: {null_linked}")
    print(f"  Errors:      {errors}")
    print(f"  DB:          {DB_PATH}")

    log_line = {
        "timestamp": now_iso,
        "job": "offer_rome_enrichment",
        "scanned": scanned,
        "linked": linked,
        "null_linked": null_linked,
        "errors": errors,
    }
    print(f"\n[LOG] {json.dumps(log_line)}")


if __name__ == "__main__":
    run_enrichment()
