"""OFF vs ON comparison runner for ELEVIA_FILTER_GENERIC_URIS.

Read-only ad-hoc script. No product code is modified. No config is changed
permanently. Loads 839 BF offers from SQLite, parses 10 real CVs, scores each
profile twice (flag OFF, flag ON) and produces JSON artefacts for analysis.

Hard filter (VIE gate) is bypassed via monkey-patch so that the comparison
focuses purely on the skills-scoring branch. `score_offer` itself is not
modified.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
API_SRC = REPO_ROOT / "apps" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from api.utils.generic_skills_filter import (  # noqa: E402
    HARD_GENERIC_URIS,
    filter_skills_uri_for_scoring,
)
from matching import matching_v1  # noqa: E402
from matching.extractors import extract_profile  # noqa: E402
from matching.matching_v1 import MatchingEngine  # noqa: E402
from profile.baseline_parser import run_baseline  # noqa: E402

# ── Bypass VIE hard filter ----------------------------------------------------
# We want score_offer to reach _score_skills for every offer, independent of
# BF offers not being VIE. We never mutate the source class; we assign for
# the duration of this script only.
MatchingEngine._hard_filter = lambda self, offer: (True, None)  # type: ignore[attr-defined]

# ── Config ---------------------------------------------------------------------
DB_PATH = REPO_ROOT / "apps" / "api" / "data" / "db" / "offers.db"
CV_DIR = REPO_ROOT / "apps" / "api" / "data" / "eval" / "synthetic_cv_dataset_v1"
CV_REF = REPO_ROOT / "apps" / "api" / "fixtures" / "cv" / "cv_fixture_v0.txt"
OUT_DIR = REPO_ROOT / "baseline" / "generic_filter_validation"
TOP_N = 10

# Small profile taxonomy guess (from filenames + Sprint 4 notes) used purely
# for reporting — not to influence scoring.
CV_DOMAIN_HINTS: Dict[str, str] = {
    "cv_fixture_v0": "data_analyst_bilingual",
    "cv_01_lina_morel": "sales_b2b",
    "cv_02_hugo_renaud": "business_dev_export",
    "cv_03_sarah_el_mansouri": "finance_or_admin_unknown",
    "cv_04_benoit_caron": "supply_ops_logistics",
    "cv_05_camille_vasseur": "communication_paris",
    "cv_06_yasmine_haddad": "marketing_digital",
    "cv_07_pierre_lemaire": "finance_or_admin_unknown",
    "cv_08_amel_dufour": "finance_or_admin_unknown",
    "cv_09_ines_barbier": "rh_junior",
}


def load_offers() -> List[Dict]:
    """Load 839 BF offers from SQLite with pre-computed skills_uri."""
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(
        """SELECT id, source, title, description, country, city, publication_date
            FROM fact_offers WHERE source='business_france'"""
    )
    offers = [dict(r) for r in cur.fetchall()]
    by_id: Dict[str, Dict] = {o["id"]: o for o in offers}
    cur.execute("SELECT offer_id, skill, skill_uri FROM fact_offer_skills")
    buckets: Dict[str, Dict[str, List[str]]] = defaultdict(
        lambda: {"skills": [], "skills_uri": []}
    )
    for row in cur.fetchall():
        oid = row["offer_id"]
        if oid not in by_id:
            continue
        label = row["skill"]
        uri = row["skill_uri"]
        if label:
            buckets[oid]["skills"].append(str(label))
        if uri:
            buckets[oid]["skills_uri"].append(str(uri))
    con.close()

    for offer in offers:
        bucket = buckets.get(offer["id"], {"skills": [], "skills_uri": []})
        offer["skills"] = bucket["skills"]
        # dedupe uris while preserving order
        seen = set()
        uris = []
        for u in bucket["skills_uri"]:
            if u not in seen:
                seen.add(u)
                uris.append(u)
        offer["skills_uri"] = uris
        offer["skills_uri_count"] = len(uris)
        # Minimal fields expected downstream
        offer.setdefault("company", "unknown")
        offer.setdefault("languages", [])
        offer.setdefault("education", None)
    return offers


def load_cvs() -> List[Tuple[str, str]]:
    cvs: List[Tuple[str, str]] = []
    if CV_REF.exists():
        cvs.append(("cv_fixture_v0", CV_REF.read_text(encoding="utf-8")))
    for p in sorted(CV_DIR.glob("cv_*.txt")):
        cvs.append((p.stem, p.read_text(encoding="utf-8")))
    return cvs


def build_profile(cv_text: str, profile_id: str):
    raw = run_baseline(cv_text, profile_id=profile_id)
    # run_baseline wraps the usable profile in raw["profile"]; that's the dict
    # extract_profile() expects (with skills/skills_uri keys).
    profile_dict = raw.get("profile") or raw
    return extract_profile(profile_dict), raw


def score_all(engine: MatchingEngine, profile, offers: List[Dict]) -> List[Dict]:
    results = []
    for offer in offers:
        res = engine.score_offer(profile, offer)
        results.append(
            {
                "offer_id": res.offer_id,
                "score": float(res.score),
                "title": offer.get("title"),
                "matched_skills": list(res.breakdown.keys()) if False else [],
                "skills_uri_used": len(offer.get("skills_uri") or []),
            }
        )
    results.sort(key=lambda r: (-r["score"], r["offer_id"]))
    return results


def clone_offers_with_filter(offers: List[Dict]) -> Tuple[List[Dict], int, Dict[str, int]]:
    """Return a deep-enough copy of offers with skills_uri filtered via
    filter_skills_uri_for_scoring. The function is flag-gated; caller sets
    ELEVIA_FILTER_GENERIC_URIS=1 before invoking.
    Returns (cloned_offers, total_removed, per_uri_removed_counts).
    """
    total_removed = 0
    per_uri: Dict[str, int] = defaultdict(int)
    cloned = []
    for offer in offers:
        c = dict(offer)
        raw = list(offer.get("skills_uri") or [])
        filtered = filter_skills_uri_for_scoring(raw)
        if filtered is not raw:
            removed = [u for u in raw if u not in set(filtered)]
            total_removed += len(removed)
            for u in removed:
                per_uri[u] += 1
            c["skills_uri"] = filtered
            c["skills_uri_count"] = len(filtered)
        cloned.append(c)
    return cloned, total_removed, dict(per_uri)


def compare_tops(off_top: List[Dict], on_top: List[Dict]) -> Dict:
    off_ids = [r["offer_id"] for r in off_top]
    on_ids = [r["offer_id"] for r in on_top]
    overlap = set(off_ids) & set(on_ids)
    overlap_count = len(overlap)

    # Score deltas on overlap
    off_map = {r["offer_id"]: r["score"] for r in off_top}
    on_map = {r["offer_id"]: r["score"] for r in on_top}
    diffs = [on_map[oid] - off_map[oid] for oid in overlap]
    score_diff_avg = round(sum(diffs) / len(diffs), 3) if diffs else 0.0

    # Ranking moves
    rank_moves = {}
    for oid in overlap:
        off_rank = off_ids.index(oid) + 1
        on_rank = on_ids.index(oid) + 1
        rank_moves[oid] = off_rank - on_rank  # positive = climbed

    newly_on = [oid for oid in on_ids if oid not in set(off_ids)]
    dropped_on = [oid for oid in off_ids if oid not in set(on_ids)]

    return {
        "overlap_count": overlap_count,
        "score_diff_avg_on_overlap": score_diff_avg,
        "ranking_moves_on_overlap": rank_moves,
        "newly_in_top_on": newly_on,
        "dropped_from_top_on": dropped_on,
    }


def per_profile_stats(profile, offers_off: List[Dict], offers_on: List[Dict]) -> Dict:
    n_hard_in_profile = sum(1 for u in profile.skills_uri if u in HARD_GENERIC_URIS)
    return {
        "profile_skills_uri_count": len(profile.skills_uri),
        "profile_hard_generic_count": n_hard_in_profile,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Safety: ensure we start with the flag unset
    os.environ.pop("ELEVIA_FILTER_GENERIC_URIS", None)

    print("[1/4] Loading offers …", file=sys.stderr)
    offers = load_offers()
    print(f"      -> {len(offers)} offers loaded", file=sys.stderr)

    print("[2/4] Loading CVs and building profiles …", file=sys.stderr)
    cvs = load_cvs()
    profiles = []
    for cv_id, text in cvs:
        try:
            profile, raw = build_profile(text, profile_id=cv_id)
            profiles.append((cv_id, profile, raw))
        except Exception as exc:  # noqa: BLE001
            print(f"      -> {cv_id}: parse failed ({exc})", file=sys.stderr)
    print(f"      -> {len(profiles)} profiles built", file=sys.stderr)

    print("[3/4] Scoring OFF vs ON for each profile …", file=sys.stderr)

    # IDF is offer-corpus dependent. To compare OFF vs ON apples-to-apples we
    # use a single MatchingEngine built on the unfiltered corpus — the ON
    # branch only alters the per-offer skills_uri fed into score_offer, not
    # the IDF table (which is a product choice rather than a runtime one).
    engine = MatchingEngine(offers)

    # Filter ON cloned corpus — flag must be active during this call
    os.environ["ELEVIA_FILTER_GENERIC_URIS"] = "1"
    offers_on, total_removed_on, per_uri_removed = clone_offers_with_filter(offers)
    # Flag needs to stay on for filter_skills_uri_for_scoring (already invoked
    # during cloning). score_offer itself does not read the flag, but some
    # downstream code might — we keep it on for the scoring pass for
    # semantic consistency, then restore.
    offers_off = offers  # untouched — reference

    per_profile: List[Dict] = []
    for cv_id, profile, raw in profiles:
        os.environ["ELEVIA_FILTER_GENERIC_URIS"] = "0"
        top_off_full = score_all(engine, profile, offers_off)
        os.environ["ELEVIA_FILTER_GENERIC_URIS"] = "1"
        top_on_full = score_all(engine, profile, offers_on)

        top_off = top_off_full[:TOP_N]
        top_on = top_on_full[:TOP_N]
        comp = compare_tops(top_off, top_on)

        n_hard_in_profile = sum(
            1 for u in profile.skills_uri if u in HARD_GENERIC_URIS
        )

        # Heuristic qualitative flags (no LLM):
        # - "less_noise": at least one HARD-generic URI was a top-scoring
        #   ingredient OFF and that offer dropped out of top10 ON, OR
        #   the top offers ON show higher skills_uri_used diversity.
        # - "lost_good_matches": an OFF top-3 offer dropped from top10 ON.
        # - "better": less_noise AND NOT lost_good_matches AND overlap >= 3.
        dropped_top3 = any(
            r["offer_id"] not in {x["offer_id"] for x in top_on}
            for r in top_off[:3]
        )
        less_noise = bool(comp["dropped_from_top_on"])
        better = less_noise and (not dropped_top3) and comp["overlap_count"] >= 3
        too_empty = len(profile.skills_uri) - n_hard_in_profile < 2

        per_profile.append(
            {
                "profile_id": cv_id,
                "profile_domain_hint": CV_DOMAIN_HINTS.get(cv_id, "unknown"),
                "profile_skills_uri_count": len(profile.skills_uri),
                "profile_hard_generic_count": n_hard_in_profile,
                "profile_becomes_empty_on_filter": too_empty,
                "top10_off": top_off,
                "top10_on": top_on,
                "overlap_count": comp["overlap_count"],
                "score_diff_avg": comp["score_diff_avg_on_overlap"],
                "ranking_moves_on_overlap": comp["ranking_moves_on_overlap"],
                "newly_in_top_on": comp["newly_in_top_on"],
                "dropped_from_top_on": comp["dropped_from_top_on"],
                "removed_skills_count": total_removed_on,
                "analysis": {
                    "better": better,
                    "lost_good_matches": dropped_top3,
                    "less_noise": less_noise,
                    "too_empty_after_filter": too_empty,
                },
            }
        )

    # Reset flag at end
    os.environ["ELEVIA_FILTER_GENERIC_URIS"] = "0"

    print("[4/4] Writing outputs …", file=sys.stderr)
    (OUT_DIR / "per_profile_comparison.json").write_text(
        json.dumps(per_profile, ensure_ascii=False, indent=2)
    )

    n = len(per_profile)
    n_better = sum(1 for p in per_profile if p["analysis"]["better"])
    n_lost = sum(1 for p in per_profile if p["analysis"]["lost_good_matches"])
    n_empty = sum(1 for p in per_profile if p["analysis"]["too_empty_after_filter"])
    n_noise = sum(1 for p in per_profile if p["analysis"]["less_noise"])
    n_neutral = n - n_better - n_lost
    avg_overlap = round(sum(p["overlap_count"] for p in per_profile) / n, 2) if n else 0
    avg_score_diff = (
        round(sum(p["score_diff_avg"] for p in per_profile) / n, 3) if n else 0
    )

    summary = {
        "profiles_tested": n,
        "pct_improved": round(100 * n_better / n, 1) if n else 0,
        "pct_lost_good_matches": round(100 * n_lost / n, 1) if n else 0,
        "pct_too_empty_after_filter": round(100 * n_empty / n, 1) if n else 0,
        "pct_less_noise": round(100 * n_noise / n, 1) if n else 0,
        "pct_neutral": round(100 * n_neutral / n, 1) if n else 0,
        "avg_top10_overlap": avg_overlap,
        "avg_score_diff_on_overlap": avg_score_diff,
        "total_uris_removed_from_corpus_on": total_removed_on,
        "per_uri_removed_counts": per_uri_removed,
        "hard_generic_urls_count": len(HARD_GENERIC_URIS),
    }
    (OUT_DIR / "global_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
