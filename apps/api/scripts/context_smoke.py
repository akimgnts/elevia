#!/usr/bin/env python3
"""
context_smoke.py — Deterministic context layer smoke runner.

Usage:
    python apps/api/scripts/context_smoke.py
    python apps/api/scripts/context_smoke.py --profile-id akim_guentas_v0
    python apps/api/scripts/context_smoke.py --offers-file apps/api/fixtures/offers/vie_catalog.json
    python apps/api/scripts/context_smoke.py --cv-text "Expert SQL, Python, Power BI."

Output (JSON):
    {
      "has_cv_text": true/false,
      "stakeholder_signal": "HIGH"|"MEDIUM"|"UNKNOWN",
      "profile_tools_signals": [...],
      "primary_role_type_distribution": {"BI_REPORTING": 3, "DATA_ENGINEERING": 2, ...},
      "fit_summary_distinct_count": N,
      "responsibilities_min_count": M,
      "responsibilities_zero_count": K  // must be 0
    }

DONE criteria:
    - profile_tools_signals non-empty (with or without CV text)
    - stakeholder friction NOT in likely_frictions when has_cv_text=False
    - responsibilities_min_count >= 1
    - fit_summary_distinct_count >= 4 (for 5+ diverse offers)
    - primary_role_type distribution not collapsed to one value
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add src to path
_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_API_SRC = _REPO_ROOT / "apps" / "api" / "src"
sys.path.insert(0, str(_API_SRC))

from context.extractors import (
    extract_context_fit,
    extract_offer_context,
    extract_profile_context,
)

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
_PROFILE_DIR = _FIXTURES_DIR / "profiles"
_OFFERS_FILE = _FIXTURES_DIR / "offers" / "vie_catalog.json"


def _load_profile(profile_id: str) -> Optional[Dict[str, Any]]:
    for suffix in ("", "_matching"):
        candidate = _PROFILE_DIR / f"{profile_id}{suffix}.json"
        if candidate.exists():
            return json.loads(candidate.read_text())
    # Try without suffix stripping
    for f in _PROFILE_DIR.glob("*.json"):
        data = json.loads(f.read_text())
        if data.get("id") == profile_id:
            return data
    return None


def _load_offers(offers_file: str) -> List[Dict[str, Any]]:
    path = Path(offers_file)
    if not path.exists():
        print(f"[smoke] Offers file not found: {path}", file=sys.stderr)
        return []
    return json.loads(path.read_text())


def run_smoke(
    profile_id: str = "akim_guentas_v0",
    offers_file: str = str(_OFFERS_FILE),
    cv_text: Optional[str] = None,
    top_n: int = 5,
) -> Dict[str, Any]:
    # ── Load profile
    profile_data = _load_profile(profile_id)
    if not profile_data:
        print(f"[smoke] WARNING: profile {profile_id!r} not found in fixtures.", file=sys.stderr)
        profile_data = {"id": profile_id, "skills": []}

    # ── Build ProfileContext
    prof_ctx = extract_profile_context(
        profile_id=profile_id,
        cv_text_cleaned=cv_text,
        profile=profile_data,
    )

    # ── Load offers (take first top_n)
    offers = _load_offers(offers_file)
    if not offers:
        print("[smoke] No offers loaded — aborting.", file=sys.stderr)
        return {}

    sample_offers = offers[:top_n]

    # ── Run OfferContext + ContextFit for each
    fit_summaries: List[Optional[str]] = []
    role_type_counts: Dict[str, int] = {}
    resp_counts: List[int] = []
    friction_stk_found: List[str] = []

    for offer in sample_offers:
        desc = offer.get("description") or ""
        offer_id = offer.get("id", "unknown")

        offer_ctx = extract_offer_context(offer_id, desc)
        fit = extract_context_fit(
            prof_ctx,
            offer_ctx,
            matched_skills=list(set(offer.get("skills", [])) & {s.lower() for s in prof_ctx.dominant_strengths}),
            missing_skills=[],
        )

        fit_summaries.append(fit.fit_summary)

        prt = offer_ctx.primary_role_type
        role_type_counts[prt] = role_type_counts.get(prt, 0) + 1

        resp_counts.append(len(offer_ctx.responsibilities))

        stk_frictions = [f for f in fit.likely_frictions if "parties prenantes" in f.lower()]
        if stk_frictions:
            friction_stk_found.append(offer_id)

    distinct_summaries = len(set(s for s in fit_summaries if s))
    min_resp = min(resp_counts) if resp_counts else 0
    zero_resp = sum(1 for c in resp_counts if c == 0)

    result = {
        "has_cv_text": prof_ctx.has_cv_text,
        "stakeholder_signal": prof_ctx.experience_signals.stakeholder_signal,
        "profile_tools_signals": prof_ctx.profile_tools_signals,
        "primary_role_type_distribution": role_type_counts,
        "fit_summary_distinct_count": distinct_summaries,
        "responsibilities_min_count": min_resp,
        "responsibilities_zero_count": zero_resp,
        "_debug": {
            "profile_id": profile_id,
            "offers_sampled": len(sample_offers),
            "fit_summaries": fit_summaries,
            "stakeholder_frictions_found_in": friction_stk_found,
        },
    }

    # ── OK/KO verdict
    ok = (
        len(prof_ctx.profile_tools_signals) > 0
        and zero_resp == 0
        and distinct_summaries >= min(4, len(sample_offers) - 1)
        and len(role_type_counts) >= min(2, len(sample_offers))
    )
    result["verdict"] = "OK" if ok else "KO"

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Context layer smoke runner")
    parser.add_argument("--profile-id", default="akim_guentas_v0", help="Profile fixture ID")
    parser.add_argument("--offers-file", default=str(_OFFERS_FILE), help="Path to offers JSON")
    parser.add_argument("--cv-text", default=None, help="Inline CV text (overrides fixture)")
    parser.add_argument("--top-n", type=int, default=5, help="Number of offers to process")
    args = parser.parse_args()

    result = run_smoke(
        profile_id=args.profile_id,
        offers_file=args.offers_file,
        cv_text=args.cv_text,
        top_n=args.top_n,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
