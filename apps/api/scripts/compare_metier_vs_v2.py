#!/usr/bin/env python3
"""compare_metier_vs_v2 — side-by-side audit of v2 vs v3 metier extraction.

Reads only offers that have v3 rows (the sample), pulls v2 rows for the same
offer_ids, and emits comparison metrics:
  - avg skills per offer (v2 vs v3)
  - % offers with >= 3 skills (v2 vs v3)
  - noise frequency (top labels in v2 vs CORE_METIER share in v3)
  - domain coherence (top canonical_ids per domain side-by-side)

Usage:
    DATABASE_URL=postgresql://... python3 apps/api/scripts/compare_metier_vs_v2.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

V2_VERSION = "offer_skills_v2"
V3_VERSION = "offer_skills_v3_metier"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y_%m_%d")


OUT_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "audit"
    / f"metier_sample_{_utc_stamp()}"
)


SAMPLE_OFFER_IDS_SQL = """
SELECT DISTINCT offer_id FROM offer_skills WHERE enrichment_version = %s
"""

V2_ROWS_SQL = """
SELECT os.offer_id, ode.domain_tag, os.canonical_id, os.label, os.importance_level
FROM offer_skills os
LEFT JOIN clean_offers co ON co.id = os.offer_id
LEFT JOIN offer_domain_enrichment ode
  ON ode.source = co.source AND ode.external_id = co.external_id
WHERE os.enrichment_version = %s
  AND os.offer_id = ANY(%s)
"""

V3_ROWS_SQL = """
SELECT os.offer_id, ode.domain_tag, os.canonical_id, os.label, os.skill_type, os.evidence
FROM offer_skills os
LEFT JOIN clean_offers co ON co.id = os.offer_id
LEFT JOIN offer_domain_enrichment ode
  ON ode.source = co.source AND ode.external_id = co.external_id
WHERE os.enrichment_version = %s
  AND os.offer_id = ANY(%s)
"""


def _bucket(rows: list[tuple], *, key_idx: int = 0) -> dict[Any, list[tuple]]:
    buckets: dict[Any, list[tuple]] = {}
    for r in rows:
        buckets.setdefault(r[key_idx], []).append(r)
    return buckets


def _topn(counter: dict[str, int], n: int = 5) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def main() -> int:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    import psycopg

    with psycopg.connect(database_url, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute(SAMPLE_OFFER_IDS_SQL, (V3_VERSION,))
            offer_ids = [int(r[0]) for r in cur.fetchall()]
            if not offer_ids:
                print(f"No rows under enrichment_version='{V3_VERSION}'. Run sample_metier_extraction.py first.")
                return 1
            cur.execute(V2_ROWS_SQL, (V2_VERSION, offer_ids))
            v2_rows = cur.fetchall()
            cur.execute(V3_ROWS_SQL, (V3_VERSION, offer_ids))
            v3_rows = cur.fetchall()

    # Per-offer counts
    v2_by_offer = _bucket(v2_rows, key_idx=0)
    v3_by_offer = _bucket(v3_rows, key_idx=0)

    n_offers = len(offer_ids)
    v2_counts = [len(v2_by_offer.get(oid, [])) for oid in offer_ids]
    v3_counts = [len(v3_by_offer.get(oid, [])) for oid in offer_ids]

    def _avg(xs: list[int]) -> float:
        return round(sum(xs) / len(xs), 2) if xs else 0.0

    def _pct_at_least(xs: list[int], threshold: int) -> float:
        if not xs:
            return 0.0
        return round(sum(1 for x in xs if x >= threshold) * 100.0 / len(xs), 2)

    # Top labels (noise indicator: most-frequent labels in v2 are likely the generics)
    v2_label_freq: dict[str, int] = {}
    for r in v2_rows:
        label = (r[3] or "").strip().lower()
        if label:
            v2_label_freq[label] = v2_label_freq.get(label, 0) + 1
    v3_label_freq: dict[str, int] = {}
    v3_type_freq: dict[str, int] = {}
    for r in v3_rows:
        label = (r[3] or "").strip().lower()
        skill_type = r[4] or ""
        if label:
            v3_label_freq[label] = v3_label_freq.get(label, 0) + 1
        if skill_type:
            v3_type_freq[skill_type] = v3_type_freq.get(skill_type, 0) + 1

    # Per-domain top canonical_ids
    def _by_domain(rows: list[tuple], *, label_idx: int) -> dict[str, dict[str, int]]:
        buckets: dict[str, dict[str, int]] = {}
        for r in rows:
            domain = r[1] or "(none)"
            label = r[label_idx] or ""
            if not label:
                continue
            buckets.setdefault(domain, {})
            buckets[domain][label] = buckets[domain].get(label, 0) + 1
        return buckets

    v2_per_domain = _by_domain(v2_rows, label_idx=3)
    v3_per_domain = _by_domain(v3_rows, label_idx=3)
    all_domains = sorted(set(v2_per_domain) | set(v3_per_domain))

    # Write CSVs
    domain_csv = []
    for domain in all_domains:
        v2_top = _topn(v2_per_domain.get(domain, {}), 5)
        v3_top = _topn(v3_per_domain.get(domain, {}), 5)
        for rank in range(max(len(v2_top), len(v3_top))):
            v2_label, v2_n = (v2_top[rank] if rank < len(v2_top) else ("", 0))
            v3_label, v3_n = (v3_top[rank] if rank < len(v3_top) else ("", 0))
            domain_csv.append(
                {
                    "domain_tag": domain,
                    "rank": rank + 1,
                    "v2_label": v2_label,
                    "v2_n": v2_n,
                    "v3_label": v3_label,
                    "v3_n": v3_n,
                }
            )

    with (OUT_DIR / "compare_top_labels_per_domain.csv").open("w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["domain_tag", "rank", "v2_label", "v2_n", "v3_label", "v3_n"]
        )
        w.writeheader()
        w.writerows(domain_csv)

    # Per-offer comparison rows
    offer_compare_csv = []
    for oid in offer_ids:
        v2_n = len(v2_by_offer.get(oid, []))
        v3_n = len(v3_by_offer.get(oid, []))
        v3_core = sum(1 for r in v3_by_offer.get(oid, []) if r[4] == "CORE_METIER")
        v3_tool = sum(1 for r in v3_by_offer.get(oid, []) if r[4] == "TOOL")
        v3_context = sum(1 for r in v3_by_offer.get(oid, []) if r[4] == "CONTEXT")
        v3_noise = sum(1 for r in v3_by_offer.get(oid, []) if r[4] == "NOISE")
        domain = ""
        if v3_by_offer.get(oid):
            domain = v3_by_offer[oid][0][1] or ""
        elif v2_by_offer.get(oid):
            domain = v2_by_offer[oid][0][1] or ""
        offer_compare_csv.append(
            {
                "offer_id": oid,
                "domain_tag": domain,
                "v2_skills": v2_n,
                "v3_skills": v3_n,
                "v3_core_metier": v3_core,
                "v3_tool": v3_tool,
                "v3_context": v3_context,
                "v3_noise": v3_noise,
            }
        )
    with (OUT_DIR / "compare_per_offer.csv").open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "offer_id", "domain_tag", "v2_skills", "v3_skills",
                "v3_core_metier", "v3_tool", "v3_context", "v3_noise",
            ],
        )
        w.writeheader()
        w.writerows(offer_compare_csv)

    # Headline metrics
    metrics = {
        "n_offers_compared": n_offers,
        "v2": {
            "avg_skills_per_offer": _avg(v2_counts),
            "pct_offers_with_3_or_more": _pct_at_least(v2_counts, 3),
            "min_skills": min(v2_counts) if v2_counts else 0,
            "max_skills": max(v2_counts) if v2_counts else 0,
            "top_labels": _topn(v2_label_freq, 10),
        },
        "v3_metier": {
            "avg_skills_per_offer": _avg(v3_counts),
            "pct_offers_with_3_or_more": _pct_at_least(v3_counts, 3),
            "min_skills": min(v3_counts) if v3_counts else 0,
            "max_skills": max(v3_counts) if v3_counts else 0,
            "top_labels": _topn(v3_label_freq, 10),
            "skill_type_breakdown": v3_type_freq,
        },
        "deltas": {
            "avg_skills_delta": round(_avg(v3_counts) - _avg(v2_counts), 2),
            "pct_3_plus_delta": round(
                _pct_at_least(v3_counts, 3) - _pct_at_least(v2_counts, 3), 2
            ),
        },
    }
    (OUT_DIR / "compare_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

    print(json.dumps(metrics, indent=2))
    print(f"\nOutputs in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
