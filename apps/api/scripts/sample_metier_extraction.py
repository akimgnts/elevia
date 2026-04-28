#!/usr/bin/env python3
"""sample_metier_extraction — domain-aware v3 metier extraction on a controlled sample.

Picks offers stratified by domain from `offer_domain_enrichment`, runs the new
strict prompt (`offer_skills_metier`), persists rows under
`enrichment_version = 'offer_skills_v3_metier'`, and writes audit CSVs.

Does NOT touch v2 rows (different enrichment_version, version-scoped DELETE).

Usage:
    DATABASE_URL=postgresql://... OPENAI_API_KEY=sk-... \
        python3 apps/api/scripts/sample_metier_extraction.py \
            --per-domain 5 --top-domains 6 [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT / "src"))

from api.utils.offer_skills_metier import (  # noqa: E402
    ENRICHMENT_VERSION_METIER,
    build_metier_rows,
    persist_metier_rows,
)
from api.utils.offer_skills_pg import (  # noqa: E402
    compute_offer_skills_content_hash,
    ensure_offer_skills_table,
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y_%m_%d")


OUT_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "audit"
    / f"metier_sample_{_utc_stamp()}"
)


PICK_STRATIFIED_SQL = """
WITH ranked AS (
  SELECT
    co.id AS offer_id,
    co.source,
    co.external_id,
    co.title,
    co.description,
    ode.domain_tag,
    ROW_NUMBER() OVER (PARTITION BY ode.domain_tag ORDER BY co.id) AS rn
  FROM clean_offers co
  JOIN offer_domain_enrichment ode
    ON ode.source = co.source AND ode.external_id = co.external_id
  WHERE co.source = %s
    AND ode.domain_tag IN (
      SELECT domain_tag
      FROM offer_domain_enrichment
      WHERE source = %s
      GROUP BY domain_tag
      ORDER BY COUNT(*) DESC
      LIMIT %s
    )
    AND co.title IS NOT NULL
    AND COALESCE(co.description, '') <> ''
)
SELECT offer_id, source, external_id, title, description, domain_tag
FROM ranked
WHERE rn <= %s
ORDER BY domain_tag, offer_id
"""


def pick_stratified_offers(
    conn,
    *,
    source: str,
    top_domains: int,
    per_domain: int,
) -> list[dict[str, Any]]:
    with conn.cursor() as cursor:
        cursor.execute(PICK_STRATIFIED_SQL, (source, source, top_domains, per_domain))
        rows = cursor.fetchall()
    return [
        {
            "offer_id": int(r[0]),
            "source": str(r[1]),
            "external_id": str(r[2]),
            "title": r[3] or "",
            "description": r[4] or "",
            "domain_tag": r[5] or "",
        }
        for r in rows
    ]


def write_csv(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for row in rows:
            w.writerow([row.get(h) for h in headers])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-domain", type=int, default=5)
    parser.add_argument("--top-domains", type=int, default=6)
    parser.add_argument("--source", default="business_france")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        return 2
    if not (os.getenv("OPENAI_API_KEY") or "").strip():
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    import psycopg

    persisted_rows: list[dict[str, Any]] = []
    dropped_rows: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []

    with psycopg.connect(database_url, connect_timeout=15) as conn:
        ensure_offer_skills_table(conn)
        offers = pick_stratified_offers(
            conn,
            source=args.source,
            top_domains=args.top_domains,
            per_domain=args.per_domain,
        )
        print(f"picked {len(offers)} offers across top {args.top_domains} domains")

        for idx, offer in enumerate(offers, 1):
            content_hash = compute_offer_skills_content_hash(
                title=offer["title"], description=offer["description"]
            )
            rows, audit = build_metier_rows(
                offer_id=offer["offer_id"],
                source=offer["source"],
                external_id=offer["external_id"],
                title=offer["title"],
                description=offer["description"],
                domain_tag=offer["domain_tag"],
                content_hash=content_hash,
            )

            written = persist_metier_rows(conn, rows, dry_run=args.dry_run)

            for row in rows:
                persisted_rows.append(
                    {
                        "offer_id": row["offer_id"],
                        "external_id": row["external_id"],
                        "domain_tag": offer["domain_tag"],
                        "canonical_id": row["canonical_id"],
                        "label": row["label"],
                        "skill_type": row["skill_type"],
                        "importance_level": row["importance_level"],
                        "confidence": row["confidence"],
                        "evidence": row["evidence"],
                    }
                )
            for d in audit["dropped"]:
                dropped_rows.append(
                    {
                        "offer_id": offer["offer_id"],
                        "external_id": offer["external_id"],
                        "domain_tag": offer["domain_tag"],
                        "label": d.get("label", ""),
                        "skill_type": d.get("skill_type", ""),
                        "evidence": d.get("evidence", ""),
                        "reason": d.get("reason", ""),
                    }
                )
            summary.append(
                {
                    "offer_id": offer["offer_id"],
                    "external_id": offer["external_id"],
                    "domain_tag": offer["domain_tag"],
                    "title": offer["title"][:120],
                    "kept": len(rows),
                    "dropped": len(audit["dropped"]),
                    "rows_written": written,
                    "error": audit.get("error") or "",
                }
            )

            print(
                f"[{idx}/{len(offers)}] offer={offer['offer_id']} "
                f"domain={offer['domain_tag']} kept={len(rows)} dropped={len(audit['dropped'])}"
                + (f" ERROR={audit['error']}" if audit.get("error") else "")
            )

    # CSV outputs (always written, even on dry-run, for inspection)
    write_csv(
        OUT_DIR / "kept_skills.csv",
        persisted_rows,
        ["offer_id", "external_id", "domain_tag", "canonical_id", "label",
         "skill_type", "importance_level", "confidence", "evidence"],
    )
    write_csv(
        OUT_DIR / "dropped_skills.csv",
        dropped_rows,
        ["offer_id", "external_id", "domain_tag", "label", "skill_type", "evidence", "reason"],
    )
    write_csv(
        OUT_DIR / "summary.csv",
        summary,
        ["offer_id", "external_id", "domain_tag", "title", "kept", "dropped", "rows_written", "error"],
    )

    # Run-level summary JSON
    n_offers = len(summary)
    kept_total = sum(s["kept"] for s in summary)
    dropped_total = sum(s["dropped"] for s in summary)
    n_with_3_plus = sum(1 for s in summary if s["kept"] >= 3)
    avg = (kept_total / n_offers) if n_offers else 0.0
    overview = {
        "enrichment_version": ENRICHMENT_VERSION_METIER,
        "source": args.source,
        "top_domains": args.top_domains,
        "per_domain": args.per_domain,
        "dry_run": args.dry_run,
        "n_offers": n_offers,
        "kept_total": kept_total,
        "dropped_total": dropped_total,
        "avg_kept_per_offer": round(avg, 2),
        "offers_with_3_or_more": n_with_3_plus,
        "pct_offers_with_3_or_more": round(n_with_3_plus * 100.0 / n_offers, 2) if n_offers else 0.0,
    }
    (OUT_DIR / "run_summary.json").write_text(json.dumps(overview, indent=2) + "\n")

    print("\nrun summary:")
    for k, v in overview.items():
        print(f"  {k}: {v}")
    print(f"\noutputs in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
