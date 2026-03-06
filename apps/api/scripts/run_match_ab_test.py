#!/usr/bin/env python3
"""
run_match_ab_test.py
Compare matching scores with ESCO promotion OFF vs ON.

Usage:
  python apps/api/scripts/run_match_ab_test.py \
    --profile-json /tmp/parse_esco_on.json --cluster DATA_IT --offers 100
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple

API_ROOT = Path(__file__).parent.parent
DB_PATH = API_ROOT / "data" / "db" / "offers.db"
OUT_PATH = Path("/tmp/elevia_match_ab_test.json")

# Add src to path for shared utilities
import sys
sys.path.insert(0, str(API_ROOT / "src"))

from api.utils.offer_skills import get_offer_skills_by_offer_ids
from matching.extractors import extract_profile
from matching.matching_v1 import MatchingEngine


def _get_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _select_cluster_column(columns: set[str]) -> str | None:
    for candidate in ("cluster_macro", "offer_cluster", "cluster"):
        if candidate in columns:
            return candidate
    return None


def _load_profile(path: Path) -> Dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("profile"), dict):
        return data["profile"]
    return data if isinstance(data, dict) else {}


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


def _select_offer_ids(conn: sqlite3.Connection, cluster: str, limit: int) -> List[str]:
    offers_cols = _get_columns(conn, "fact_offers")
    cluster_col = _select_cluster_column(offers_cols)
    params: List[object] = []
    where = "WHERE fos.skill_uri IS NOT NULL AND fos.skill_uri != ''"
    if cluster_col:
        where += f" AND fo.{cluster_col} = ?"
        params.append(cluster)
    query = f"""
        SELECT fos.offer_id
        FROM fact_offer_skills fos
        JOIN fact_offers fo ON fo.id = fos.offer_id
        {where}
        GROUP BY fos.offer_id
        ORDER BY fos.offer_id ASC
        LIMIT ?
    """
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [str(r[0]) for r in rows]


def _load_offers(conn: sqlite3.Connection, offer_ids: List[str]) -> List[Dict]:
    if not offer_ids:
        return []
    placeholders = ",".join("?" for _ in offer_ids)
    rows = conn.execute(
        f"""
        SELECT id, source, title, description, company, city, country,
               publication_date, contract_duration, start_date, payload_json
        FROM fact_offers
        WHERE id IN ({placeholders})
        """,
        offer_ids,
    ).fetchall()
    offers_map = {str(r[0]): dict(r) for r in rows}
    skills_map = get_offer_skills_by_offer_ids(conn, offer_ids)

    offers: List[Dict] = []
    for offer_id in offer_ids:
        offer = offers_map.get(str(offer_id))
        if not offer:
            continue
        entry = skills_map.get(str(offer_id), {})
        if entry.get("skills_uri"):
            offer["skills_uri"] = entry["skills_uri"]
        if entry.get("skills"):
            offer["skills"] = entry["skills"]
        _attach_payload_fields(offer)
        offer.pop("payload_json", None)
        offers.append(offer)
    return offers


def _run_matching(profile: Dict, offers: List[Dict], promote_flag: str) -> Dict[str, float]:
    os.environ["ELEVIA_PROMOTE_ESCO"] = promote_flag
    extracted = extract_profile(copy.deepcopy(profile))
    engine = MatchingEngine(copy.deepcopy(offers))
    scores: Dict[str, float] = {}
    for offer in offers:
        result = engine.score_offer(extracted, offer)
        scores[str(result.offer_id)] = float(result.score)
    return scores


def main() -> int:
    parser = argparse.ArgumentParser(description="Run A/B matching test (ESCO promotion OFF vs ON)")
    parser.add_argument("--profile-json", required=True)
    parser.add_argument("--cluster", default="DATA_IT")
    parser.add_argument("--offers", type=int, default=100)
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
        offer_ids = _select_offer_ids(conn, args.cluster, args.offers)
        offers = _load_offers(conn, offer_ids)
    finally:
        conn.close()

    if not offers:
        print("No offers selected for A/B test.")
        return 1

    scores_off = _run_matching(profile, offers, "0")
    scores_on = _run_matching(profile, offers, "1")

    results: List[Dict[str, float]] = []
    for offer_id in offer_ids:
        off = scores_off.get(str(offer_id), 0.0)
        on = scores_on.get(str(offer_id), 0.0)
        delta = round(on - off, 2)
        results.append(
            {
                "offer_id": str(offer_id),
                "score_off": off,
                "score_on": on,
                "delta": delta,
            }
        )

    offers_tested = len(results)
    offers_improved = len([r for r in results if r["delta"] > 0])
    offers_degraded = len([r for r in results if r["delta"] < 0])
    offers_unchanged = len([r for r in results if r["delta"] == 0])
    offers_with_delta = offers_improved + offers_degraded
    delta_ratio = round(offers_with_delta / offers_tested, 3) if offers_tested else 0.0
    avg_delta = round(sum(r["delta"] for r in results) / offers_tested, 3) if offers_tested else 0.0
    max_delta = max((r["delta"] for r in results), default=0.0)
    min_delta = min((r["delta"] for r in results), default=0.0)

    top_deltas = sorted(results, key=lambda r: (-abs(r["delta"]), r["offer_id"]))[:10]

    report = {
        "offers_tested": offers_tested,
        "offers_improved": offers_improved,
        "offers_degraded": offers_degraded,
        "offers_unchanged": offers_unchanged,
        "delta_ratio": delta_ratio,
        "avg_delta": avg_delta,
        "max_delta": max_delta,
        "min_delta": min_delta,
        "top_deltas": top_deltas,
    }

    OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("MATCHING A/B TEST")
    print(f"offers_tested: {offers_tested}")
    print(f"offers_improved: {offers_improved}")
    print(f"offers_degraded: {offers_degraded}")
    print(f"offers_unchanged: {offers_unchanged}")
    print(f"\ndelta_ratio: {delta_ratio}")
    print(f"avg_delta: {avg_delta}")
    print(f"max_delta: {max_delta}")
    print(f"min_delta: {min_delta}")
    print("\nTOP DELTA OFFERS")
    print("offer_id | score_off | score_on | delta")
    for row in top_deltas:
        print(f"{row['offer_id']} | {row['score_off']} | {row['score_on']} | {row['delta']}")
    print(f"\nReport written: {OUT_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
