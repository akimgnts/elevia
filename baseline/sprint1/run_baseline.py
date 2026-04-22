#!/usr/bin/env python3
"""
Sprint 1 baseline runner.

Reads frozen inputs from inputs/ and runs the current product pipeline
(matching.MatchingEngine + matching.extractors.extract_profile) unchanged.

Produces outputs/<profile_id>.json and manifest.json. No scoring-core
modification. No improvement. Only measurement of the current behavior.

Reproducibility: frozen profile panel + frozen offer set + pinned commit
captured in manifest.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASELINE_DIR = Path(__file__).resolve().parent
API_SRC = BASELINE_DIR.parent.parent / "apps" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from matching.matching_v1 import MatchingEngine  # noqa: E402
from matching.extractors import extract_profile  # noqa: E402


PROFILES_DIR = BASELINE_DIR / "inputs" / "profiles"
OFFERS_FILE = BASELINE_DIR / "inputs" / "offers.json"
OUTPUTS_DIR = BASELINE_DIR / "outputs"
MANIFEST_FILE = BASELINE_DIR / "manifest.json"


def _git_commit() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=BASELINE_DIR, stderr=subprocess.DEVNULL
        )
        return out.decode("ascii").strip()
    except Exception:
        return "unknown"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _offer_by_id(offers, oid: str):
    for o in offers:
        if str(o.get("id")) == str(oid):
            return o
    return None


def _extract_offer_skill_labels(offer) -> list:
    skills = offer.get("skills") or offer.get("skills_display") or []
    out = []
    for s in skills:
        if isinstance(s, dict):
            lbl = s.get("label") or s.get("surface") or ""
            if lbl:
                out.append(str(lbl))
        elif isinstance(s, str):
            out.append(s)
    return out


def _result_to_dict(res, offer: dict) -> dict:
    matched_labels = []
    missing_labels = []
    if res.match_debug:
        matched_labels = list(res.match_debug.get("skills", {}).get("matched", []))
        missing_labels = list(res.match_debug.get("skills", {}).get("missing", []))
    return {
        "offer_id": res.offer_id,
        "offer_title": offer.get("title"),
        "offer_country": offer.get("country"),
        "offer_source": offer.get("source"),
        "score": res.score,
        "breakdown": res.breakdown,
        "reasons": res.reasons,
        "matched_skills": matched_labels,
        "missing_skills": missing_labels,
        "offer_skills_raw": _extract_offer_skill_labels(offer),
        "score_is_partial": getattr(res, "score_is_partial", False),
    }


def run_profile(profile_data: dict, offers: list) -> dict:
    engine = MatchingEngine(offers=offers)

    # Path A: product /v1/match behavior — strict threshold (>=80) applied.
    output = engine.match(profile=profile_data, offers=offers)
    top10_strict = [
        _result_to_dict(res, _offer_by_id(offers, res.offer_id) or {})
        for res in output.results[:10]
    ]

    # Path B: product /inbox behavior — score_offer loop, no threshold, ranked.
    # Both paths are live product code; neither modifies scoring logic.
    extracted = extract_profile(profile_data)
    scored = []
    for offer in offers:
        res = engine.score_offer(extracted, offer)
        scored.append(res)
    scored.sort(key=lambda r: r.score, reverse=True)
    top10_unthresholded = [
        _result_to_dict(res, _offer_by_id(offers, res.offer_id) or {})
        for res in scored[:10]
    ]

    return {
        "profile_id": profile_data.get("profile_id"),
        "total_candidate_offers": len(offers),
        "results_above_threshold": len(output.results),
        "threshold": output.threshold,
        "message": output.message,
        "profile_input": {
            "skills_input": profile_data.get("skills") or [],
            "languages": profile_data.get("languages") or [],
            "education_level": profile_data.get("education_level"),
            "nationality": profile_data.get("nationality"),
            "age": profile_data.get("age"),
            "years_of_experience": profile_data.get("years_of_experience"),
        },
        "profile_extracted": {
            "skills_count": len(getattr(extracted, "skills", []) or []),
            "skills": list(getattr(extracted, "skills", []) or [])[:50],
            "skills_uri_count": int(getattr(extracted, "skills_uri_count", 0) or 0),
            "matching_skills_count": int(getattr(extracted, "matching_skills_count", 0) or 0),
            "capabilities_count": int(getattr(extracted, "capabilities_count", 0) or 0),
            "skill_source": getattr(extracted, "skill_source", None),
            "languages_count": len(getattr(extracted, "languages", []) or []),
            "education_level": getattr(extracted, "education_level", None),
        },
        "top10_strict_threshold_80": top10_strict,
        "top10_unthresholded_ranked": top10_unthresholded,
    }


def main() -> int:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    offers = json.loads(OFFERS_FILE.read_text(encoding="utf-8"))
    profile_files = sorted(PROFILES_DIR.glob("profile_*.json"))

    summaries = []
    for pf in profile_files:
        profile_data = json.loads(pf.read_text(encoding="utf-8"))
        pid = profile_data.get("profile_id") or pf.stem
        result = run_profile(profile_data, offers)
        out_path = OUTPUTS_DIR / f"{pf.stem}.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        un = result["top10_unthresholded_ranked"]
        summaries.append({
            "profile_file": pf.name,
            "profile_id": pid,
            "results_above_threshold": result["results_above_threshold"],
            "best_unthresholded_score": un[0]["score"] if un else None,
            "worst_unthresholded_top10_score": un[-1]["score"] if un else None,
        })
        print(
            f"[ok] {pf.name} → strict>=80: {result['results_above_threshold']} | "
            f"unthresholded top1: {un[0]['score'] if un else None}"
        )

    manifest = {
        "sprint": "sprint1_baseline",
        "generated_at_utc": _utc_now(),
        "git_commit": _git_commit(),
        "python_version": sys.version.split()[0],
        "env_flags": {
            "ELEVIA_FILTER_GENERIC_URIS": os.getenv("ELEVIA_FILTER_GENERIC_URIS", "unset"),
            "ELEVIA_PROMOTE_ESCO": os.getenv("ELEVIA_PROMOTE_ESCO", "unset"),
            "ELEVIA_DEBUG_MATCHING": os.getenv("ELEVIA_DEBUG_MATCHING", "unset"),
        },
        "entrypoints": {
            "profile_extraction": "apps/api/src/matching/extractors.py::extract_profile",
            "scoring_engine": "apps/api/src/matching/matching_v1.py::MatchingEngine.match",
            "catalog_loader_prod_path": "apps/api/src/api/utils/inbox_catalog.py::load_catalog_offers (unused locally: DB unreachable)",
        },
        "inputs": {
            "profiles_dir": "inputs/profiles/",
            "profiles": [pf.name for pf in profile_files],
            "offers_file": "inputs/offers.json",
            "offer_count": len(offers),
            "offer_sources": {
                "golden_synthetic_VIE_001_to_020": 20,
                "vie_catalog_fixtures": 15,
            },
        },
        "summaries": summaries,
        "hypotheses_and_limits": [
            "DATABASE_URL in apps/api/.env is malformed (double '@' produces unresolvable host) — real Business France corpus not reachable from this local environment. Baseline uses the two largest local fixture files flowing through the same MatchingEngine path.",
            "Golden offers originally exposed 'skills_required' / 'languages_required' (not 'skills' / 'languages' that the engine expects); keys were renamed losslessly in the frozen input file — no value was altered.",
            "Profile panel missing one HR/ops profile and one explicit business+data hybrid; 5/7 archetypes covered with existing assets.",
            "ESCO normalization pass (normalize_offers_to_uris) NOT applied on fixtures; the engine derives URIs on-the-fly via _map_offer_skills_to_uris (same fallback path used when precomputed URIs are absent).",
            "Threshold = 80 enforced by product code — offers below this bar are correctly excluded; 'results_above_threshold' reflects actual product behavior.",
        ],
    }
    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[manifest] {MANIFEST_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
