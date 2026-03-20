#!/usr/bin/env python3
"""
Calibration sweep for core-penalty model.

Usage:
  PYTHONPATH=apps/api/src python3 apps/api/scripts/run_core_penalty_sweep.py \
    --profile-json apps/api/fixtures/profiles/akim_guentas_matching.json \
    --sample-size 20
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, List

from api.utils.inbox_catalog import load_catalog_offers
from matching import MatchingEngine
from matching.extractors import extract_profile


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-json", required=True)
    parser.add_argument("--sample-size", type=int, default=20)
    return parser.parse_args()


def _score(engine: MatchingEngine, profile, offer: Dict[str, Any]) -> Dict[str, Any]:
    result = engine.score_offer(profile, offer)
    skills_debug = (result.match_debug or {}).get("skills", {})
    context = {
        k: skills_debug.get(k)
        for k in (
            "matched_core",
            "missing_core",
            "matched_secondary",
            "missing_secondary",
            "matched_context",
            "missing_context",
        )
        if k in skills_debug
    }
    return {
        "score": result.score,
        "skills_score": skills_debug.get("score"),
        "context": context,
    }


def _select_offers(catalog: List[Dict[str, Any]], profile, sample_size: int) -> List[Dict[str, Any]]:
    os.environ["ELEVIA_CONTEXTUAL_WEIGHTING"] = "1"
    os.environ["ELEVIA_SCORING_MODEL"] = "baseline"
    engine = MatchingEngine(offers=catalog)

    selected = []
    for offer in catalog:
        if offer.get("is_vie") is not True:
            continue
        outcome = _score(engine, profile, offer)
        ctx = outcome["context"] or {}
        core_total = len(ctx.get("matched_core") or []) + len(ctx.get("missing_core") or [])
        if core_total == 0:
            continue
        selected.append(offer)
        if len(selected) >= sample_size:
            break
    return selected


def main() -> None:
    args = _parse_args()
    profile_raw = json.loads(Path(args.profile_json).read_text())
    profile = extract_profile(profile_raw)

    catalog = load_catalog_offers()
    selected = _select_offers(catalog, profile, args.sample_size)
    print(f"Selected offers: {len(selected)}")

    # Baseline scores
    os.environ["ELEVIA_CONTEXTUAL_WEIGHTING"] = "1"
    os.environ["ELEVIA_SCORING_MODEL"] = "baseline"
    baseline_engine = MatchingEngine(offers=catalog)
    baseline_scores = {}
    baseline_core_missing = {}
    baseline_clusters = {}
    for offer in selected:
        outcome = _score(baseline_engine, profile, offer)
        ctx = outcome["context"] or {}
        missing_core = len(ctx.get("missing_core") or [])
        baseline_scores[offer["id"]] = outcome["score"]
        baseline_core_missing[offer["id"]] = missing_core
        baseline_clusters[offer["id"]] = offer.get("offer_cluster")

    penalty_factors = [0.02, 0.03, 0.04, 0.05]
    penalty_caps = [0.12, 0.15, 0.18]

    print("\nCALIBRATION GRID")
    print("factor,cap,avg_shift,max_penalty,avg_shift_by_cluster")

    for factor in penalty_factors:
        for cap in penalty_caps:
            os.environ["ELEVIA_SCORING_MODEL"] = "core_penalty"
            os.environ["ELEVIA_CORE_PENALTY_FACTOR"] = str(factor)
            os.environ["ELEVIA_CORE_PENALTY_CAP"] = str(cap)
            engine = MatchingEngine(offers=catalog)

            total_shift = 0.0
            max_penalty = 0.0
            cluster_shift: Dict[str, List[float]] = defaultdict(list)

            print(f"\nCONFIG factor={factor} cap={cap}")
            print("offer_id,cluster,missing_core,baseline,adjusted")
            for offer in selected:
                oid = offer["id"]
                baseline = baseline_scores[oid]
                missing_core = baseline_core_missing[oid]
                adjusted = _score(engine, profile, offer)["score"]
                shift = adjusted - baseline
                total_shift += shift
                max_penalty = max(max_penalty, baseline - adjusted)
                cluster_shift[str(baseline_clusters[oid])].append(shift)
                print(f"{oid},{baseline_clusters[oid]},{missing_core},{baseline},{adjusted}")

            avg_shift = total_shift / max(len(selected), 1)
            avg_by_cluster = {k: round(sum(v) / max(len(v), 1), 2) for k, v in cluster_shift.items()}
            print(f"summary,avg_shift={round(avg_shift,2)},max_penalty={round(max_penalty,2)},by_cluster={avg_by_cluster}")


if __name__ == "__main__":
    main()
