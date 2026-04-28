#!/usr/bin/env python3
"""validate_v3_backfill_complete — post-backfill validation.

Checks:
1. Coverage: All BF offers have v3_metier (target: 100%, min: 95%)
2. Skills per offer: ≥3 skills (target: 60-70%)
3. Evidence: all rows have non-empty evidence
4. Skill types: CORE_METIER dominant, NOISE minimal
5. Confidence: all scores in [0, 1]
6. Duplicates: no (offer_id, canonical_id) pairs
7. Data integrity: no null canonical_ids, no non-skill prefixes
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT / "src"))


def main() -> int:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        return 2

    import psycopg

    with psycopg.connect(database_url, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            print("=" * 70)
            print("V3 METIER BACKFILL VALIDATION")
            print("=" * 70)

            # 1. Coverage
            cur.execute("""
                SELECT COUNT(*) FROM clean_offers WHERE source='business_france'
            """)
            total_offers = cur.fetchone()[0]

            cur.execute("""
                SELECT COUNT(DISTINCT offer_id) FROM offer_skills
                WHERE enrichment_version = 'offer_skills_v3_metier'
            """)
            offers_with_v3 = cur.fetchone()[0]

            coverage_pct = round(100.0 * offers_with_v3 / total_offers, 2) if total_offers else 0.0
            print(f"\n1. COVERAGE")
            print(f"   Total BF offers: {total_offers}")
            print(f"   Offers with v3_metier: {offers_with_v3}")
            print(f"   Coverage: {coverage_pct}%")
            print(f"   Status: {'✓ PASS' if coverage_pct >= 95 else '✗ FAIL'} (target ≥95%)")

            # 2. Skills per offer distribution
            cur.execute("""
                SELECT
                  COUNT(*) as total,
                  COUNT(*) FILTER (WHERE skills_count >= 3) as with_3_plus,
                  ROUND(AVG(skills_count), 2) as avg
                FROM (
                  SELECT COUNT(*) as skills_count
                  FROM offer_skills
                  WHERE enrichment_version = 'offer_skills_v3_metier'
                  GROUP BY offer_id
                ) t
            """)
            row = cur.fetchone()
            total_with_v3, offers_with_3plus, avg_skills = row[0], row[1], row[2]
            pct_3plus = round(100.0 * offers_with_3plus / total_with_v3, 2) if total_with_v3 else 0.0

            print(f"\n2. SKILLS PER OFFER")
            print(f"   Total skills: {total_with_v3}")
            print(f"   Offers with ≥3 skills: {offers_with_3plus} ({pct_3plus}%)")
            print(f"   Avg per offer: {avg_skills}")
            print(f"   Status: {'✓ PASS' if pct_3plus >= 60 else '⚠ WARN'} (target 60-70%)")

            # 3. Skill type distribution
            cur.execute("""
                SELECT skill_type, COUNT(*) as count
                FROM offer_skills
                WHERE enrichment_version = 'offer_skills_v3_metier'
                GROUP BY skill_type
                ORDER BY count DESC
            """)
            type_dist = {row[0]: row[1] for row in cur.fetchall()}
            total_skills = sum(type_dist.values())
            core_pct = round(100.0 * type_dist.get("CORE_METIER", 0) / total_skills, 2)
            noise_pct = round(100.0 * type_dist.get("NOISE", 0) / total_skills, 2)

            print(f"\n3. SKILL TYPE DISTRIBUTION")
            for skill_type in ["CORE_METIER", "TOOL", "CONTEXT", "NOISE"]:
                count = type_dist.get(skill_type, 0)
                pct = round(100.0 * count / total_skills, 2) if total_skills else 0.0
                print(f"   {skill_type}: {count} ({pct}%)")
            print(f"   Status: {'✓ PASS' if core_pct >= 70 and noise_pct < 2 else '⚠ WARN'}")

            # 4. Evidence validation
            cur.execute("""
                SELECT
                  COUNT(*) as total,
                  COUNT(*) FILTER (WHERE evidence IS NOT NULL AND evidence <> '') as with_evidence
                FROM offer_skills
                WHERE enrichment_version = 'offer_skills_v3_metier'
            """)
            total_rows, rows_with_evidence = cur.fetchone()
            evidence_pct = round(100.0 * rows_with_evidence / total_rows, 2) if total_rows else 0.0

            print(f"\n4. EVIDENCE VALIDATION")
            print(f"   Rows with evidence: {rows_with_evidence}/{total_rows} ({evidence_pct}%)")
            print(f"   Status: {'✓ PASS' if evidence_pct == 100.0 else '✗ FAIL'} (all required)")

            # 5. Confidence distribution
            cur.execute("""
                SELECT
                  COUNT(*) FILTER (WHERE confidence >= 0.7) as high,
                  COUNT(*) FILTER (WHERE confidence >= 0.5 AND confidence < 0.7) as med,
                  COUNT(*) FILTER (WHERE confidence < 0.5) as low,
                  COUNT(*) FILTER (WHERE confidence < 0 OR confidence > 1) as invalid
                FROM offer_skills
                WHERE enrichment_version = 'offer_skills_v3_metier'
            """)
            high, med, low, invalid = cur.fetchone()
            print(f"\n5. CONFIDENCE DISTRIBUTION")
            print(f"   High (≥0.7): {high}")
            print(f"   Medium (0.5-0.7): {med}")
            print(f"   Low (<0.5): {low}")
            print(f"   Invalid: {invalid}")
            print(f"   Status: {'✓ PASS' if invalid == 0 else '✗ FAIL'}")

            # 6. Duplicates check
            cur.execute("""
                SELECT COUNT(*) FROM (
                  SELECT offer_id, canonical_id, COUNT(*) as cnt
                  FROM offer_skills
                  WHERE enrichment_version = 'offer_skills_v3_metier'
                  GROUP BY offer_id, canonical_id
                  HAVING COUNT(*) > 1
                ) t
            """)
            duplicate_pairs = cur.fetchone()[0]

            print(f"\n6. DUPLICATES CHECK")
            print(f"   Duplicate (offer_id, canonical_id) pairs: {duplicate_pairs}")
            print(f"   Status: {'✓ PASS' if duplicate_pairs == 0 else '✗ FAIL'}")

            # 7. Data integrity
            cur.execute("""
                SELECT
                  COUNT(*) FILTER (WHERE canonical_id IS NULL) as null_canonical,
                  COUNT(*) FILTER (WHERE canonical_id NOT LIKE 'metier:%') as non_metier_prefix
                FROM offer_skills
                WHERE enrichment_version = 'offer_skills_v3_metier'
            """)
            null_canonical, non_metier = cur.fetchone()

            print(f"\n7. DATA INTEGRITY")
            print(f"   Null canonical_id: {null_canonical}")
            print(f"   Non-metier: prefix: {non_metier}")
            print(f"   Status: {'✓ PASS' if null_canonical == 0 and non_metier == 0 else '✗ FAIL'}")

            # Final summary
            print(f"\n" + "=" * 70)
            checks_pass = (
                coverage_pct >= 95
                and pct_3plus >= 60
                and core_pct >= 70
                and evidence_pct == 100.0
                and invalid == 0
                and duplicate_pairs == 0
                and null_canonical == 0
                and non_metier == 0
            )
            if checks_pass:
                print("✓ ALL CHECKS PASSED — V3 BACKFILL COMPLETE & VALIDATED")
            else:
                print("✗ SOME CHECKS FAILED — SEE ABOVE FOR DETAILS")
            print("=" * 70)

    return 0 if checks_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
