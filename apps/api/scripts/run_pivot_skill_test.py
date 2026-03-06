#!/usr/bin/env python3
"""
run_pivot_skill_test.py
Audit pivot-skill impact on matching for a given cluster.

Usage:
  python apps/api/scripts/run_pivot_skill_test.py \
    --profile-json /tmp/parse_esco_on.json --cluster DATA_IT --offers 150
"""

from __future__ import annotations

import argparse
import copy
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple

API_ROOT = Path(__file__).parent.parent
DB_PATH = API_ROOT / "data" / "db" / "offers.db"
OUT_PATH = Path("/tmp/elevia_pivot_skill_test.json")

import sys
sys.path.insert(0, str(API_ROOT / "src"))

from api.utils.offer_skills import get_offer_skills_by_offer_ids
from matching.extractors import extract_profile
from matching.matching_v1 import MatchingEngine
from offer.offer_cluster import detect_offer_cluster


def _load_profile(path: Path) -> Dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("profile"), dict):
        return data["profile"]
    return data if isinstance(data, dict) else {}


def _get_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _select_cluster_column(columns: set[str]) -> str | None:
    for candidate in ("cluster_macro", "offer_cluster", "cluster"):
        if candidate in columns:
            return candidate
    return None


def _attach_payload_fields(offer: Dict) -> None:
    payload_raw = offer.get("payload_json")
    if not payload_raw or not isinstance(payload_raw, str):
        return
    try:
        payload = json.loads(payload_raw)
    except Exception:
        return
    if offer.get("is_vie") is None and isinstance(payload.get("is_vie"), bool):
        offer["is_vie"] = payload.get("is_vie")


def _load_offers(
    conn: sqlite3.Connection,
    cluster: str,
    limit: int,
) -> List[Dict]:
    columns = _get_columns(conn, "fact_offers")
    cluster_col = _select_cluster_column(columns)

    rows = conn.execute(
        "SELECT id, title, description, company, city, country, "
        "publication_date, contract_duration, start_date, payload_json "
        f"{',' + cluster_col if cluster_col else ''} "
        "FROM fact_offers"
    ).fetchall()

    offer_ids = [str(r["id"]) for r in rows]
    skills_map = get_offer_skills_by_offer_ids(conn, offer_ids)

    offers: List[Dict] = []
    for r in rows:
        offer_id = str(r["id"])
        entry = skills_map.get(offer_id, {})
        skills_uri = entry.get("skills_uri") or []
        if not skills_uri:
            continue

        if cluster_col:
            offer_cluster = str(r.get(cluster_col) or "").upper()
        else:
            labels = entry.get("skills") or []
            offer_cluster, _, _ = detect_offer_cluster(
                r["title"] or "", r["description"] or "", labels
            )
        if offer_cluster != cluster:
            continue

        offer = dict(r)
        offer["skills_uri"] = skills_uri
        if entry.get("skills"):
            offer["skills"] = entry["skills"]
        _attach_payload_fields(offer)
        offer.pop("payload_json", None)
        offers.append(offer)

    offers = sorted(offers, key=lambda o: str(o.get("id") or ""))[:limit]
    return offers


def _compute_pivot_skills(offers: List[Dict], top_n: int = 10) -> List[Tuple[str, int]]:
    freq: Dict[str, int] = {}
    for offer in offers:
        uris = offer.get("skills_uri") or []
        for uri in set(uris):
            freq[str(uri)] = freq.get(str(uri), 0) + 1
    return sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:top_n]


def _build_profile_variant(
    profile: Dict, pivot_uris: List[str], mode: str
) -> Dict:
    """
    mode:
      - 'A': normal
      - 'B': remove pivots
      - 'C': keep only pivots
    """
    p = copy.deepcopy(profile)
    base = [u for u in (p.get("skills_uri") or []) if isinstance(u, str)]
    promoted = [u for u in (p.get("skills_uri_promoted") or []) if isinstance(u, str)]

    pivot_set = set(pivot_uris)
    if mode == "B":
        base = [u for u in base if u not in pivot_set]
        promoted = [u for u in promoted if u not in pivot_set]
    elif mode == "C":
        base = [u for u in base if u in pivot_set]
        promoted = [u for u in promoted if u in pivot_set]

    p["skills_uri"] = base
    if promoted:
        p["skills_uri_promoted"] = promoted
    else:
        p.pop("skills_uri_promoted", None)
    p.pop("skills_uri_effective", None)
    return p


def _score_offers(profile: Dict, offers: List[Dict]) -> Tuple[float, Dict[str, int], List[Tuple[str, int]]]:
    extracted = extract_profile(copy.deepcopy(profile))
    engine = MatchingEngine(copy.deepcopy(offers))
    scores: List[int] = []
    scored: List[Tuple[str, int]] = []
    for offer in offers:
        res = engine.score_offer(extracted, offer)
        scores.append(int(res.score))
        scored.append((str(res.offer_id), int(res.score)))
    mean_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    dist = {"0-39": 0, "40-59": 0, "60-79": 0, "80-100": 0}
    for s in scores:
        if s < 40:
            dist["0-39"] += 1
        elif s < 60:
            dist["40-59"] += 1
        elif s < 80:
            dist["60-79"] += 1
        else:
            dist["80-100"] += 1

    top20 = sorted(scored, key=lambda x: (-x[1], x[0]))[:20]
    return mean_score, dist, top20


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pivot skill audit")
    parser.add_argument("--profile-json", required=True)
    parser.add_argument("--cluster", default="DATA_IT")
    parser.add_argument("--offers", type=int, default=150)
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(json.dumps({"error": "DB_MISSING", "db_path": str(db_path)}, indent=2))
        return 1

    profile = _load_profile(Path(args.profile_json))

    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        offers = _load_offers(conn, args.cluster, args.offers)
    finally:
        conn.close()

    if not offers:
        print("No offers selected for pivot test.")
        return 1

    pivot = _compute_pivot_skills(offers, top_n=10)
    pivot_uris = [u for u, _ in pivot]

    profile_a = _build_profile_variant(profile, pivot_uris, "A")
    profile_b = _build_profile_variant(profile, pivot_uris, "B")
    profile_c = _build_profile_variant(profile, pivot_uris, "C")

    mean_a, dist_a, top20_a = _score_offers(profile_a, offers)
    mean_b, dist_b, top20_b = _score_offers(profile_b, offers)
    mean_c, dist_c, top20_c = _score_offers(profile_c, offers)

    delta_a_b = round(mean_a - mean_b, 2)
    delta_a_c = round(mean_a - mean_c, 2)

    report = {
        "offers_tested": len(offers),
        "pivot_skills": [{"uri": u, "count": c} for u, c in pivot],
        "mean_score_A": mean_a,
        "mean_score_B": mean_b,
        "mean_score_C": mean_c,
        "delta_A_B": delta_a_b,
        "delta_A_C": delta_a_c,
        "distribution_A": dist_a,
        "distribution_B": dist_b,
        "distribution_C": dist_c,
        "top20_A": top20_a,
        "top20_B": top20_b,
        "top20_C": top20_c,
    }

    OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("PIVOT SKILL TEST")
    print(f"OFFERS TESTED: {len(offers)}")
    print("\nTOP PIVOT SKILLS")
    for uri, count in pivot:
        print(f"{uri} {count}")

    print("\nMEAN SCORES")
    print(f"profile_A (normal): {mean_a}")
    print(f"profile_B (no pivots): {mean_b}")
    print(f"profile_C (pivots only): {mean_c}")

    print("\nDELTAS")
    print(f"delta_A_B: {delta_a_b}")
    print(f"delta_A_C: {delta_a_c}")

    print(f"\nReport written: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
