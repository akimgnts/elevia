#!/usr/bin/env python3
"""
backfill_bf_skills_esco.py - BF ESCO backfill + is_vie migration
================================================================
Sprint BMAD — Matching Opérationnel (PATCH 1 + 2)

Two-phase idempotent backfill for Business France Azure offers:

Phase 1 — migrate_bf_is_vie
  Update payload_json to inject is_vie=True for offers with missionType="VIE".
  Uses Python-level JSON read/write (not SQL json_set) to preserve bool type.
  Required because _attach_payload_fields() checks isinstance(payload["is_vie"], bool).

Phase 2 — backfill_bf_esco_skills
  Rebuild fact_offer_skills for BF offers using ESCO normalization:
  - Extracts tokens from title + description (NO pre-loaded noisy tokens)
  - Maps via map_skill() → ESCO URIs
  - Stores ONLY ESCO-mapped labels (source='esco'), capped at MAX_SKILLS_PER_OFFER
  - Idempotent: deletes existing BF skills before re-inserting

URI scoring context:
  ELEVIA_SCORE_USE_URIS=1 (default) → denominator = len(skills_uri)
  With noisy tokens (avg 149/offer), too many wrong-domain URIs inflate denominator
  → skills_score < 10%. Fix: clean ESCO skills → small denominator → viable score.

Usage:
    python3 apps/api/scripts/backfill_bf_skills_esco.py

Constraints:
  - DB-only (no network)
  - Zero changes to scoring core
  - Idempotent (safe to re-run)
"""

import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

API_ROOT = Path(__file__).parent.parent
DB_PATH = API_ROOT / "data" / "db" / "offers.db"

# Add src to path for shared utilities
sys.path.insert(0, str(API_ROOT / "src"))

from api.utils.offer_skills import ensure_offer_skills_table
from api.utils.inbox_catalog import _normalize_offer_skills_via_esco

# Max ESCO skills to store per offer (avoid denominator inflation)
MAX_SKILLS_PER_OFFER = 25


# ==============================================================================
# STRUCTURED LOGGING
# ==============================================================================

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _log(event: str, status: str, **extra: Any) -> None:
    """Emit structured JSON log to stdout. No payload dump."""
    payload = {
        "timestamp": _utc_now(),
        "event": event,
        "status": status,
        **extra,
    }
    print(json.dumps(payload, ensure_ascii=False))


# ==============================================================================
# PHASE 1 — is_vie MIGRATION
# ==============================================================================

def migrate_bf_is_vie(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Inject is_vie=True into payload_json for BF offers with missionType="VIE".

    Python-level JSON update (not SQL) ensures the value is a Python bool True,
    which serializes to JSON 'true'. This is required by _attach_payload_fields()
    which checks isinstance(payload.get("is_vie"), bool).

    Idempotent: skips offers already having is_vie=True.
    """
    cursor = conn.cursor()
    rows = cursor.execute(
        "SELECT id, payload_json FROM fact_offers WHERE source='business_france'"
    ).fetchall()

    updated = 0
    skipped_already_ok = 0
    skipped_no_payload = 0

    for offer_id, payload_json in rows:
        if not payload_json:
            skipped_no_payload += 1
            continue

        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError:
            skipped_no_payload += 1
            continue

        # Check current state
        if payload.get("is_vie") is True:
            skipped_already_ok += 1
            continue

        # Inject is_vie from missionType (deterministic)
        mission_type = str(payload.get("missionType") or "").upper()
        payload["is_vie"] = (mission_type == "VIE")

        new_payload_json = json.dumps(payload, ensure_ascii=False)
        cursor.execute(
            "UPDATE fact_offers SET payload_json=? WHERE id=?",
            (new_payload_json, offer_id),
        )
        updated += 1

    conn.commit()

    return {
        "bf_offers_scanned": len(rows),
        "is_vie_updated": updated,
        "is_vie_already_ok": skipped_already_ok,
        "is_vie_skipped_no_payload": skipped_no_payload,
    }


# ==============================================================================
# PHASE 2 — ESCO SKILLS BACKFILL
# ==============================================================================

def _extract_esco_labels(offer_dict: Dict[str, Any]) -> List[str]:
    """
    Extract ESCO-mapped labels only (no unmapped raw tokens).

    Builds a clean offer dict without pre-loaded noisy skills, then runs
    _normalize_offer_skills_via_esco. Returns only items that mapped to ESCO
    (from skills_display), capped at MAX_SKILLS_PER_OFFER.

    The denominator in URI scoring = len(skills_uri). Keeping this small and
    relevant ensures skills_score can reach the 71.4% threshold needed for
    total_score >= 80.
    """
    # Build clean offer dict — no "skills" key to prevent step 1 noise injection
    # Only title + description → step 2 extracts tokens, maps to ESCO
    clean_dict: Dict[str, Any] = {}
    if offer_dict.get("title"):
        clean_dict["title"] = offer_dict["title"]
    if offer_dict.get("description"):
        clean_dict["description"] = offer_dict["description"]
    # id for debug logs
    if offer_dict.get("id"):
        clean_dict["id"] = offer_dict["id"]

    try:
        normalized = _normalize_offer_skills_via_esco(clean_dict)
    except Exception:
        return []

    # Use skills_display to extract only ESCO-mapped labels
    # skills_display = [{uri, label, source}, ...]
    skills_display = normalized.get("skills_display") or []
    esco_labels: List[str] = []
    seen: set = set()

    for item in skills_display:
        label = item.get("label") or item.get("uri") or ""
        label = str(label).strip().lower()
        if label and label not in seen:
            seen.add(label)
            esco_labels.append(label)
        if len(esco_labels) >= MAX_SKILLS_PER_OFFER:
            break

    return esco_labels


def _replace_bf_offer_skills(
    cursor: sqlite3.Cursor,
    offer_id: str,
    skills: List[str],
    timestamp: str,
) -> int:
    """
    Delete existing skills for this BF offer and insert clean ESCO labels.

    Idempotent: DELETE + INSERT OR IGNORE means running twice = same result.
    Source='esco' is defined in offer_skills.SCHEMA_SQL CHECK constraint.
    """
    # Delete existing skills for this offer (all sources)
    cursor.execute(
        "DELETE FROM fact_offer_skills WHERE offer_id=?",
        (offer_id,),
    )

    inserted = 0
    for skill in skills:
        cursor.execute(
            """
            INSERT OR IGNORE INTO fact_offer_skills
            (offer_id, skill, source, confidence, created_at)
            VALUES (?, ?, 'esco', NULL, ?)
            """,
            (offer_id, skill, timestamp),
        )
        if cursor.rowcount == 1:
            inserted += 1

    return inserted


def backfill_bf_esco_skills(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Rebuild fact_offer_skills for all BF Azure offers using ESCO normalization.

    Process per offer:
    1. Build clean dict (title + description only, no pre-loaded noisy skills)
    2. Run _normalize_offer_skills_via_esco → get skills_display (ESCO-mapped only)
    3. Delete existing skills → insert clean ESCO labels (source='esco')

    Returns stats dict with OBS evidence.
    """
    ensure_offer_skills_table(conn)
    cursor = conn.cursor()

    rows = cursor.execute(
        "SELECT id, title, description FROM fact_offers WHERE source='business_france'"
    ).fetchall()

    timestamp = _utc_now()
    offers_processed = 0
    offers_with_skills = 0
    offers_zero_skills = 0
    total_skills_inserted = 0
    skill_counts: List[int] = []

    for offer_id, title, description in rows:
        offer_dict = {
            "id": str(offer_id),
            "title": title or "",
            "description": description or "",
        }

        esco_labels = _extract_esco_labels(offer_dict)
        inserted = _replace_bf_offer_skills(cursor, str(offer_id), esco_labels, timestamp)

        offers_processed += 1
        total_skills_inserted += inserted
        skill_counts.append(inserted)

        if inserted > 0:
            offers_with_skills += 1
        else:
            offers_zero_skills += 1

    conn.commit()

    avg_skills = round(sum(skill_counts) / len(skill_counts), 2) if skill_counts else 0.0
    zero_skill_ratio = round(offers_zero_skills / offers_processed, 3) if offers_processed else 0.0

    return {
        "bf_offers_processed": offers_processed,
        "offers_with_skills": offers_with_skills,
        "offers_zero_skills": offers_zero_skills,
        "total_skills_inserted": total_skills_inserted,
        "avg_skills_per_offer": avg_skills,
        "zero_skill_ratio": zero_skill_ratio,
    }


# ==============================================================================
# DB EVIDENCE QUERIES (OBS)
# ==============================================================================

def query_is_vie_evidence(conn: sqlite3.Connection) -> Dict[str, Any]:
    """SQL evidence: % BF offers with is_vie=true in payload_json."""
    total = conn.execute(
        "SELECT COUNT(*) FROM fact_offers WHERE source='business_france'"
    ).fetchone()[0]

    # json_extract returns 1 for JSON true (SQLite boolean representation)
    with_vie = conn.execute(
        """
        SELECT COUNT(*) FROM fact_offers
        WHERE source='business_france'
        AND json_extract(payload_json,'$.is_vie') = 1
        """
    ).fetchone()[0]

    ratio = round(with_vie / total, 3) if total else 0.0
    return {
        "bf_total": total,
        "bf_is_vie_true": with_vie,
        "is_vie_true_ratio": ratio,
    }


def query_skills_evidence(conn: sqlite3.Connection) -> Dict[str, Any]:
    """SQL evidence: avg skills per BF offer, zero-skill ratio."""
    result = conn.execute(
        """
        SELECT
            ROUND(AVG(cnt), 2) as avg_skills,
            SUM(CASE WHEN cnt = 0 THEN 1 ELSE 0 END) as zero_skill_count,
            COUNT(*) as bf_offers
        FROM (
            SELECT fo.id as offer_id, COUNT(fos.skill) as cnt
            FROM fact_offers fo
            LEFT JOIN fact_offer_skills fos ON fo.id = fos.offer_id
            WHERE fo.source = 'business_france'
            GROUP BY fo.id
        )
        """
    ).fetchone()

    avg_skills = result[0] or 0.0
    zero_count = result[1] or 0
    bf_offers = result[2] or 0
    zero_ratio = round(zero_count / bf_offers, 3) if bf_offers else 0.0

    return {
        "avg_skills_per_offer": avg_skills,
        "zero_skill_count": zero_count,
        "bf_offers": bf_offers,
        "zero_skill_ratio": zero_ratio,
    }


# ==============================================================================
# MAIN
# ==============================================================================

def main() -> int:
    start_time = time.time()

    _log("backfill_bf_skills_esco", "start", db_path=str(DB_PATH))

    if not DB_PATH.exists():
        _log("backfill_bf_skills_esco", "error", error=f"DB not found at {DB_PATH}")
        return 1

    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")

    try:
        # Phase 1 — is_vie migration
        _log("phase1_is_vie", "start")
        p1_stats = migrate_bf_is_vie(conn)
        _log("phase1_is_vie", "success", **p1_stats)

        # Phase 2 — ESCO skills backfill
        _log("phase2_esco_skills", "start")
        p2_stats = backfill_bf_esco_skills(conn)
        _log("phase2_esco_skills", "success", **p2_stats)

        # OBS evidence
        vie_evidence = query_is_vie_evidence(conn)
        skills_evidence = query_skills_evidence(conn)
        _log("obs_evidence", "ok", **vie_evidence, **skills_evidence)

    except Exception as e:
        _log("backfill_bf_skills_esco", "error", error=str(e))
        return 1
    finally:
        conn.close()

    duration_ms = int((time.time() - start_time) * 1000)
    _log("backfill_bf_skills_esco", "done", duration_ms=duration_ms)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
