#!/usr/bin/env python3
"""sync_v3_metier_to_sqlite — Sync V3 IA canonical skills from PostgreSQL to SQLite.

Pipeline:
1. Read PostgreSQL.offer_skills with enrichment_version IN ('offer_skills_v3_metier', 'offer_skills_v3_fallback')
2. Deduplicate by (offer_id, canonical_id)
3. Write to SQLite.fact_offer_skills with skill_uri = canonical_id (metier:*)
4. Idempotent: skip existing (offer_id, skill) pairs
5. Dry-run capable

Usage:
    export DATABASE_URL=postgresql://...
    python3 apps/api/scripts/sync_v3_metier_to_sqlite.py [--dry-run] [--limit 50]

Requirements:
    - DATABASE_URL must point to PostgreSQL
    - psycopg3 installed
    - SQLite offers.db at apps/api/data/db/offers.db
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

API_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = API_ROOT / "data" / "db" / "offers.db"

# Load .env from project root and apps/api/
load_dotenv(API_ROOT / ".env")
load_dotenv(API_ROOT.parent.parent / ".env")

sys.path.insert(0, str(API_ROOT / "src"))

from api.utils.offer_skills import ensure_offer_skills_table


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _log(event: str, status: str, **extra: Any) -> None:
    payload = {
        "timestamp": _utc_now(),
        "event": event,
        "status": status,
        **extra,
    }
    print(json.dumps(payload, ensure_ascii=False))


def fetch_v3_skills_from_postgres(
    pg_conn,
    *,
    enrichment_versions: tuple[str, ...] = ("offer_skills_v3_metier", "offer_skills_v3_fallback"),
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch V3 canonical skills from PostgreSQL.

    Returns list of dicts: {offer_id, external_id, source, canonical_id, label, importance_level, confidence}
    """
    versioning_filter = ", ".join(f"'{v}'" for v in enrichment_versions)

    query = f"""
    SELECT DISTINCT
        os.offer_id,
        os.external_id,
        os.source,
        os.canonical_id,
        os.label,
        os.importance_level,
        os.confidence,
        os.enrichment_version
    FROM offer_skills os
    WHERE os.enrichment_version IN ({versioning_filter})
      AND os.canonical_id LIKE 'metier:%'
    ORDER BY os.offer_id, os.canonical_id
    """

    if limit:
        query += f" LIMIT {int(limit)}"

    with pg_conn.cursor() as cursor:
        cursor.execute(query)
        rows = cursor.fetchall()

    skills = [
        {
            "offer_id": row[0],
            "external_id": row[1],
            "source": row[2],
            "canonical_id": row[3],
            "label": row[4],
            "importance_level": row[5],
            "confidence": row[6],
            "enrichment_version": row[7],
        }
        for row in rows
    ]
    return skills


def sync_to_sqlite(
    sqlite_conn: sqlite3.Connection,
    pg_skills: list[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Sync V3 skills from PostgreSQL to SQLite fact_offer_skills.

    Returns stats dict: {inserted, skipped, errors}
    """
    ensure_offer_skills_table(sqlite_conn)
    cursor = sqlite_conn.cursor()

    stats = {
        "total_processed": len(pg_skills),
        "inserted": 0,
        "skipped_existing": 0,
        "errors": 0,
        "sample_inserted": [],
        "offers_affected": set(),
    }

    timestamp = _utc_now()

    # Deduplicate: keep first occurrence of (offer_id, canonical_id)
    seen = set()
    dedup_skills = []
    for skill in pg_skills:
        key = (skill["offer_id"], skill["canonical_id"])
        if key not in seen:
            seen.add(key)
            dedup_skills.append(skill)

    stats["deduplicated_from"] = len(pg_skills)
    stats["deduplicated_to"] = len(dedup_skills)

    for skill in dedup_skills:
        offer_id = skill["offer_id"]
        canonical_id = skill["canonical_id"]
        label = skill["label"]

        # Check if already exists
        cursor.execute(
            """
            SELECT 1 FROM fact_offer_skills
            WHERE offer_id = ? AND skill = ? AND skill_uri = ?
            """,
            (str(offer_id), label, canonical_id),
        )

        if cursor.fetchone():
            stats["skipped_existing"] += 1
            continue

        try:
            if not dry_run:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO fact_offer_skills
                    (offer_id, skill, skill_uri, source, confidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(offer_id),
                        label,
                        canonical_id,
                        "manual",  # source=manual (valid constraint); skill_uri=metier:* distinguishes from garbage
                        skill.get("confidence"),
                        timestamp,
                    ),
                )
                if cursor.rowcount == 1:
                    stats["inserted"] += 1
                    stats["offers_affected"].add(str(offer_id))
                    if len(stats["sample_inserted"]) < 5:
                        stats["sample_inserted"].append(
                            {
                                "offer_id": str(offer_id),
                                "skill": label,
                                "skill_uri": canonical_id,
                                "importance": skill.get("importance_level"),
                            }
                        )
            else:
                # Dry-run: just count
                stats["inserted"] += 1
                stats["offers_affected"].add(str(offer_id))

        except Exception as e:
            stats["errors"] += 1
            _log("sync_error", "error", offer_id=str(offer_id), skill=label, error=str(e))

    if not dry_run:
        sqlite_conn.commit()

    stats["offers_affected"] = len(stats["offers_affected"])
    return stats


def get_quality_metrics(
    sqlite_conn: sqlite3.Connection,
    *, before: bool = False
) -> dict[str, Any]:
    """Get quality metrics from fact_offer_skills."""
    cursor = sqlite_conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM fact_offer_skills")
    total_rows = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT offer_id) FROM fact_offer_skills")
    distinct_offers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM fact_offer_skills WHERE skill_uri LIKE 'metier:%'")
    metier_rows = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM fact_offer_skills WHERE skill_uri IS NULL")
    null_uri_rows = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT source) FROM fact_offer_skills")
    sources_count = cursor.fetchone()[0]

    cursor.execute("SELECT source, COUNT(*) FROM fact_offer_skills GROUP BY source ORDER BY COUNT(*) DESC")
    source_breakdown = {row[0]: row[1] for row in cursor.fetchall()}

    metric_type = "before" if before else "after"
    return {
        f"{metric_type}_total_rows": total_rows,
        f"{metric_type}_distinct_offers": distinct_offers,
        f"{metric_type}_metier_rows": metier_rows,
        f"{metric_type}_metier_pct": round(100.0 * metier_rows / total_rows, 2) if total_rows > 0 else 0,
        f"{metric_type}_null_uri_rows": null_uri_rows,
        f"{metric_type}_garbage_pct": round(100.0 * null_uri_rows / total_rows, 2) if total_rows > 0 else 0,
        f"{metric_type}_sources": source_breakdown,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync V3 IA canonical skills to SQLite")
    parser.add_argument("--dry-run", action="store_true", help="Test without writing")
    parser.add_argument("--limit", type=int, default=None, help="Limit V3 skills to sync")
    args = parser.parse_args()

    # PostgreSQL connection
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        print("Usage: DATABASE_URL=postgresql://... python3 sync_v3_metier_to_sqlite.py", file=sys.stderr)
        return 2

    try:
        import psycopg
    except ImportError:
        print("ERROR: psycopg not installed. Run: pip install psycopg", file=sys.stderr)
        return 2

    # SQLite connection
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found", file=sys.stderr)
        return 1

    sqlite_conn = sqlite3.connect(str(DB_PATH), timeout=10)
    _log("sync_start", "info", dry_run=args.dry_run, limit=args.limit)

    try:
        # Get before metrics
        before_metrics = get_quality_metrics(sqlite_conn, before=True)
        _log("quality_before", "info", **before_metrics)

        # Connect to PostgreSQL and fetch V3 skills
        print("[PG] Connecting to PostgreSQL...", file=sys.stderr)
        pg_conn = psycopg.connect(database_url, connect_timeout=15)

        print("[PG] Fetching V3 skills...", file=sys.stderr)
        v3_skills = fetch_v3_skills_from_postgres(pg_conn, limit=args.limit)
        print(f"[PG] Found {len(v3_skills)} V3 skills", file=sys.stderr)

        pg_conn.close()

        # Sync to SQLite
        print("[SQLite] Syncing to fact_offer_skills...", file=sys.stderr)
        stats = sync_to_sqlite(sqlite_conn, v3_skills, dry_run=args.dry_run)

        _log("sync_stats", "info", **stats)

        # Get after metrics
        after_metrics = get_quality_metrics(sqlite_conn, before=False)
        _log("quality_after", "info", **after_metrics)

        # Summary
        print("\n" + "=" * 70)
        print("SYNC SUMMARY")
        print("=" * 70)
        print(f"Dry-run: {args.dry_run}")
        print(f"V3 skills from PostgreSQL: {len(v3_skills)}")
        print(f"Deduplicated: {stats['deduplicated_to']}")
        print(f"Inserted: {stats['inserted']}")
        print(f"Skipped (existing): {stats['skipped_existing']}")
        print(f"Errors: {stats['errors']}")
        print(f"Offers affected: {stats['offers_affected']}")

        if stats["sample_inserted"]:
            print(f"\nSample inserted (first {len(stats['sample_inserted'])}):")
            for sample in stats["sample_inserted"]:
                print(f"  {sample['offer_id']}: {sample['skill']} → {sample['skill_uri']}")

        print(f"\nBefore: {before_metrics['before_total_rows']} total, {before_metrics['before_metier_pct']}% metier:*")
        print(f"After:  {after_metrics['after_total_rows']} total, {after_metrics['after_metier_pct']}% metier:*")
        print(f"Garbage ratio before: {before_metrics['before_garbage_pct']}%")
        print(f"Garbage ratio after:  {after_metrics['after_garbage_pct']}%")
        print("=" * 70)

        sqlite_conn.close()
        return 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sqlite_conn.rollback()
        sqlite_conn.close()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
