#!/usr/bin/env python3
"""simple_ranking_comparison — compare V1 vs V3 skill extraction quality.

Direct coverage & richness comparison: shows V2 vs V3+fallback across all offers.
No profile matching needed (V2 and V3 use incompatible skill namespaces).

Usage:
    DATABASE_URL=postgresql://... python3 apps/api/scripts/simple_ranking_comparison.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        return 2

    print("=" * 80)
    print("V1 vs V3+FALLBACK EXTRACTION COMPARISON")
    print("=" * 80)
    print("\nDirect coverage and richness comparison (no profile needed).")
    print("V1 = offer_skills_v2 baseline")
    print("V3 = offer_skills_v3_metier + offer_skills_v3_fallback\n")

    import psycopg

    with psycopg.connect(database_url, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            # Coverage: How many offers have skills in each version?
            print("=" * 80)
            print("COVERAGE (% of business_france offers with ≥1 skill)")
            print("=" * 80)

            cur.execute("""
                SELECT COUNT(*) FROM clean_offers
                WHERE source = 'business_france'
            """)
            total_offers = cur.fetchone()[0]
            print(f"Total business_france offers: {total_offers}")

            cur.execute("""
                SELECT COUNT(DISTINCT offer_id)
                FROM offer_skills
                WHERE enrichment_version = 'offer_skills_v2'
                  AND offer_id IN (
                    SELECT id FROM clean_offers WHERE source = 'business_france'
                  )
            """)
            v1_covered = cur.fetchone()[0]
            print(f"V1 (v2) covered: {v1_covered}/{total_offers} ({100*v1_covered/total_offers:.1f}%)")

            cur.execute("""
                SELECT COUNT(DISTINCT offer_id)
                FROM offer_skills
                WHERE enrichment_version IN ('offer_skills_v3_metier', 'offer_skills_v3_fallback')
                  AND offer_id IN (
                    SELECT id FROM clean_offers WHERE source = 'business_france'
                  )
            """)
            v3_covered = cur.fetchone()[0]
            print(f"V3 (v3_metier+fallback) covered: {v3_covered}/{total_offers} ({100*v3_covered/total_offers:.1f}%)")

            # Skill richness: avg skills per offer
            print("\n" + "=" * 80)
            print("RICHNESS (avg skills per covered offer)")
            print("=" * 80)

            cur.execute("""
                SELECT AVG(skill_count)
                FROM (
                  SELECT COUNT(*) as skill_count
                  FROM offer_skills
                  WHERE enrichment_version = 'offer_skills_v2'
                  GROUP BY offer_id
                ) t
            """)
            v1_avg = cur.fetchone()[0] or 0
            print(f"V1 (v2): {v1_avg:.2f} skills/offer")

            cur.execute("""
                SELECT AVG(skill_count)
                FROM (
                  SELECT COUNT(*) as skill_count
                  FROM offer_skills
                  WHERE enrichment_version IN ('offer_skills_v3_metier', 'offer_skills_v3_fallback')
                  GROUP BY offer_id
                ) t
            """)
            v3_avg = cur.fetchone()[0] or 0
            print(f"V3 (v3_metier+fallback): {v3_avg:.2f} skills/offer")

            # Minimum skills threshold: % of offers with ≥3 skills
            print("\n" + "=" * 80)
            print("MINIMUM THRESHOLD (% with ≥3 skills)")
            print("=" * 80)

            cur.execute("""
                SELECT COUNT(*)
                FROM (
                  SELECT offer_id, COUNT(*) as cnt
                  FROM offer_skills
                  WHERE enrichment_version = 'offer_skills_v2'
                  GROUP BY offer_id
                  HAVING COUNT(*) >= 3
                ) t
            """)
            v1_min3 = cur.fetchone()[0]
            print(f"V1: {v1_min3}/{total_offers} ({100*v1_min3/total_offers:.1f}%)")

            cur.execute("""
                SELECT COUNT(*)
                FROM (
                  SELECT offer_id, COUNT(*) as cnt
                  FROM offer_skills
                  WHERE enrichment_version IN ('offer_skills_v3_metier', 'offer_skills_v3_fallback')
                  GROUP BY offer_id
                  HAVING COUNT(*) >= 3
                ) t
            """)
            v3_min3 = cur.fetchone()[0]
            print(f"V3: {v3_min3}/{total_offers} ({100*v3_min3/total_offers:.1f}%)")

            # Quality metrics: V3 skill type distribution
            print("\n" + "=" * 80)
            print("V3 SKILL TYPE DISTRIBUTION (v3_metier + fallback)")
            print("=" * 80)

            cur.execute("""
                SELECT skill_type, COUNT(*) as cnt
                FROM offer_skills
                WHERE enrichment_version IN ('offer_skills_v3_metier', 'offer_skills_v3_fallback')
                GROUP BY skill_type
                ORDER BY cnt DESC
            """)
            for skill_type, cnt in cur.fetchall():
                print(f"  {skill_type}: {cnt}")

            # Sample top offers by skill count (both versions)
            print("\n" + "=" * 80)
            print("TOP 10 RICHEST OFFERS (by V3 skill count)")
            print("=" * 80)

            cur.execute("""
                SELECT
                  co.id,
                  co.title,
                  v3_counts.cnt as v3_skills
                FROM clean_offers co
                JOIN (
                  SELECT offer_id, COUNT(*) as cnt
                  FROM offer_skills
                  WHERE enrichment_version IN ('offer_skills_v3_metier', 'offer_skills_v3_fallback')
                  GROUP BY offer_id
                ) v3_counts ON co.id = v3_counts.offer_id
                WHERE co.source = 'business_france'
                ORDER BY v3_counts.cnt DESC
                LIMIT 10
            """)

            for idx, (offer_id, title, v3_cnt) in enumerate(cur.fetchall(), 1):
                # Get V1 count for same offer
                cur.execute("""
                    SELECT COUNT(*)
                    FROM offer_skills
                    WHERE offer_id = %s AND enrichment_version = 'offer_skills_v2'
                """, (offer_id,))
                v1_cnt = cur.fetchone()[0]

                print(f"{idx:2}. {title[:60]}")
                print(f"       V1: {v1_cnt} skills | V3: {v3_cnt} skills | Improvement: +{v3_cnt-v1_cnt}")

    print("\n" + "=" * 80)
    print("✓ Comparison complete")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
