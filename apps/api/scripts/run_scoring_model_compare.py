#!/usr/bin/env python3
"""
Compare scoring models on selected offers.

Usage:
  PYTHONPATH=apps/api/src python3 apps/api/scripts/run_scoring_model_compare.py \
    --profile-json apps/api/fixtures/profiles/akim_guentas_matching.json \
    --offer-ids BF-AZ-0002,BF-AZ-0004,BF-237154
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import List, Dict, Any

from api.utils.inbox_catalog import load_catalog_offers
from matching import MatchingEngine
from matching.extractors import extract_profile


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-json", required=True)
    parser.add_argument("--offer-ids", required=True, help="Comma-separated offer IDs")
    parser.add_argument(
        "--models",
        default="baseline,core_penalty,hierarchical,weighted_tier",
        help="Comma-separated scoring models",
    )
    parser.add_argument("--force-vie", action="store_true")
    return parser.parse_args()


def _score_offer(engine: MatchingEngine, profile, offer: Dict[str, Any]) -> Dict[str, Any]:
    result = engine.score_offer(profile, offer)
    skills_debug = (result.match_debug or {}).get("skills", {})
    return {
        "score": result.score,
        "skills_score": skills_debug.get("score"),
        "matched": skills_debug.get("matched"),
        "missing": skills_debug.get("missing"),
        "context": {
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
        },
    }


def main() -> None:
    args = _parse_args()
    offer_ids = [oid.strip() for oid in args.offer_ids.split(",") if oid.strip()]
    models = [m.strip() for m in args.models.split(",") if m.strip()]

    profile_raw = json.loads(Path(args.profile_json).read_text())
    profile = extract_profile(profile_raw)

    os.environ["ELEVIA_CONTEXTUAL_WEIGHTING"] = "1"

    catalog = load_catalog_offers()
    by_id = {str(o.get("id")): o for o in catalog}

    print("SCORING MODEL COMPARISON")
    print("offers:", ", ".join(offer_ids))
    print("models:", ", ".join(models))
    print()

    for model in models:
        os.environ["ELEVIA_SCORING_MODEL"] = model
        engine = MatchingEngine(offers=catalog)
        print(f"MODEL: {model}")
        for oid in offer_ids:
            offer = by_id.get(oid)
            if not offer:
                print(f"  {oid}: missing")
                continue
            offer = dict(offer)
            if args.force_vie:
                offer["is_vie"] = True
            outcome = _score_offer(engine, profile, offer)
            print(
                f"  {oid} | score={outcome['score']} | skills={outcome['skills_score']} | "
                f"core_missing={len((outcome['context'].get('missing_core') or []))}"
            )
        print()


if __name__ == "__main__":
    main()
