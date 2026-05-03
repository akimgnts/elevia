#!/usr/bin/env python3
"""precheck_v3_sync — Verify PostgreSQL connectivity and V3 row count before sync."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

API_ROOT = Path(__file__).resolve().parent.parent

# Load .env from project root and apps/api/
load_dotenv(API_ROOT / ".env")
load_dotenv(API_ROOT.parent.parent / ".env")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    print("=" * 80)
    print("PRE-CHECK: V3 IA SYNC PREREQUISITES")
    print("=" * 80)
    print(f"Timestamp: {_utc_now()}\n")

    # Step 1: Verify DATABASE_URL
    print("[1/4] Checking DATABASE_URL...")
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("✗ ERROR: DATABASE_URL not set")
        print("  Checked .env files:")
        print(f"    - {API_ROOT / '.env'}")
        print(f"    - {API_ROOT.parent.parent / '.env'}")
        return 1

    # Mask password for display
    url_display = database_url.split("@")[0] + "@***" if "@" in database_url else database_url[:20] + "***"
    print(f"✓ DATABASE_URL loaded: {url_display}")

    # Step 2: Import psycopg
    print("\n[2/4] Checking psycopg...")
    try:
        import psycopg
    except ImportError:
        print("✗ ERROR: psycopg not installed. Run: pip install psycopg")
        return 1
    print("✓ psycopg available")

    # Step 3: Test PostgreSQL connection
    print("\n[3/4] Connecting to PostgreSQL...")
    try:
        pg_conn = psycopg.connect(database_url, connect_timeout=15)
        print("✓ PostgreSQL connected")

        # Step 4: Check V3 rows
        print("\n[4/4] Checking V3 rows in offer_skills...")
        with pg_conn.cursor() as cursor:
            # Count total V3 rows
            cursor.execute(
                """
                SELECT COUNT(*) FROM offer_skills
                WHERE enrichment_version IN ('offer_skills_v3_metier', 'offer_skills_v3_fallback')
                  AND canonical_id LIKE 'metier:%'
                """
            )
            v3_count = cursor.fetchone()[0]
            print(f"  V3 rows (offer_skills_v3_*): {v3_count}")

            if v3_count == 0:
                print("  ⚠ WARNING: No V3 rows found. Sync would have no-op.")
                pg_conn.close()
                return 0

            # Count distinct offers
            cursor.execute(
                """
                SELECT COUNT(DISTINCT offer_id) FROM offer_skills
                WHERE enrichment_version IN ('offer_skills_v3_metier', 'offer_skills_v3_fallback')
                  AND canonical_id LIKE 'metier:%'
                """
            )
            distinct_offers = cursor.fetchone()[0]
            print(f"  Distinct offers: {distinct_offers}")

            # Count by importance level
            cursor.execute(
                """
                SELECT importance_level, COUNT(*) FROM offer_skills
                WHERE enrichment_version IN ('offer_skills_v3_metier', 'offer_skills_v3_fallback')
                  AND canonical_id LIKE 'metier:%'
                GROUP BY importance_level
                ORDER BY importance_level
                """
            )
            for importance, count in cursor.fetchall():
                print(f"  {importance}: {count}")

            # Sample offers
            print(f"\n  Sample offers (first 5):")
            cursor.execute(
                """
                SELECT DISTINCT offer_id FROM offer_skills
                WHERE enrichment_version IN ('offer_skills_v3_metier', 'offer_skills_v3_fallback')
                  AND canonical_id LIKE 'metier:%'
                ORDER BY offer_id
                LIMIT 5
                """
            )
            for (offer_id,) in cursor.fetchall():
                print(f"    - {offer_id}")

            print(f"\n✓ V3 rows ready for sync: {v3_count} rows across {distinct_offers} offers")

        pg_conn.close()

    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print("\n" + "=" * 80)
    print("PRE-CHECK PASSED")
    print("=" * 80)
    print("\nNext step: Run production sync")
    print("  python3 apps/api/scripts/sync_v3_metier_to_sqlite.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
