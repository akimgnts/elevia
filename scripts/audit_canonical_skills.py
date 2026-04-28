"""audit_canonical_skills — full audit of canonical skill system.

Steps 1-5: SQL inventory, coverage, quality, domain coherence, redundancy.
Outputs CSV files + summary stats. Step 6 (structural classification) and
Step 7 (final diagnosis) are produced manually from these results.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from typing import Any, List, Tuple

import psycopg

OUT_DIR = Path(__file__).resolve().parent.parent / "audit" / "canonical_skills_audit_2026_04_27"

QUERIES: List[Tuple[str, str]] = [
    # STEP 1 — INVENTORY
    (
        "step1_inventory_summary.csv",
        """
        SELECT
          (SELECT COUNT(DISTINCT canonical_id) FROM offer_skills) AS distinct_canonical_ids,
          (SELECT COUNT(*) FROM offer_skills) AS total_offer_skill_rows,
          (SELECT COUNT(DISTINCT offer_id) FROM offer_skills) AS distinct_offers_with_skills
        """,
    ),
    (
        "step1_canonical_frequency.csv",
        """
        SELECT
          canonical_id,
          MIN(label) AS sample_label,
          COUNT(*) AS occurrences,
          COUNT(DISTINCT offer_id) AS offers_using,
          ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total
        FROM offer_skills
        GROUP BY canonical_id
        ORDER BY occurrences DESC
        """,
    ),
    # STEP 2 — COVERAGE
    (
        "step2_coverage_overall.csv",
        """
        WITH offers AS (
          SELECT id FROM clean_offers WHERE source = 'business_france'
        ),
        per_offer AS (
          SELECT o.id AS offer_id, COUNT(os.id) AS skill_count
          FROM offers o LEFT JOIN offer_skills os ON os.offer_id = o.id
          GROUP BY o.id
        )
        SELECT
          (SELECT COUNT(*) FROM offers) AS total_offers,
          COUNT(*) FILTER (WHERE skill_count = 0) AS offers_without_skills,
          COUNT(*) FILTER (WHERE skill_count >= 1) AS offers_with_at_least_1_skill,
          COUNT(*) FILTER (WHERE skill_count >= 3) AS offers_with_at_least_3_skills,
          ROUND(AVG(skill_count)::numeric, 2) AS avg_skills_per_offer,
          MIN(skill_count) AS min_skills,
          MAX(skill_count) AS max_skills,
          ROUND(
            COUNT(*) FILTER (WHERE skill_count = 0) * 100.0 / COUNT(*), 2
          ) AS pct_unusable_offers
        FROM per_offer
        """,
    ),
    (
        "step2_coverage_by_domain.csv",
        """
        WITH per_offer AS (
          SELECT
            co.id AS offer_id,
            ode.domain_tag,
            COUNT(os.id) AS skill_count
          FROM clean_offers co
          LEFT JOIN offer_skills os ON os.offer_id = co.id
          LEFT JOIN offer_domain_enrichment ode
            ON ode.source = co.source AND ode.external_id = co.external_id
          WHERE co.source = 'business_france'
          GROUP BY co.id, ode.domain_tag
        )
        SELECT
          domain_tag,
          COUNT(*) AS offer_count,
          COUNT(*) FILTER (WHERE skill_count = 0) AS no_skills,
          ROUND(AVG(skill_count)::numeric, 2) AS avg_skills,
          MAX(skill_count) AS max_skills,
          ROUND(COUNT(*) FILTER (WHERE skill_count = 0) * 100.0 / COUNT(*), 2) AS pct_no_skills
        FROM per_offer
        GROUP BY domain_tag
        ORDER BY pct_no_skills DESC
        """,
    ),
    # STEP 3 — SKILL QUALITY (top 20)
    (
        "step3_top20_skills.csv",
        """
        SELECT
          canonical_id,
          MIN(label) AS sample_label,
          COUNT(*) AS occurrences,
          COUNT(DISTINCT offer_id) AS offers_using,
          COUNT(*) FILTER (WHERE importance_level = 'CORE') AS core_count,
          COUNT(*) FILTER (WHERE importance_level = 'SECONDARY') AS secondary_count,
          ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct_of_total
        FROM offer_skills
        GROUP BY canonical_id
        ORDER BY occurrences DESC
        LIMIT 20
        """,
    ),
    # STEP 4 — DOMAIN × SKILLS COHERENCE (top 10 per domain)
    (
        "step4_top10_skills_per_domain.csv",
        """
        SELECT *
        FROM (
          SELECT
            ode.domain_tag,
            os.canonical_id,
            MIN(os.label) AS sample_label,
            COUNT(*) AS n,
            ROW_NUMBER() OVER (PARTITION BY ode.domain_tag ORDER BY COUNT(*) DESC) AS rank
          FROM offer_skills os
          JOIN clean_offers co ON co.id = os.offer_id
          JOIN offer_domain_enrichment ode
            ON ode.source = co.source AND ode.external_id = co.external_id
          GROUP BY ode.domain_tag, os.canonical_id
        ) ranked
        WHERE rank <= 10
        ORDER BY domain_tag, rank
        """,
    ),
    (
        "step4_skill_domain_spread.csv",
        """
        WITH skill_domain AS (
          SELECT
            os.canonical_id,
            ode.domain_tag,
            COUNT(*) AS n
          FROM offer_skills os
          JOIN clean_offers co ON co.id = os.offer_id
          JOIN offer_domain_enrichment ode
            ON ode.source = co.source AND ode.external_id = co.external_id
          GROUP BY os.canonical_id, ode.domain_tag
        )
        SELECT
          canonical_id,
          COUNT(DISTINCT domain_tag) AS distinct_domains,
          SUM(n) AS total_uses,
          STRING_AGG(domain_tag || ':' || n, ', ' ORDER BY n DESC) AS distribution
        FROM skill_domain
        GROUP BY canonical_id
        HAVING SUM(n) >= 10
        ORDER BY distinct_domains DESC, total_uses DESC
        LIMIT 50
        """,
    ),
    # STEP 5 — REDUNDANCY / FRAGMENTATION
    (
        "step5_low_frequency_skills.csv",
        """
        WITH freq AS (
          SELECT canonical_id, MIN(label) AS sample_label, COUNT(*) AS n
          FROM offer_skills
          GROUP BY canonical_id
        )
        SELECT
          (SELECT COUNT(*) FROM freq) AS distinct_total,
          (SELECT COUNT(*) FROM freq WHERE n = 1) AS singletons,
          (SELECT COUNT(*) FROM freq WHERE n < 3) AS rare_below_3,
          (SELECT COUNT(*) FROM freq WHERE n < 5) AS rare_below_5,
          (SELECT ROUND(COUNT(*) FILTER (WHERE n = 1) * 100.0 / COUNT(*), 2) FROM freq) AS pct_singletons,
          (SELECT ROUND(COUNT(*) FILTER (WHERE n < 3) * 100.0 / COUNT(*), 2) FROM freq) AS pct_below_3
        """,
    ),
    (
        "step5_singletons_sample.csv",
        """
        SELECT canonical_id, MIN(label) AS sample_label, COUNT(*) AS n
        FROM offer_skills
        GROUP BY canonical_id
        HAVING COUNT(*) <= 2
        ORDER BY n ASC, canonical_id
        LIMIT 100
        """,
    ),
]


def _run(conn: psycopg.Connection, sql: str) -> Tuple[List[str], List[Tuple[Any, ...]]]:
    cur = conn.execute(sql)
    cols = [d.name for d in cur.description]
    return cols, cur.fetchall()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        return 2

    with psycopg.connect(url, connect_timeout=15) as conn:
        for fname, sql in QUERIES:
            try:
                cols, rows = _run(conn, sql)
            except Exception as exc:
                print(f"FAIL {fname}: {exc}", file=sys.stderr)
                continue
            (OUT_DIR / fname).open("w", newline="").close()  # truncate
            with (OUT_DIR / fname).open("w", newline="") as f:
                w = csv.writer(f)
                w.writerow(cols)
                for r in rows:
                    w.writerow(r)
            print(f"OK {fname} — {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
