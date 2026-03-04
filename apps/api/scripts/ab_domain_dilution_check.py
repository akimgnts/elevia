#!/usr/bin/env python3
"""
ab_domain_dilution_check.py — Domain URI Top-K rarity filter A/B evidence.

Three-way comparison for 20 DATA_IT VIE offers:
  A) ESCO-only:       no domain URIs (denominator = only ESCO URIs)
  B) TopK=5 (new):   Top-K rarity filter active (denominator = ESCO + ≤5 domain)
  C) NoFilter=50:     no effective filter (denominator = ESCO + all domain URIs)

Asserts: score_B >= score_C  (filter reduces dilution)

Saves: audit/golden/domain_dilution_ab_20.json

Usage:
    cd /Users/akimguentas/Dev/elevia-compass
    python3 apps/api/scripts/ab_domain_dilution_check.py
"""
from __future__ import annotations

import copy
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent.parent.parent
API_SRC = REPO_ROOT / "apps" / "api" / "src"
sys.path.insert(0, str(API_SRC))

# ── Config ────────────────────────────────────────────────────────────────────
TOPK_NEW = int(os.getenv("ELEVIA_OFFER_DOMAIN_TOPK", "5"))
TOPK_OLD = 50   # simulates pre-fix behavior (accept up to 50 domain tokens)
TARGET_CLUSTER = "DATA_IT"
TARGET_COUNT = 20
OUTPUT_PATH = REPO_ROOT / "audit" / "golden" / "domain_dilution_ab_20.json"

# Fixed profile for reproducibility (Marie Dupont — Data Analyst)
PROFILE_FIXTURE = str(REPO_ROOT / "apps" / "api" / "fixtures" / "cv" / "cv_fixture_v0.txt")


def _esco_only_uris(offer: dict) -> list[str]:
    return [u for u in (offer.get("skills_uri") or []) if u.startswith("http://data.europa.eu/esco/")]


def _rebuild_offer_with_topk(offer: dict, k: int, apply_fn) -> dict:
    """Strip existing domain URIs and re-apply with the given K value."""
    rebuilt = copy.deepcopy(offer)
    rebuilt["skills_uri"] = _esco_only_uris(rebuilt)
    rebuilt["domain_uris"] = []
    rebuilt["domain_uri_count"] = 0
    os.environ["ELEVIA_OFFER_DOMAIN_TOPK"] = str(k)
    apply_fn(rebuilt)
    return rebuilt


def main() -> None:
    print("=" * 60)
    print("DOMAIN URI DILUTION — A/B CHECK (3-way)")
    print(f"TopK-new={TOPK_NEW}  TopK-old={TOPK_OLD}  Cluster={TARGET_CLUSTER}")
    print("=" * 60)

    from api.utils.inbox_catalog import load_catalog_offers
    from compass.offer_canonicalization import _apply_domain_uris
    from compass.canonical_pipeline import run_cv_pipeline
    from matching.matching_v1 import MatchingEngine
    from matching.extractors import extract_profile

    # ── Load profile ──────────────────────────────────────────────────────────
    print(f"\n[PROFILE] Parsing {PROFILE_FIXTURE} ...")
    if not Path(PROFILE_FIXTURE).exists():
        print("[ERROR] Profile fixture not found.")
        sys.exit(1)

    with open(PROFILE_FIXTURE, encoding="utf-8") as f:
        cv_text = f.read()

    pipeline_result = run_cv_pipeline(cv_text)
    br = pipeline_result.baseline_result or {}
    profile_sub = br.get("profile") or {}
    skills_uri = profile_sub.get("skills_uri") or []
    domain_uris: list[str] = []  # baseline only — domain URIs separate

    profile_dict = {
        "profile_id": "marie-dupont-fixture",
        "skills_uri": skills_uri,
        "domain_uris": domain_uris,
    }
    extracted = extract_profile(profile_dict)
    print(f"[PROFILE] esco_uri={len(skills_uri)}, domain_uris={len(domain_uris)}")

    # ── Load offers ───────────────────────────────────────────────────────────
    print(f"\n[OFFERS] Loading catalog offers (cluster={TARGET_CLUSTER}) ...")
    all_offers = load_catalog_offers()

    # Filter to DATA_IT VIE offers with active domain URIs
    data_it_vie = [
        o for o in all_offers
        if o.get("offer_cluster") == TARGET_CLUSTER and o.get("is_vie") is True
    ]

    # Prefer offers that have domain URIs (active enrichment)
    with_domain = [o for o in data_it_vie if o.get("domain_uri_count", 0) > 0]
    sample = (with_domain if with_domain else data_it_vie)[:TARGET_COUNT]

    if not sample:
        print("[ERROR] No DATA_IT VIE offers available. Run enrichment first.")
        sys.exit(1)

    print(f"[OFFERS] Using {len(sample)} VIE offers ({len(with_domain)} with active domain URIs)")

    # ── Three-way scoring ─────────────────────────────────────────────────────
    results = []
    delta_b_vs_c = []  # score_topk5 - score_nofiler

    print(f"\n{'Offer ID':22s}  {'ESCO-only':>9}  {'TopK='+str(TOPK_NEW):>9}  {'NoFilt='+str(TOPK_OLD):>11}  {'Δ(B-C)':>7}  domain_cnt")
    print("-" * 85)

    for offer in sample:
        offer_id = offer.get("id", "unknown")

        # A — ESCO-only (no domain URIs)
        offer_a = copy.deepcopy(offer)
        offer_a["skills_uri"] = _esco_only_uris(offer_a)
        offer_a["domain_uris"] = []
        offer_a["domain_uri_count"] = 0
        score_a = MatchingEngine([offer_a]).score_offer(extracted, offer_a).score

        # B — Top-K=5 (new behavior)
        offer_b = _rebuild_offer_with_topk(offer, TOPK_NEW, _apply_domain_uris)
        score_b = MatchingEngine([offer_b]).score_offer(extracted, offer_b).score
        cnt_b = offer_b.get("domain_uri_count", 0)

        # C — No filter (old behavior, K=50)
        offer_c = _rebuild_offer_with_topk(offer, TOPK_OLD, _apply_domain_uris)
        score_c = MatchingEngine([offer_c]).score_offer(extracted, offer_c).score
        cnt_c = offer_c.get("domain_uri_count", 0)

        delta = round(score_b - score_c, 1)
        delta_b_vs_c.append(delta)

        direction = "▲" if delta > 0 else ("▼" if delta < 0 else "=")
        print(
            f"  {offer_id:20s}  {score_a:7.1f}    {score_b:7.1f}    {score_c:9.1f}  "
            f"  {direction}{abs(delta):4.1f}  {cnt_b}→{cnt_c}"
        )

        results.append({
            "offer_id": offer_id,
            "score_esco_only": score_a,
            "score_topk5": score_b,
            "score_nofilter": score_c,
            "delta_topk_vs_nofilter": delta,
            "domain_uri_count_topk": cnt_b,
            "domain_uri_count_nofilter": cnt_c,
            "esco_uri_count": len(_esco_only_uris(offer)),
            "domain_uris_topk": offer_b.get("domain_uris", []),
        })

    # ── Summary ───────────────────────────────────────────────────────────────
    avg_delta = sum(delta_b_vs_c) / len(delta_b_vs_c) if delta_b_vs_c else 0
    improved = sum(1 for d in delta_b_vs_c if d > 0)
    regressed = sum(1 for d in delta_b_vs_c if d < 0)
    neutral = sum(1 for d in delta_b_vs_c if d == 0)

    print("\n" + "=" * 60)
    print("SUMMARY  (score_topk5 vs score_nofilter)")
    print("=" * 60)
    print(f"Offers:          {len(results)}")
    print(f"TopK improved:   {improved}")
    print(f"TopK regressed:  {regressed}")
    print(f"Neutral:         {neutral}")
    print(f"Avg Δ(B-C):      {avg_delta:+.2f}")
    print(f"Conclusion:      {'✅ Filter helps or neutral' if avg_delta >= 0 else '⚠ Filter regresses (unexpected)'}")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "topk_new": TOPK_NEW,
        "topk_old_simulation": TOPK_OLD,
        "cluster": TARGET_CLUSTER,
        "profile": "cv_fixture_v0.txt (Marie Dupont — Data Analyst)",
        "profile_esco_uri_count": len(skills_uri),
        "comparison": {
            "A": "ESCO-only (no domain URIs)",
            "B": f"Top-K={TOPK_NEW} (new filter)",
            "C": f"No-filter K={TOPK_OLD} (old behavior)",
        },
        "summary": {
            "offers_checked": len(results),
            "topk_improved_vs_nofilter": improved,
            "topk_regressed_vs_nofilter": regressed,
            "neutral": neutral,
            "avg_delta_topk_vs_nofilter": round(avg_delta, 2),
        },
        "results": results,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[SAVED] {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
