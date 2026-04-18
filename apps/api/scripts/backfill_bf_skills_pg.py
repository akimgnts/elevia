#!/usr/bin/env python3
"""
backfill_bf_skills_pg.py - Extract and store Business France skills in PostgreSQL.

Reads clean_offers (PostgreSQL), extracts skills via ESCO offline pipeline,
writes into offer_skills (PostgreSQL). Idempotent.

Usage:
    python3 apps/api/scripts/backfill_bf_skills_pg.py [--limit N] [--dry-run] [--debug]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

API_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(API_ROOT / "src"))

from esco.extract import extract_raw_skills_from_offer
from esco.mapper import map_skill


# ============================================================================
# Schema
# ============================================================================

CREATE_OFFER_SKILLS_SQL = """
CREATE TABLE IF NOT EXISTS offer_skills (
    offer_id     TEXT        NOT NULL,
    source       TEXT        NOT NULL,
    skill        TEXT        NOT NULL,
    skill_uri    TEXT,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (offer_id, source, skill)
);
"""

CREATE_OFFER_SKILLS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_offer_skills_offer_id ON offer_skills(offer_id);",
    "CREATE INDEX IF NOT EXISTS idx_offer_skills_offer_id_uri ON offer_skills(offer_id, skill_uri);",
]

UPSERT_SKILL_SQL = """
INSERT INTO offer_skills (offer_id, source, skill, skill_uri, extracted_at)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (offer_id, source, skill)
DO UPDATE SET
    skill_uri    = EXCLUDED.skill_uri,
    extracted_at = EXCLUDED.extracted_at;
"""


# ============================================================================
# Helpers
# ============================================================================

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _log(event: str, status: str, **extra: Any) -> None:
    print(json.dumps({"timestamp": _utc_now(), "event": event, "status": status, **extra}, ensure_ascii=False))


def _ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(CREATE_OFFER_SKILLS_SQL)
        for idx in CREATE_OFFER_SKILLS_INDEXES:
            cur.execute(idx)
    conn.commit()


def _extract_and_map(offer: Dict[str, Any]) -> List[Tuple[str, Optional[str]]]:
    """
    Extract skill candidates from offer fields, map to ESCO.
    Returns list of (label, uri|None). Deduplicates by URI for mapped skills.
    Extraction is fully offline — no network calls.
    """
    raw_labels = extract_raw_skills_from_offer(offer)
    results: List[Tuple[str, Optional[str]]] = []
    seen_uris: set = set()

    for label in raw_labels:
        result = map_skill(label, enable_fuzzy=False)
        if result and result.get("esco_id"):
            uri = str(result["esco_id"])
            if uri not in seen_uris:
                results.append((result.get("label", label), uri))
                seen_uris.add(uri)
        else:
            results.append((label, None))

    return results


# ============================================================================
# Core backfill
# ============================================================================

def run_backfill(
    conn,
    *,
    limit: int = 0,
    dry_run: bool = False,
    debug: bool = False,
) -> Dict[str, int]:
    _ensure_table(conn)

    with conn.cursor() as cur:
        if limit > 0:
            cur.execute(
                "SELECT external_id, title, description, mission_profile FROM clean_offers WHERE source = %s ORDER BY external_id LIMIT %s",
                ("business_france", limit),
            )
        else:
            cur.execute(
                "SELECT external_id, title, description, mission_profile FROM clean_offers WHERE source = %s ORDER BY external_id",
                ("business_france",),
            )
        rows = cur.fetchall()

    offers_read = len(rows)
    offers_enriched = 0
    skills_written = 0
    timestamp = _utc_now()

    for external_id, title, description, mission_profile in rows:
        # Prioritize mission_profile (structured requirements) over full description.
        # Fall back to description only when mission_profile is absent.
        extraction_text = mission_profile or description or ""
        skills = _extract_and_map({"title": title or "", "description": extraction_text})

        if not skills:
            if debug:
                _log("bf_skill_extract", "debug", offer_id=external_id, skills_found=0)
            continue

        offers_enriched += 1

        if not dry_run:
            with conn.cursor() as cur:
                for label, uri in skills:
                    cur.execute(UPSERT_SKILL_SQL, (external_id, "business_france", label, uri, timestamp))
            skills_written += len(skills)
        else:
            skills_written += len(skills)

        if debug:
            _log(
                "bf_skill_extract",
                "debug",
                offer_id=external_id,
                skills_found=len(skills),
                mapped=sum(1 for _, u in skills if u),
                sample=[(l, u) for l, u in skills[:3]],
            )

    if not dry_run:
        conn.commit()

    return {
        "offers_read": offers_read,
        "offers_enriched": offers_enriched,
        "skills_written": skills_written,
    }


# ============================================================================
# Entry point
# ============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill BF skills into PostgreSQL offer_skills")
    parser.add_argument("--limit", type=int, default=0, help="Max offers to process (0 = all)")
    parser.add_argument("--dry-run", action="store_true", help="Extract and log without writing")
    parser.add_argument("--debug", action="store_true", help="Per-offer debug logs")
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        _log("backfill_bf_skills_pg", "error", error="DATABASE_URL not set")
        return 1

    start_time = time.time()

    try:
        import psycopg
        conn = psycopg.connect(database_url)
    except Exception as e:
        _log("backfill_bf_skills_pg", "error", error=f"PostgreSQL connection failed: {e}")
        return 1

    try:
        stats = run_backfill(conn, limit=args.limit, dry_run=args.dry_run, debug=args.debug)
    except Exception as e:
        _log("backfill_bf_skills_pg", "error", error=str(e))
        conn.close()
        return 1
    finally:
        conn.close()

    duration_ms = int((time.time() - start_time) * 1000)
    status = "dry_run" if args.dry_run else "success"
    _log("backfill_bf_skills_pg", status, duration_ms=duration_ms, **stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
