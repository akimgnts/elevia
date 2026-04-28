#!/usr/bin/env python3
"""backfill_offer_skills_v3_metier — complete 100% backfill of v3_metier skills.

Processes ALL business_france offers not yet enriched with v3_metier,
batching to optimize AI API calls. Enforces strict v3 constraints:
- 3 to 5 skills per offer
- Evidence mandatory (verbatim substring of title/description)
- skill_type: CORE_METIER / TOOL / CONTEXT / NOISE only
- No generics (project_management, communication, etc.)

Idempotent: skip offers already in offer_skills with enrichment_version='offer_skills_v3_metier'.

Usage:
    DATABASE_URL=postgresql://... OPENAI_API_KEY=sk-... \
        python3 apps/api/scripts/backfill_offer_skills_v3_metier.py \
            --batch-size 15 [--dry-run] [--max-offers 50]
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
    return datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M%S")


OUT_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "audit"
    / f"metier_backfill_{_utc_stamp()}"
)


IDENTIFY_MISSING_SQL = """
SELECT DISTINCT
  co.id AS offer_id,
  co.source,
  co.external_id,
  co.title,
  co.description,
  ode.domain_tag
FROM clean_offers co
LEFT JOIN offer_domain_enrichment ode
  ON ode.source = co.source AND ode.external_id = co.external_id
LEFT JOIN (
  SELECT DISTINCT offer_id
  FROM offer_skills
  WHERE enrichment_version = %s
) v3
  ON v3.offer_id = co.id
WHERE co.source = %s
  AND v3.offer_id IS NULL
  AND co.title IS NOT NULL
  AND COALESCE(co.description, '') <> ''
ORDER BY co.id
"""


def identify_missing_offers(conn, *, source: str, limit: int | None = None) -> list[dict[str, Any]]:
    """Find all offers without v3_metier enrichment."""
    with conn.cursor() as cursor:
        cursor.execute(IDENTIFY_MISSING_SQL, (ENRICHMENT_VERSION_METIER, source))
        rows = cursor.fetchall()

    offers = [
        {
            "offer_id": int(r[0]),
            "source": str(r[1]),
            "external_id": str(r[2]),
            "title": r[3] or "",
            "description": r[4] or "",
            "domain_tag": r[5] or "other",
        }
        for r in rows
    ]
    if limit:
        offers = offers[:limit]
    return offers


def batch_offers(offers: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    """Split offers into batches."""
    return [offers[i : i + batch_size] for i in range(0, len(offers), batch_size)]


def process_batch(
    conn, batch: list[dict[str, Any]], batch_idx: int, total_batches: int, dry_run: bool = False
) -> dict[str, Any]:
    """Process a batch of offers. Returns summary."""
    batch_summary = {
        "batch_idx": batch_idx,
        "total_batches": total_batches,
        "n_offers": len(batch),
        "kept_total": 0,
        "dropped_total": 0,
        "rows_written": 0,
        "errors": 0,
        "offer_summaries": [],
    }

    for offer in batch:
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

        written = persist_metier_rows(conn, rows, dry_run=dry_run)

        batch_summary["kept_total"] += len(rows)
        batch_summary["dropped_total"] += len(audit.get("dropped", []))
        batch_summary["rows_written"] += written
        if audit.get("error"):
            batch_summary["errors"] += 1

        batch_summary["offer_summaries"].append(
            {
                "offer_id": offer["offer_id"],
                "external_id": offer["external_id"],
                "domain_tag": offer["domain_tag"],
                "title": offer["title"][:80],
                "kept": len(rows),
                "dropped": len(audit.get("dropped", [])),
                "error": audit.get("error") or "",
            }
        )

    return batch_summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=15, help="Offers per batch")
    parser.add_argument("--source", default="business_france")
    parser.add_argument("--dry-run", action="store_true", help="Test without persisting")
    parser.add_argument("--max-offers", type=int, default=None, help="Limit for testing")
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

    with psycopg.connect(database_url, connect_timeout=15) as conn:
        ensure_offer_skills_table(conn)

        # Identify missing offers
        missing = identify_missing_offers(conn, source=args.source, limit=args.max_offers)
        print(f"Found {len(missing)} offers without v3_metier")

        if not missing:
            print("No offers to process.")
            return 0

        # Batch processing
        batches = batch_offers(missing, args.batch_size)
        total_batches = len(batches)
        all_kept = []
        all_dropped = []
        global_summary = {
            "enrichment_version": ENRICHMENT_VERSION_METIER,
            "source": args.source,
            "batch_size": args.batch_size,
            "dry_run": args.dry_run,
            "n_offers_total": len(missing),
            "n_batches": total_batches,
            "kept_total": 0,
            "dropped_total": 0,
            "rows_written_total": 0,
            "errors_total": 0,
            "batch_summaries": [],
        }

        for batch_idx, batch in enumerate(batches, 1):
            batch_result = process_batch(conn, batch, batch_idx, total_batches, dry_run=args.dry_run)

            global_summary["kept_total"] += batch_result["kept_total"]
            global_summary["dropped_total"] += batch_result["dropped_total"]
            global_summary["rows_written_total"] += batch_result["rows_written"]
            global_summary["errors_total"] += batch_result["errors"]
            global_summary["batch_summaries"].append(batch_result)

            # Collect all offer summaries
            for summary in batch_result["offer_summaries"]:
                print(
                    f"[{batch_idx}/{total_batches}] offer={summary['offer_id']} "
                    f"domain={summary['domain_tag']} kept={summary['kept']} dropped={summary['dropped']}"
                    + (f" ERROR={summary['error']}" if summary["error"] else "")
                )
                all_kept.append(summary)
                all_dropped.append(summary)

    # Validation metrics
    n_with_3_plus = sum(1 for s in all_kept if s["kept"] >= 3)
    avg_kept = (global_summary["kept_total"] / len(missing)) if missing else 0.0

    global_summary["avg_kept_per_offer"] = round(avg_kept, 2)
    global_summary["offers_with_3_or_more"] = n_with_3_plus
    global_summary["pct_offers_with_3_or_more"] = (
        round(n_with_3_plus * 100.0 / len(missing), 2) if missing else 0.0
    )

    # Write CSV outputs
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with (OUT_DIR / "offers_processed.csv").open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["offer_id", "external_id", "domain_tag", "title", "kept", "dropped", "error"],
        )
        w.writeheader()
        for summary in all_kept:
            w.writerow(summary)

    # Summary JSON
    (OUT_DIR / "backfill_summary.json").write_text(json.dumps(global_summary, indent=2) + "\n")

    print("\n" + "=" * 60)
    print("BACKFILL COMPLETE")
    print("=" * 60)
    print(f"Offers processed: {len(missing)}")
    print(f"Skills kept: {global_summary['kept_total']}")
    print(f"Skills dropped: {global_summary['dropped_total']}")
    print(f"Rows written: {global_summary['rows_written_total']}")
    print(f"Errors: {global_summary['errors_total']}")
    print(f"Avg kept per offer: {global_summary['avg_kept_per_offer']}")
    print(f"Offers with ≥3 skills: {n_with_3_plus} ({global_summary['pct_offers_with_3_or_more']}%)")
    print(f"Outputs: {OUT_DIR}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
