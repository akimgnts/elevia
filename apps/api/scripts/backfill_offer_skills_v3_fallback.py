#!/usr/bin/env python3
"""backfill_offer_skills_v3_fallback — fallback extraction for 0-skill offers.

Processes offers WITHOUT any v3_metier skills. Extraction is relaxed:
- max 3 skills (vs v3's 5)
- relaxed evidence (contextual cues OK)
- CORE_METIER / TOOL / CONTEXT only (no NOISE)

NEVER touches v3_metier. Insert only if offer has 0 v3_metier rows.

Usage:
    DATABASE_URL=postgresql://... OPENAI_API_KEY=sk-... \
        python3 apps/api/scripts/backfill_offer_skills_v3_fallback.py \
            [--dry-run]
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

from api.utils.offer_skills_fallback import (  # noqa: E402
    ENRICHMENT_VERSION_FALLBACK,
    build_fallback_rows,
    persist_fallback_rows,
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
    / f"metier_fallback_{_utc_stamp()}"
)


IDENTIFY_ZERO_SKILL_OFFERS_SQL = """
SELECT
  co.id AS offer_id,
  co.source,
  co.external_id,
  co.title,
  co.description,
  COALESCE(ode.domain_tag, 'other') AS domain_tag
FROM clean_offers co
LEFT JOIN offer_domain_enrichment ode
  ON ode.source = co.source AND ode.external_id = co.external_id
WHERE co.source = %s
  AND co.title IS NOT NULL
  AND COALESCE(co.description, '') <> ''
  AND NOT EXISTS (
    SELECT 1 FROM offer_skills os
    WHERE os.offer_id = co.id
    AND os.enrichment_version = 'offer_skills_v3_metier'
  )
ORDER BY co.id
"""


def identify_zero_skill_offers(conn, *, source: str) -> list[dict[str, Any]]:
    """Find offers without v3_metier skills."""
    with conn.cursor() as cursor:
        cursor.execute(IDENTIFY_ZERO_SKILL_OFFERS_SQL, (source,))
        rows = cursor.fetchall()

    return [
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="business_france")
    parser.add_argument("--dry-run", action="store_true", help="Test without persisting")
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

        # Identify offers without v3_metier
        offers = identify_zero_skill_offers(conn, source=args.source)
        print(f"Found {len(offers)} offers without v3_metier")

        if not offers:
            print("No offers to process.")
            return 0

        all_summaries = []
        total_kept = 0
        total_dropped = 0
        total_errors = 0

        for idx, offer in enumerate(offers, 1):
            content_hash = compute_offer_skills_content_hash(
                title=offer["title"], description=offer["description"]
            )
            rows, audit = build_fallback_rows(
                offer_id=offer["offer_id"],
                source=offer["source"],
                external_id=offer["external_id"],
                title=offer["title"],
                description=offer["description"],
                domain_tag=offer["domain_tag"],
                content_hash=content_hash,
            )

            written = persist_fallback_rows(conn, rows, dry_run=args.dry_run)

            total_kept += len(rows)
            total_dropped += len(audit.get("dropped", []))
            if audit.get("error"):
                total_errors += 1

            all_summaries.append(
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

            print(
                f"[{idx}/{len(offers)}] offer={offer['offer_id']} "
                f"domain={offer['domain_tag']} kept={len(rows)} dropped={len(audit.get('dropped', []))}"
                + (f" ERROR={audit['error']}" if audit.get("error") else "")
            )

        # Summary
        n_with_skills = sum(1 for s in all_summaries if s["kept"] > 0)
        avg_kept = (total_kept / len(offers)) if offers else 0.0

        summary = {
            "enrichment_version": ENRICHMENT_VERSION_FALLBACK,
            "source": args.source,
            "dry_run": args.dry_run,
            "n_offers": len(offers),
            "n_offers_with_skills": n_with_skills,
            "pct_offers_with_skills": round(100.0 * n_with_skills / len(offers), 2) if offers else 0.0,
            "kept_total": total_kept,
            "dropped_total": total_dropped,
            "errors": total_errors,
            "avg_kept_per_offer": round(avg_kept, 2),
        }

        # Write CSV
        with (OUT_DIR / "offers_processed.csv").open("w", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["offer_id", "external_id", "domain_tag", "title", "kept", "dropped", "error"],
            )
            w.writeheader()
            for s in all_summaries:
                w.writerow(s)

        (OUT_DIR / "fallback_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

        print("\n" + "=" * 60)
        print("FALLBACK EXTRACTION COMPLETE")
        print("=" * 60)
        print(f"Offers processed: {len(offers)}")
        print(f"Offers with skills: {n_with_skills} ({summary['pct_offers_with_skills']}%)")
        print(f"Skills kept: {total_kept}")
        print(f"Skills dropped: {total_dropped}")
        print(f"Errors: {total_errors}")
        print(f"Avg kept per offer: {avg_kept:.2f}")
        print(f"Outputs: {OUT_DIR}")
        print("=" * 60)

        return 0


if __name__ == "__main__":
    raise SystemExit(main())
