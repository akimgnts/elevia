"""audit_db_4blocks — comprehensive DB audit (12 CSV exports + summary).

Runs the 4-block audit on the live PostgreSQL database (offer_domain_enrichment,
offer_skills, clean_offers).

Usage:
    DATABASE_URL=postgresql://... python scripts/audit_db_4blocks.py
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from typing import Any, List, Tuple

import psycopg

OUT_DIR = Path(__file__).resolve().parent.parent / "audit" / "db_audit_2026_04_27"


QUERIES: List[Tuple[str, str]] = [
    (
        "01_domain_distribution.csv",
        """
        SELECT
          domain_tag,
          COUNT(*) AS n,
          ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
        FROM offer_domain_enrichment
        GROUP BY domain_tag
        ORDER BY n DESC
        """,
    ),
    (
        "02_method_distribution.csv",
        """
        SELECT
          method,
          COUNT(*) AS n,
          ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct,
          ROUND(AVG(confidence)::numeric, 3) AS avg_confidence,
          MIN(confidence) AS min_confidence,
          MAX(confidence) AS max_confidence
        FROM offer_domain_enrichment
        GROUP BY method
        ORDER BY n DESC
        """,
    ),
    (
        "03_low_confidence_rules.csv",
        """
        SELECT
          co.external_id,
          co.title,
          co.company,
          co.country,
          ode.domain_tag,
          ode.confidence,
          ode.method,
          ode.evidence::text AS evidence
        FROM offer_domain_enrichment ode
        JOIN clean_offers co
          ON co.source = ode.source
         AND co.external_id = ode.external_id
        WHERE ode.method = 'rules'
          AND ode.confidence <= 0.5
        ORDER BY ode.confidence ASC, co.title
        """,
    ),
    (
        "04_high_confidence_rules.csv",
        """
        SELECT
          co.external_id,
          co.title,
          co.company,
          co.country,
          ode.domain_tag,
          ode.confidence,
          ode.method,
          ode.evidence::text AS evidence
        FROM offer_domain_enrichment ode
        JOIN clean_offers co
          ON co.source = ode.source
         AND co.external_id = ode.external_id
        WHERE ode.method = 'rules'
          AND ode.confidence >= 0.9
        ORDER BY ode.domain_tag, co.title
        """,
    ),
    (
        "05_evidence_frequency.csv",
        """
        SELECT
          ode.method,
          ode.domain_tag,
          jsonb_array_elements_text(ode.evidence) AS evidence_item,
          COUNT(*) AS n
        FROM offer_domain_enrichment ode
        WHERE ode.evidence IS NOT NULL
          AND jsonb_typeof(ode.evidence) = 'array'
        GROUP BY ode.method, ode.domain_tag, evidence_item
        ORDER BY n DESC
        LIMIT 200
        """,
    ),
    (
        "06_skills_distribution.csv",
        """
        SELECT
          'global_total' AS metric,
          NULL::text AS importance_level,
          NULL::text AS source_method,
          COUNT(*) AS n,
          NULL::numeric AS pct
        FROM offer_skills
        UNION ALL
        SELECT
          'by_importance' AS metric,
          importance_level,
          NULL::text AS source_method,
          COUNT(*) AS n,
          ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY 1), 2) AS pct
        FROM offer_skills
        GROUP BY importance_level
        UNION ALL
        SELECT
          'by_source_method' AS metric,
          NULL::text AS importance_level,
          source_method,
          COUNT(*) AS n,
          ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY 1), 2) AS pct
        FROM offer_skills
        GROUP BY source_method
        ORDER BY metric, n DESC
        """,
    ),
    (
        "07_core_skills_global.csv",
        """
        SELECT
          canonical_id,
          label,
          COUNT(*) AS n
        FROM offer_skills
        WHERE importance_level = 'CORE'
        GROUP BY canonical_id, label
        ORDER BY n DESC
        LIMIT 100
        """,
    ),
    (
        "08_core_skills_by_domain.csv",
        """
        SELECT *
        FROM (
          SELECT
            ode.domain_tag,
            os.canonical_id,
            os.label,
            COUNT(*) AS n,
            ROW_NUMBER() OVER (
              PARTITION BY ode.domain_tag
              ORDER BY COUNT(*) DESC
            ) AS rank
          FROM offer_skills os
          JOIN clean_offers co
            ON co.id = os.offer_id
          JOIN offer_domain_enrichment ode
            ON ode.source = co.source
           AND ode.external_id = co.external_id
          WHERE os.importance_level = 'CORE'
          GROUP BY ode.domain_tag, os.canonical_id, os.label
        ) ranked
        WHERE rank <= 20
        ORDER BY domain_tag, rank
        """,
    ),
    (
        "09_tech_leaks_non_tech_domains.csv",
        """
        SELECT
          ode.domain_tag,
          os.canonical_id,
          os.label,
          os.importance_level,
          COUNT(*) AS n
        FROM offer_skills os
        JOIN clean_offers co
          ON co.id = os.offer_id
        JOIN offer_domain_enrichment ode
          ON ode.source = co.source
         AND ode.external_id = co.external_id
        WHERE ode.domain_tag NOT IN ('data', 'engineering')
          AND os.canonical_id IN (
            'skill:sql_querying',
            'skill:cloud_architecture',
            'skill:backend_development',
            'skill:frontend_development',
            'skill:database_design',
            'skill:business_intelligence'
          )
        GROUP BY ode.domain_tag, os.canonical_id, os.label, os.importance_level
        ORDER BY n DESC
        """,
    ),
    (
        "10_offers_without_core.csv",
        """
        SELECT
          co.external_id,
          co.title,
          co.company,
          ode.domain_tag,
          COUNT(os.id) AS total_skills,
          COUNT(*) FILTER (WHERE os.importance_level = 'CORE') AS core_count
        FROM clean_offers co
        LEFT JOIN offer_skills os
          ON os.offer_id = co.id
        LEFT JOIN offer_domain_enrichment ode
          ON ode.source = co.source
         AND ode.external_id = co.external_id
        WHERE co.source = 'business_france'
        GROUP BY co.external_id, co.title, co.company, ode.domain_tag
        HAVING COUNT(*) FILTER (WHERE os.importance_level = 'CORE') = 0
        ORDER BY total_skills DESC
        """,
    ),
    (
        "11_core_ratio_by_domain.csv",
        """
        SELECT
          ode.domain_tag,
          COUNT(DISTINCT co.id) AS offer_count,
          COUNT(os.id) AS total_skills,
          COUNT(*) FILTER (WHERE os.importance_level = 'CORE') AS core_skills,
          COUNT(DISTINCT os.canonical_id) FILTER (WHERE os.importance_level = 'CORE') AS distinct_core_skills,
          ROUND(
            COUNT(*) FILTER (WHERE os.importance_level = 'CORE') * 100.0
            / NULLIF(COUNT(os.id), 0),
            2
          ) AS core_pct
        FROM clean_offers co
        LEFT JOIN offer_skills os
          ON os.offer_id = co.id
        LEFT JOIN offer_domain_enrichment ode
          ON ode.source = co.source
         AND ode.external_id = co.external_id
        WHERE co.source = 'business_france'
        GROUP BY ode.domain_tag
        ORDER BY core_pct ASC NULLS FIRST
        """,
    ),
    (
        "12_title_domain_mismatches.csv",
        """
        SELECT
          'business_analyst' AS title_pattern,
          co.external_id,
          co.title,
          co.company,
          ode.domain_tag,
          ode.confidence,
          ode.method,
          ode.evidence::text AS evidence
        FROM clean_offers co
        JOIN offer_domain_enrichment ode
          ON ode.source = co.source
         AND ode.external_id = co.external_id
        WHERE LOWER(co.title) LIKE '%business analyst%'

        UNION ALL
        SELECT
          'business_developer_not_sales',
          co.external_id, co.title, co.company,
          ode.domain_tag, ode.confidence, ode.method, ode.evidence::text
        FROM clean_offers co
        JOIN offer_domain_enrichment ode
          ON ode.source = co.source
         AND ode.external_id = co.external_id
        WHERE LOWER(co.title) LIKE '%business developer%'
          AND ode.domain_tag != 'sales'

        UNION ALL
        SELECT
          'recruit_or_talent_or_hr_not_hr',
          co.external_id, co.title, co.company,
          ode.domain_tag, ode.confidence, ode.method, ode.evidence::text
        FROM clean_offers co
        JOIN offer_domain_enrichment ode
          ON ode.source = co.source
         AND ode.external_id = co.external_id
        WHERE (LOWER(co.title) LIKE '%recruit%'
            OR LOWER(co.title) LIKE '%talent%'
            OR LOWER(co.title) LIKE '%hr%')
          AND ode.domain_tag != 'hr'

        UNION ALL
        SELECT
          'data_title_not_data',
          co.external_id, co.title, co.company,
          ode.domain_tag, ode.confidence, ode.method, ode.evidence::text
        FROM clean_offers co
        JOIN offer_domain_enrichment ode
          ON ode.source = co.source
         AND ode.external_id = co.external_id
        WHERE (LOWER(co.title) LIKE '%data analyst%'
            OR LOWER(co.title) LIKE '%data engineer%'
            OR LOWER(co.title) LIKE '%data scientist%')
          AND ode.domain_tag != 'data'

        UNION ALL
        SELECT
          'developer_not_engineering',
          co.external_id, co.title, co.company,
          ode.domain_tag, ode.confidence, ode.method, ode.evidence::text
        FROM clean_offers co
        JOIN offer_domain_enrichment ode
          ON ode.source = co.source
         AND ode.external_id = co.external_id
        WHERE (LOWER(co.title) LIKE '%developer%'
            OR LOWER(co.title) LIKE '%développeur%'
            OR LOWER(co.title) LIKE '%developpeur%')
          AND ode.domain_tag != 'engineering'

        ORDER BY title_pattern, domain_tag, confidence DESC
        """,
    ),
]


def _run(conn: psycopg.Connection, sql: str) -> Tuple[List[str], List[Tuple[Any, ...]]]:
    cur = conn.execute(sql)
    cols = [d.name for d in cur.description]
    rows = cur.fetchall()
    return cols, rows


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        return 2

    summary_lines: List[str] = []
    summary_lines.append(f"# DB Audit — 4 blocks ({OUT_DIR.name})")
    summary_lines.append("")

    with psycopg.connect(url, connect_timeout=15) as conn:
        for fname, sql in QUERIES:
            try:
                cols, rows = _run(conn, sql)
            except Exception as exc:
                print(f"FAIL {fname}: {exc}", file=sys.stderr)
                summary_lines.append(f"- **{fname}**: FAIL — `{exc}`")
                continue

            out_path = OUT_DIR / fname
            with out_path.open("w", newline="") as f:
                w = csv.writer(f)
                w.writerow(cols)
                for r in rows:
                    w.writerow(r)

            summary_lines.append(f"- **{fname}**: {len(rows)} rows")
            print(f"OK {fname} — {len(rows)} rows")

    summary = OUT_DIR / "00_SUMMARY.md"
    summary.write_text("\n".join(summary_lines) + "\n")
    print(f"\nSummary: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
