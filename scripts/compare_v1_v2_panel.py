"""compare_v1_v2_panel — A/B comparison script for fit_score_v2 shadow.

Calls /api/inbox twice (flag OFF, flag ON) for the same profile and emits a
JSON + markdown report with: top10 lists, distributions, overlap, alignment ratio.

Usage:
    PYTHONPATH=apps/api/src:apps/api apps/api/.venv/bin/python \
        scripts/compare_v1_v2_panel.py --profile apps/api/fixtures/profile_demo.json

NO ranking change is expected — this script verifies the invariant.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from fastapi.testclient import TestClient  # noqa: E402

from api.main import app  # noqa: E402


def _post_inbox(client: TestClient, profile: Dict[str, Any], *, flag: str, limit: int) -> Dict[str, Any]:
    prev = os.environ.get("ELEVIA_FIT_SCORE_V2_SHADOW")
    os.environ["ELEVIA_FIT_SCORE_V2_SHADOW"] = flag
    try:
        resp = client.post(
            "/inbox",
            json={
                "profile_id": profile.get("id") or "compare-script",
                "profile": profile,
                "min_score": 0,
                "limit": limit,
            },
        )
    finally:
        if prev is None:
            os.environ.pop("ELEVIA_FIT_SCORE_V2_SHADOW", None)
        else:
            os.environ["ELEVIA_FIT_SCORE_V2_SHADOW"] = prev
    resp.raise_for_status()
    return resp.json()


def _percentiles(values: List[int]) -> Dict[str, float]:
    if not values:
        return {"min": 0, "p50": 0, "p90": 0, "max": 0, "mean": 0.0}
    sv = sorted(values)
    return {
        "min": min(sv),
        "p50": statistics.median(sv),
        "p90": sv[max(0, int(0.9 * len(sv)) - 1)],
        "max": max(sv),
        "mean": round(statistics.fmean(sv), 2),
    }


def _aligned_ratio(items: List[Dict[str, Any]]) -> float:
    if not items:
        return 0.0
    aligned = sum(1 for i in items if i.get("domain_affinity") == "aligned")
    return round(aligned / len(items), 4)


def _top10(items: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    sorted_items = sorted(
        items,
        key=lambda i: (i.get(key) is None, -(i.get(key) or 0)),
    )[:10]
    return [
        {
            "offer_id": i.get("offer_id"),
            "title": i.get("title"),
            "score_v1": i.get("score"),
            "fit_score_v2": i.get("fit_score"),
            "preference_score": i.get("preference_score"),
            "domain_affinity": i.get("domain_affinity"),
        }
        for i in sorted_items
    ]


def _build_report(profile_id: str, off: Dict[str, Any], on: Dict[str, Any]) -> Dict[str, Any]:
    items_off = off.get("items", [])
    items_on = on.get("items", [])

    scores_v1_off = [i.get("score") for i in items_off if isinstance(i.get("score"), int)]
    scores_v1_on = [i.get("score") for i in items_on if isinstance(i.get("score"), int)]
    fit_v2 = [i.get("fit_score") for i in items_on if isinstance(i.get("fit_score"), int)]
    pref_v2 = [i.get("preference_score") for i in items_on if isinstance(i.get("preference_score"), int)]

    order_off = [i.get("offer_id") for i in items_off]
    order_on = [i.get("offer_id") for i in items_on]
    ranking_unchanged = order_off == order_on
    v1_score_unchanged = (
        {i.get("offer_id"): i.get("score") for i in items_off}
        == {i.get("offer_id"): i.get("score") for i in items_on}
    )

    top10_v1 = _top10(items_on, "score")
    top10_v2 = _top10(items_on, "fit_score")
    overlap = len(
        {x["offer_id"] for x in top10_v1} & {x["offer_id"] for x in top10_v2}
    )

    return {
        "profile_id": profile_id,
        "offer_count": len(items_on),
        "ranking_unchanged_with_flag_on": ranking_unchanged,
        "v1_score_unchanged_with_flag_on": v1_score_unchanged,
        "domain_aligned_ratio": {
            "v1_off": _aligned_ratio(items_off),
            "v2_on": _aligned_ratio(items_on),
        },
        "score_distribution_v1": _percentiles(scores_v1_on),
        "fit_score_v2_distribution": _percentiles(fit_v2),
        "preference_score_v2_distribution": _percentiles(pref_v2),
        "top10_v1_by_score": top10_v1,
        "top10_v2_by_fit_score": top10_v2,
        "top10_overlap_count": overlap,
        "fit_score_v2_populated_count": len(fit_v2),
        "preference_score_v2_populated_count": len(pref_v2),
    }


def _to_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# Fit Score V2 Shadow — Compare Report (`{report['profile_id']}`)\n")
    lines.append(f"- Offers returned: **{report['offer_count']}**")
    lines.append(f"- Ranking unchanged (flag ON vs OFF): **{report['ranking_unchanged_with_flag_on']}**")
    lines.append(f"- V1 score unchanged: **{report['v1_score_unchanged_with_flag_on']}**")
    lines.append(f"- Top-10 overlap (V1 vs V2): **{report['top10_overlap_count']}/10**")
    lines.append(f"- domain_aligned ratio — flag OFF: {report['domain_aligned_ratio']['v1_off']}, ON: {report['domain_aligned_ratio']['v2_on']}\n")
    lines.append("## V1 Score distribution (flag ON)")
    lines.append(f"```\n{json.dumps(report['score_distribution_v1'], indent=2)}\n```\n")
    lines.append("## Fit Score V2 distribution")
    lines.append(f"```\n{json.dumps(report['fit_score_v2_distribution'], indent=2)}\n```\n")
    lines.append("## Preference Score V2 distribution")
    lines.append(f"```\n{json.dumps(report['preference_score_v2_distribution'], indent=2)}\n```\n")
    lines.append("## Top-10 by V1 score")
    lines.append("| offer_id | title | v1 | v2 fit | pref | affinity |")
    lines.append("|---|---|---|---|---|---|")
    for r in report["top10_v1_by_score"]:
        lines.append(
            f"| {r['offer_id']} | {r['title']} | {r['score_v1']} | {r['fit_score_v2']} | {r['preference_score']} | {r['domain_affinity']} |"
        )
    lines.append("\n## Top-10 by Fit Score V2")
    lines.append("| offer_id | title | v1 | v2 fit | pref | affinity |")
    lines.append("|---|---|---|---|---|---|")
    for r in report["top10_v2_by_fit_score"]:
        lines.append(
            f"| {r['offer_id']} | {r['title']} | {r['score_v1']} | {r['fit_score_v2']} | {r['preference_score']} | {r['domain_affinity']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="apps/api/fixtures/profile_demo.json")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument(
        "--out-json",
        default="docs/ai/reports/fit_score_v2_shadow_compare.json",
    )
    parser.add_argument(
        "--out-md",
        default="docs/ai/reports/fit_score_v2_shadow_compare.md",
    )
    args = parser.parse_args()

    profile_path = Path(args.profile)
    if not profile_path.is_absolute():
        profile_path = ROOT / profile_path
    with open(profile_path) as f:
        profile = json.load(f)

    client = TestClient(app)
    off = _post_inbox(client, profile, flag="0", limit=args.limit)
    on = _post_inbox(client, profile, flag="1", limit=args.limit)

    report = _build_report(profile.get("id") or profile_path.stem, off, on)

    out_json = ROOT / args.out_json
    out_md = ROOT / args.out_md
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    out_md.write_text(_to_markdown(report))

    print(f"OK wrote {out_json}")
    print(f"OK wrote {out_md}")
    print(f"  ranking_unchanged={report['ranking_unchanged_with_flag_on']}")
    print(f"  v1_score_unchanged={report['v1_score_unchanged_with_flag_on']}")
    print(f"  fit_score_v2_populated={report['fit_score_v2_populated_count']}/{report['offer_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
