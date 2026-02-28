#!/usr/bin/env python3
"""
backfill_offer_skills.py - Populate fact_offer_skills from existing offers
==========================================================================

Read-only backfill job:
- Reads fact_offers payload_json (no network calls)
- Uses FT competences and fallback token extraction
- Adds ROME competences when available
- Inserts into fact_offer_skills (idempotent)

Usage:
    python3 apps/api/scripts/backfill_offer_skills.py
"""

import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

API_ROOT = Path(__file__).parent.parent
DB_PATH = API_ROOT / "data" / "db" / "offers.db"

# Add src to path for shared utilities
sys.path.insert(0, str(API_ROOT / "src"))

from api.utils.offer_skills import ensure_offer_skills_table
from api.utils.rome_link import get_offer_rome_links, get_rome_competences_for_rome_codes
from esco.extract import extract_raw_skills_from_offer
from matching.extractors import normalize_skill_label


def _utc_now() -> str:
    """Return ISO 8601 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _log(event: str, status: str, **extra: Any) -> None:
    """Emit structured JSON log to stdout."""
    payload = {
        "timestamp": _utc_now(),
        "event": event,
        "status": status,
        **extra,
    }
    print(json.dumps(payload, ensure_ascii=False))


def _extract_ft_skills(payload: Dict[str, Any]) -> List[str]:
    """Extract and normalize FT skills from payload."""
    skills: List[str] = []
    competences = payload.get("competences", [])
    if isinstance(competences, list):
        for comp in competences:
            if isinstance(comp, dict):
                label = comp.get("libelle") or comp.get("label")
                if label:
                    skills.append(str(label))
            elif isinstance(comp, str):
                skills.append(comp)

    if not skills:
        proxy = {
            "title": payload.get("intitule") or payload.get("appellationlibelle"),
            "description": payload.get("description"),
            "skills": competences,
        }
        skills = extract_raw_skills_from_offer(proxy)

    normalized = [normalize_skill_label(s) for s in skills if s]
    return sorted({s for s in normalized if s})


def _extract_generic_skills(payload: Dict[str, Any], title: str, description: str) -> List[str]:
    """Extract and normalize generic offer skills."""
    proxy = dict(payload)
    if title:
        proxy.setdefault("title", title)
    if description:
        proxy.setdefault("description", description)
    skills = extract_raw_skills_from_offer(proxy)
    normalized = [normalize_skill_label(s) for s in skills if s]
    return sorted({s for s in normalized if s})


def _insert_offer_skills(
    cursor: sqlite3.Cursor,
    offer_id: str,
    skills: List[str],
    source: str,
    timestamp: str,
) -> int:
    """Insert skills into fact_offer_skills (idempotent)."""
    inserted = 0
    for skill in skills:
        cursor.execute(
            """
            INSERT OR IGNORE INTO fact_offer_skills
            (offer_id, skill, source, confidence, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (offer_id, skill, source, None, timestamp),
        )
        if cursor.rowcount == 1:
            inserted += 1
    return inserted


def backfill_offer_skills(conn: sqlite3.Connection) -> Dict[str, int]:
    """Run backfill on an open connection. Returns stats dict."""
    ensure_offer_skills_table(conn)
    cursor = conn.cursor()

    rows = cursor.execute(
        "SELECT id, source, title, description, payload_json FROM fact_offers"
    ).fetchall()

    offer_ids = [str(row[0]) for row in rows]
    rome_links = get_offer_rome_links(conn, offer_ids)
    rome_codes = sorted({link["rome_code"] for link in rome_links.values() if link.get("rome_code")})
    rome_competences = get_rome_competences_for_rome_codes(conn, rome_codes, limit_per_rome=3)

    offers_with_skills = 0
    total_inserted = 0
    timestamp = _utc_now()

    for offer_id, source, title, description, payload_json in rows:
        # BF offers use ESCO normalization — handled by backfill_bf_skills_esco.py
        if source == "business_france":
            continue

        payload: Dict[str, Any] = {}
        if payload_json:
            try:
                payload = json.loads(payload_json)
            except json.JSONDecodeError:
                payload = {}

        rome_skills: List[str] = []
        link = rome_links.get(str(offer_id))
        if link and link.get("rome_code"):
            for comp in rome_competences.get(link["rome_code"], []):
                label = comp.get("competence_label")
                if label:
                    rome_skills.append(normalize_skill_label(label))
        rome_skills = [s for s in rome_skills if s]

        if source == "france_travail":
            payload_skills = _extract_ft_skills(payload or {})
            payload_source = "france_travail"
        else:
            payload_skills = _extract_generic_skills(payload or {}, title, description)
            payload_source = "manual"

        inserted = 0
        if rome_skills:
            inserted += _insert_offer_skills(cursor, str(offer_id), rome_skills, "rome", timestamp)
        if payload_skills:
            inserted += _insert_offer_skills(cursor, str(offer_id), payload_skills, payload_source, timestamp)

        if rome_skills or payload_skills:
            offers_with_skills += 1
        total_inserted += inserted

    conn.commit()
    return {
        "offers_scanned": len(rows),
        "offers_with_skills": offers_with_skills,
        "skills_inserted": total_inserted,
        "rome_links": len(rome_links),
    }


def main() -> int:
    start_time = time.time()
    if not DB_PATH.exists():
        _log("backfill_offer_skills", "error", error=f"DB not found at {DB_PATH}")
        return 1

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    try:
        stats = backfill_offer_skills(conn)
    finally:
        conn.close()

    duration_ms = int((time.time() - start_time) * 1000)
    _log("backfill_offer_skills", "success", duration_ms=duration_ms, **stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
