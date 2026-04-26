#!/usr/bin/env python3
"""Domain-aware Matching Audit v1 — audit only.

Reads BF offer_skills and offer_domain_enrichment from PostgreSQL to derive a
data-driven canonical_skill -> domain_tag weight map (11-tag DB taxonomy).
For each sample profile (synthetic, canonical-id-based), infers cv_domain and
projects the impact of a hypothetical hard / soft domain filter on the active
catalog. No runtime, route, scoring, matching, schema or frontend change.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))
_venv = sorted((REPO_ROOT / "apps" / "api" / ".venv" / "lib").glob("python*/site-packages"))
if _venv:
    sys.path.insert(0, str(_venv[0]))


# STRONG_SIGNALS and ADJACENCY are imported from the runtime module so that the
# audit and the inbox soft-signal layer share a single source of truth.
from api.utils.domain_affinity import (  # noqa: E402  (sys.path setup above)
    ADJACENCY,
    STRONG_SIGNALS,
    domain_affinity,
)

WEAK_SIGNALS: set[str] = {
    "skill:excel", "skill:powerpoint", "skill:word", "skill:office",
    "skill:communication", "skill:reporting", "skill:documentation",
    "skill:project_management", "skill:teamwork", "skill:leadership",
    "skill:compliance", "skill:problem_solving", "skill:time_management",
    "skill:presentation",
}

STRONG_WEIGHT = 3.0
DATA_DRIVEN_WEIGHT = 1.0
WEAK_DATA_DRIVEN_WEIGHT = 0.2


def _classify_skill(canonical_id: str) -> tuple[str | None, bool]:
    for domain, members in STRONG_SIGNALS.items():
        if canonical_id in members:
            return domain, False
    return None, canonical_id in WEAK_SIGNALS


SAMPLE_PROFILES: list[dict[str, Any]] = [
    {
        "name": "P1_data_analyst",
        "expected_domain": "data",
        "canonical_ids": [
            "skill:data_analysis", "skill:business_intelligence", "skill:sql",
            "skill:excel", "skill:statistical_programming", "skill:data_visualization",
        ],
    },
    {
        "name": "P2_software_engineer",
        "expected_domain": "engineering",
        "canonical_ids": [
            "skill:software_development", "skill:cloud_architecture", "skill:devops",
            "skill:agile", "skill:documentation", "skill:project_management",
        ],
    },
    {
        "name": "P3_finance_controller",
        "expected_domain": "finance",
        "canonical_ids": [
            "skill:budgeting", "skill:financial_analysis", "skill:accounting",
            "skill:excel", "skill:compliance", "skill:reporting",
        ],
    },
    {
        "name": "P4_marketing_manager",
        "expected_domain": "marketing",
        "canonical_ids": [
            "skill:digital_marketing", "skill:seo", "skill:content_marketing",
            "skill:social_media", "skill:campaign_management",
        ],
    },
    {
        "name": "P5_hr_recruiter",
        "expected_domain": "hr",
        "canonical_ids": [
            "skill:recruitment", "skill:talent_acquisition",
            "skill:human_resources_management", "skill:onboarding",
        ],
    },
    {
        "name": "P6_supply_chain",
        "expected_domain": "supply",
        "canonical_ids": [
            "skill:supply_chain_management", "skill:procurement",
            "skill:logistics", "skill:inventory_management",
        ],
    },
    {
        "name": "P7_sales_b2b",
        "expected_domain": "sales",
        "canonical_ids": [
            "skill:b2b_sales", "skill:lead_generation", "skill:account_management",
            "skill:business_development", "skill:negotiation",
        ],
    },
]


def _connect():
    import psycopg
    db_url = (os.getenv("DATABASE_URL") or "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL not set (load apps/api/.env)")
    return psycopg.connect(db_url, connect_timeout=5)


def load_skill_domain_weights() -> dict[str, dict[str, int]]:
    weights: dict[str, Counter[str]] = defaultdict(Counter)
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.canonical_id, e.domain_tag, COUNT(*) AS n
            FROM offer_skills s
            JOIN offer_domain_enrichment e
              ON s.source = e.source AND s.external_id = e.external_id
            WHERE s.source = 'business_france'
              AND e.source = 'business_france'
              AND s.canonical_id IS NOT NULL
              AND e.domain_tag IS NOT NULL
            GROUP BY s.canonical_id, e.domain_tag
            """
        )
        for canonical_id, domain_tag, n in cur.fetchall():
            weights[str(canonical_id)][str(domain_tag)] = int(n)
    return {k: dict(v) for k, v in weights.items()}


def load_active_offers_with_domain() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.external_id, c.title, COALESCE(e.domain_tag, 'unknown') AS domain_tag
            FROM clean_offers c
            LEFT JOIN offer_domain_enrichment e
              ON c.source = e.source AND c.external_id = e.external_id
            WHERE c.source = 'business_france'
              AND COALESCE(c.is_active, TRUE) = TRUE
            """
        )
        for ext_id, title, domain in cur.fetchall():
            rows.append({
                "external_id": str(ext_id),
                "title": str(title or ""),
                "domain_tag": str(domain or "unknown"),
            })
    return rows


def infer_cv_domain(canonical_ids: list[str], skill_weights: dict[str, dict[str, int]]) -> dict[str, Any]:
    """Hardened inference v2.

    Strong signals (curated per domain) override BF data-driven distributions.
    Weak signals (excel, powerpoint, reporting, etc.) are downweighted so they
    cannot dominate. A domain is assigned only if at least one strong signal is
    present; otherwise the CV is routed to "other" with low confidence.
    """
    score: Counter[str] = Counter()
    breakdown: list[dict[str, Any]] = []
    strong_count = 0
    weak_count = 0
    for skill in canonical_ids:
        strong_domain, is_weak = _classify_skill(skill)
        signal_type = "strong" if strong_domain else ("weak" if is_weak else "neutral")
        if strong_domain:
            score[strong_domain] += STRONG_WEIGHT
            strong_count += 1
        if is_weak:
            weak_count += 1
        w = skill_weights.get(skill, {})
        if w:
            n = sum(w.values())
            mult = WEAK_DATA_DRIVEN_WEIGHT if is_weak else DATA_DRIVEN_WEIGHT
            for domain, count in w.items():
                score[domain] += mult * (count / n)
            top = max(w, key=w.get)
        else:
            top = None
        breakdown.append({
            "skill": skill,
            "signal_type": signal_type,
            "strong_domain": strong_domain,
            "data_driven_top": top,
            "data_driven_n": sum(w.values()),
            "data_driven_distribution": w,
        })

    if strong_count == 0:
        cv_domain = "other"
        confidence = "low_no_strong_signal"
    else:
        cv_domain = score.most_common(1)[0][0]
        confidence = "ok"

    return {
        "cv_domain": cv_domain,
        "confidence": confidence,
        "strong_signal_count": strong_count,
        "weak_signal_count": weak_count,
        "score_distribution": dict(score.most_common()),
        "skill_breakdown": breakdown,
        "skills_with_signal": sum(1 for b in breakdown if b["data_driven_top"] or b["strong_domain"]),
    }


def audit_cv(profile: dict[str, Any], info: dict[str, Any], offers: list[dict[str, Any]]) -> dict[str, Any]:
    cv_domain = info["cv_domain"]
    aligned, adjacent, distant, neutral = [], [], [], []
    for offer in offers:
        affinity = domain_affinity(cv_domain, offer["domain_tag"])
        if affinity == "aligned":
            aligned.append(offer)
        elif affinity == "adjacent":
            adjacent.append(offer)
        elif affinity == "distant":
            distant.append(offer)
        else:
            neutral.append(offer)
    mismatched = adjacent + distant  # legacy binary view (aligned vs not)
    total = len(offers)

    def _short(o: dict[str, Any]) -> dict[str, Any]:
        return {"external_id": o["external_id"], "title": o["title"][:90], "domain_tag": o["domain_tag"]}

    return {
        "profile": profile["name"],
        "expected_domain": profile["expected_domain"],
        "cv_domain_inferred": cv_domain,
        "expected_matches_inferred": cv_domain == profile["expected_domain"],
        "confidence": info.get("confidence", "n/a"),
        "strong_signal_count": info.get("strong_signal_count", 0),
        "weak_signal_count": info.get("weak_signal_count", 0),
        "skills_with_signal": info["skills_with_signal"],
        "skills_total": len(profile["canonical_ids"]),
        "score_distribution_top5": dict(list(info["score_distribution"].items())[:5]),
        "totals": {
            "active_offers": total,
            "aligned": len(aligned),
            "adjacent": len(adjacent),
            "distant": len(distant),
            "neutral_unknown_or_other": len(neutral),
            "mismatched_legacy": len(mismatched),
        },
        "hard_filter_projection": {
            "would_keep": len(aligned),
            "would_keep_with_neutral": len(aligned) + len(neutral),
            "would_exclude": len(mismatched),
            "exclusion_pct": round(100.0 * len(mismatched) / total, 1) if total else 0.0,
        },
        "soft_filter_projection": {
            "high_priority": len(aligned),
            "low_priority": len(mismatched),
            "neutral": len(neutral),
        },
        "affinity_projection": {
            "aligned_pct": round(100.0 * len(aligned) / total, 1) if total else 0.0,
            "adjacent_pct": round(100.0 * len(adjacent) / total, 1) if total else 0.0,
            "distant_pct": round(100.0 * len(distant) / total, 1) if total else 0.0,
            "neutral_pct": round(100.0 * len(neutral) / total, 1) if total else 0.0,
            "soft_keep_aligned_plus_adjacent_pct": round(100.0 * (len(aligned) + len(adjacent)) / total, 1) if total else 0.0,
            "distant_only_exclusion_pct": round(100.0 * len(distant) / total, 1) if total else 0.0,
            "exclusion_reduction_vs_binary_pct": round(100.0 * len(adjacent) / total, 1) if total else 0.0,
        },
        "samples": {
            "aligned_top5": [_short(o) for o in aligned[:5]],
            "adjacent_top10": [_short(o) for o in adjacent[:10]],
            "distant_top10": [_short(o) for o in distant[:10]],
            "mismatched_top10": [_short(o) for o in mismatched[:10]],
            "neutral_top5": [_short(o) for o in neutral[:5]],
        },
        "skill_breakdown": info["skill_breakdown"],
    }


def build_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines: list[str] = []
    lines.append("# Domain-aware Matching Audit v1\n")
    lines.append("> Audit only. No runtime / route / scoring / matching / schema / frontend / DB change. Reads BF tables only (SELECT).\n")
    lines.append("## Summary\n")
    lines.append(f"- audit_date: `{s['audit_date']}`")
    lines.append(f"- profiles_audited: **{s['profiles_audited']}**")
    lines.append(f"- active_bf_offers: **{s['active_offers_total']}**")
    lines.append(f"- skill_universe_in_offer_skills: **{s['skill_universe_size']}**")
    lines.append(f"- expected_vs_inferred_match_rate: **{s['expected_vs_inferred_match_rate_pct']}%**")
    lines.append(f"- average_hard_filter_exclusion_pct: **{s['average_hard_filter_exclusion_pct']}%**")
    lines.append(f"- average_aligned_pct: **{s['average_aligned_pct']}%**")
    lines.append(f"- average_adjacent_pct: **{s.get('average_adjacent_pct', 0)}%**")
    lines.append(f"- average_distant_pct: **{s.get('average_distant_pct', 0)}%**")
    lines.append(f"- average_neutral_pct: **{s.get('average_neutral_pct', 0)}%**")
    lines.append(f"- average_soft_keep (aligned + adjacent): **{s.get('average_soft_keep_aligned_plus_adjacent_pct', 0)}%**")
    lines.append(f"- average_distant_only_exclusion_pct: **{s.get('average_distant_only_exclusion_pct', 0)}%**")
    lines.append(f"- average_exclusion_reduction_vs_binary_pct: **{s.get('average_exclusion_reduction_vs_binary_pct', 0)}%**\n")

    lines.append("## Method (v2 — strong vs weak signal weighting)\n")
    lines.append("1. For each `canonical_id` in `offer_skills` (BF), compute its `domain_tag` distribution from `offer_domain_enrichment`.")
    lines.append("2. For each sample profile (canonical-id list), accumulate domain scores using:")
    lines.append(f"   - **Strong signal** (curated per domain): +{STRONG_WEIGHT} to that domain.")
    lines.append(f"   - **Data-driven distribution**: ×{DATA_DRIVEN_WEIGHT} normal weight, ×{WEAK_DATA_DRIVEN_WEIGHT} for weak signals (excel, powerpoint, reporting, etc.).")
    lines.append("   - Require **≥1 strong signal**; otherwise `cv_domain = \"other\"` (low confidence).")
    lines.append("3. For each active BF offer, classify as `aligned` (offer.domain_tag == cv_domain), `mismatched`, or `neutral` (`unknown`/`other`).")
    lines.append("4. Project hypothetical hard filter (drop mismatched) and soft filter (low-priority mismatched, neutral kept).\n")

    lines.append("## Domain Affinity Matrix v1 (DB 11-tag)\n")
    lines.append("Three-level classification per offer:")
    lines.append("- **aligned**: `offer.domain_tag == cv_domain`")
    lines.append("- **adjacent**: pair listed in `ADJACENCY` (cross-domain mobility / hybrid roles)")
    lines.append("- **distant**: known domain, no listed adjacency")
    lines.append("- **neutral**: `unknown` / `other`\n")
    lines.append("Adjacency pairs (unordered):\n")
    for pair in sorted("|".join(sorted(p)) for p in ADJACENCY):
        a, b = pair.split("|", 1)
        lines.append(f"- `{a}` ↔ `{b}`")
    lines.append("")

    lines.append("## Per-profile results\n")
    for r in payload["results"]:
        ok = "✓" if r["expected_matches_inferred"] else "✗"
        lines.append(f"### {r['profile']} — expected `{r['expected_domain']}` / inferred `{r['cv_domain_inferred']}` {ok}")
        lines.append(f"- skills with signal: {r['skills_with_signal']} / {r['skills_total']} · strong: {r.get('strong_signal_count', 0)} · weak: {r.get('weak_signal_count', 0)} · confidence: `{r.get('confidence', 'n/a')}`")
        td = r["score_distribution_top5"]
        lines.append("- score top5: " + " · ".join(f"{d}={v:.2f}" for d, v in td.items()))
        t = r["totals"]
        lines.append(f"- offers: aligned **{t['aligned']}** · adjacent **{t.get('adjacent', 0)}** · distant **{t.get('distant', 0)}** · neutral **{t['neutral_unknown_or_other']}** · total {t['active_offers']}")
        af = r.get("affinity_projection", {})
        lines.append(f"- affinity %: aligned {af.get('aligned_pct', 0)} · adjacent {af.get('adjacent_pct', 0)} · distant {af.get('distant_pct', 0)} · neutral {af.get('neutral_pct', 0)} · soft_keep {af.get('soft_keep_aligned_plus_adjacent_pct', 0)} · exclusion_reduction {af.get('exclusion_reduction_vs_binary_pct', 0)}")
        h = r["hard_filter_projection"]
        lines.append(f"- hard filter: keep **{h['would_keep']}** (or {h['would_keep_with_neutral']} if neutral kept), exclude **{h['would_exclude']}** ({h['exclusion_pct']}%)")
        sf = r["soft_filter_projection"]
        lines.append(f"- soft filter: high **{sf['high_priority']}**, low **{sf['low_priority']}**, neutral **{sf['neutral']}**")
        sa = r["samples"]["aligned_top5"][:3]
        if sa:
            lines.append("\n**Sample aligned:**")
            for o in sa:
                lines.append(f"  - `{o['external_id']}` [{o['domain_tag']}] {o['title']}")
        sadj = r["samples"].get("adjacent_top10", [])[:5]
        if sadj:
            lines.append("\n**Sample adjacent (kept by soft, dropped by hard):**")
            for o in sadj:
                lines.append(f"  - `{o['external_id']}` [{o['domain_tag']}] {o['title']}")
        sdist = r["samples"].get("distant_top10", [])[:5]
        if sdist:
            lines.append("\n**Sample distant (would be excluded by both soft and hard):**")
            for o in sdist:
                lines.append(f"  - `{o['external_id']}` [{o['domain_tag']}] {o['title']}")
        lines.append("")

    lines.append("## Manual interpretation guide\n")
    lines.append("- A **good mismatch** is an offer whose `domain_tag` correctly diverges from the cv_domain — hard filter helps.")
    lines.append("- A **false mismatch** is an offer the user would actually want — hard filter would harm. Hint: check titles for cross-domain roles (e.g. data analyst in finance dept).")
    lines.append("- Neutral (`unknown`/`other`) offers are not actionable for a domain filter without taxonomy upgrade.")
    lines.append("- An expected-vs-inferred mismatch on a profile signals either (a) skill set is multi-domain by nature, or (b) the data-driven map needs more skills.")

    lines.append("\n## Decision criteria for next sprint\n")
    lines.append("- If average_hard_filter_exclusion_pct is high but mismatch samples look mostly good → hard filter may be safe.")
    lines.append("- If false mismatches dominate → prefer soft filter (re-rank only) when this becomes a runtime sprint.")
    lines.append("- If expected_vs_inferred_match_rate < 80% → strengthen the cv_domain inference (more skills, smarter weighting) before any runtime activation.")
    lines.append("- If `average_exclusion_reduction_vs_binary_pct` is significant and adjacent samples look correct → adopt 3-level affinity as soft signal.")
    lines.append("- If adjacent samples look mostly wrong → tighten or remove specific adjacency pairs before adoption.\n")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Domain-aware Matching Audit v1 (audit only).")
    parser.add_argument("--out-json", default="baseline/domain_aware_matching_audit/audit_v1.json")
    parser.add_argument("--out-md", default="docs/ai/reports/domain_aware_matching_audit_v1.md")
    args = parser.parse_args()

    if os.getenv("ELEVIA_DOMAIN_AUDIT", "0") not in ("1", "true", "TRUE"):
        print(json.dumps({"skipped": True, "reason": "set ELEVIA_DOMAIN_AUDIT=1 to run"}))
        return 0

    load_dotenv(REPO_ROOT / "apps" / "api" / ".env")

    skill_weights = load_skill_domain_weights()
    offers = load_active_offers_with_domain()

    results = [audit_cv(p, infer_cv_domain(p["canonical_ids"], skill_weights), offers) for p in SAMPLE_PROFILES]

    n = len(results)
    summary = {
        "audit_date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "profiles_audited": n,
        "active_offers_total": len(offers),
        "skill_universe_size": len(skill_weights),
        "expected_vs_inferred_match_rate_pct": round(
            100.0 * sum(1 for r in results if r["expected_matches_inferred"]) / n, 1
        ),
        "average_hard_filter_exclusion_pct": round(
            sum(r["hard_filter_projection"]["exclusion_pct"] for r in results) / n, 1
        ),
        "average_aligned_pct": round(
            sum(r["affinity_projection"]["aligned_pct"] for r in results) / n, 1
        ),
        "average_adjacent_pct": round(
            sum(r["affinity_projection"]["adjacent_pct"] for r in results) / n, 1
        ),
        "average_distant_pct": round(
            sum(r["affinity_projection"]["distant_pct"] for r in results) / n, 1
        ),
        "average_neutral_pct": round(
            sum(r["affinity_projection"]["neutral_pct"] for r in results) / n, 1
        ),
        "average_soft_keep_aligned_plus_adjacent_pct": round(
            sum(r["affinity_projection"]["soft_keep_aligned_plus_adjacent_pct"] for r in results) / n, 1
        ),
        "average_distant_only_exclusion_pct": round(
            sum(r["affinity_projection"]["distant_only_exclusion_pct"] for r in results) / n, 1
        ),
        "average_exclusion_reduction_vs_binary_pct": round(
            sum(r["affinity_projection"]["exclusion_reduction_vs_binary_pct"] for r in results) / n, 1
        ),
    }

    payload = {
        "version": "v1",
        "type": "domain_aware_matching_audit",
        "taxonomy_used": "db_11_tag",
        "scope": "business_france_active",
        "behavior_change": "none",
        "inference_version": "v2_strong_weak_weighting",
        "affinity_version": "v1_3_level_aligned_adjacent_distant",
        "inference_weights": {
            "strong_weight": STRONG_WEIGHT,
            "data_driven_weight": DATA_DRIVEN_WEIGHT,
            "weak_data_driven_weight": WEAK_DATA_DRIVEN_WEIGHT,
            "strong_signals_per_domain": {k: sorted(v) for k, v in STRONG_SIGNALS.items()},
            "weak_signals": sorted(WEAK_SIGNALS),
        },
        "adjacency_pairs": sorted(["|".join(sorted(p)) for p in ADJACENCY]),
        "summary": summary,
        "sample_profiles": SAMPLE_PROFILES,
        "results": results,
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(build_markdown(payload), encoding="utf-8")

    print(json.dumps({"out_json": str(out_json), "out_md": str(out_md), "summary": summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
