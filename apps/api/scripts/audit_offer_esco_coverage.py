#!/usr/bin/env python3
"""
audit_offer_esco_coverage.py
Deterministic ESCO coverage audit for offer catalog (read-only).

Usage:
  python apps/api/scripts/audit_offer_esco_coverage.py

Outputs:
  - JSON report printed to stdout
  - JSON report written to /tmp/elevia_offer_esco_audit.json
  - Human-readable summary printed to stdout
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Tuple

API_SRC = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(API_SRC))

from offer.offer_cluster import detect_offer_cluster

DB_PATH = Path(__file__).parent.parent / "data" / "db" / "offers.db"
OUT_PATH = Path("/tmp/elevia_offer_esco_audit.json")

CLUSTERS = ["DATA_IT", "FINANCE", "ENGINEERING_INDUSTRY", "MARKETING_SALES", "OTHER"]


def _percent(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100, 2)


def _median(values: List[int]) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    mid = len(vals) // 2
    if len(vals) % 2 == 1:
        return float(vals[mid])
    return (vals[mid - 1] + vals[mid]) / 2.0


def _p90(values: List[int]) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    # nearest-rank method
    idx = max(0, int(round(0.9 * len(vals) + 0.5)) - 1)
    return float(vals[min(idx, len(vals) - 1)])


def _get_table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def _get_offer_skills_map(conn: sqlite3.Connection) -> Tuple[Dict[str, Dict[str, List[str]]], bool]:
    cur = conn.cursor()
    columns = {row[1] for row in cur.execute("PRAGMA table_info(fact_offer_skills)").fetchall()}
    has_skill_uri = "skill_uri" in columns
    if has_skill_uri:
        cur.execute("SELECT offer_id, skill, skill_uri FROM fact_offer_skills")
    else:
        cur.execute("SELECT offer_id, skill, NULL as skill_uri FROM fact_offer_skills")
    skills_map: Dict[str, Dict[str, List[str]]] = {}
    for offer_id, skill, skill_uri in cur.fetchall():
        if not offer_id or not skill:
            continue
        entry = skills_map.setdefault(str(offer_id), {"labels": [], "uris": []})
        entry["labels"].append(str(skill))
        if skill_uri:
            entry["uris"].append(str(skill_uri))
    return skills_map, has_skill_uri


def _get_top_skill_labels(conn: sqlite3.Connection, limit: int = 10) -> List[Tuple[str, int]]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT skill, COUNT(*) as cnt
        FROM fact_offer_skills
        GROUP BY skill
        ORDER BY cnt DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [(row[0], int(row[1])) for row in cur.fetchall()]


def main() -> int:
    if not DB_PATH.exists():
        print(json.dumps({"error": "DB_MISSING", "db_path": str(DB_PATH)}, indent=2))
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    try:
        columns = _get_table_columns(conn, "fact_offers")
    except sqlite3.OperationalError:
        print(json.dumps({"error": "TABLE_MISSING", "table": "fact_offers"}, indent=2))
        return 1

    cluster_col = None
    for candidate in ("cluster_macro", "offer_cluster", "cluster"):
        if candidate in columns:
            cluster_col = candidate
            break

    select_cols = ["id", "title", "description"]
    if cluster_col:
        select_cols.append(cluster_col)

    cur = conn.cursor()
    cur.execute(f"SELECT {', '.join(select_cols)} FROM fact_offers")
    offers = cur.fetchall()

    skills_map, has_skill_uri = _get_offer_skills_map(conn)
    top_skill_labels = _get_top_skill_labels(conn, limit=10)
    conn.close()

    total_offers = len(offers)
    skills_counts: List[int] = []
    offers_with_any_skill_rows = 0

    dist = {
        "0": 0,
        "1-3": 0,
        "4-10": 0,
        "10+": 0,
    }

    cluster_stats = {
        c: {
            "offer_count": 0,
            "offers_with_esco": 0,
            "coverage_ratio": 0.0,
            "mean_skills_uri": 0.0,
        }
        for c in CLUSTERS
    }

    for row in offers:
        offer_id = str(row["id"])
        title = row["title"] or ""
        description = row["description"] or ""

        if cluster_col and row[cluster_col]:
            cluster = str(row[cluster_col]).upper()
        else:
            cluster, _, _ = detect_offer_cluster(
                title,
                description,
                skills_map.get(offer_id, []),
            )

        if cluster not in CLUSTERS:
            cluster = "OTHER"

        entry = skills_map.get(offer_id, {"labels": [], "uris": []})
        raw_labels = entry.get("labels") or []
        raw_uris = entry.get("uris") or []
        if raw_labels:
            offers_with_any_skill_rows += 1
        count = len(set(raw_uris))
        skills_counts.append(count)

        # distribution
        if count == 0:
            dist["0"] += 1
        elif 1 <= count <= 3:
            dist["1-3"] += 1
        elif 4 <= count <= 10:
            dist["4-10"] += 1
        else:
            dist["10+"] += 1

        # cluster stats
        stats = cluster_stats[cluster]
        stats["offer_count"] += 1
        if count > 0:
            stats["offers_with_esco"] += 1
        stats.setdefault("_skills_counts", []).append(count)

    # global stats
    offers_with_uri = sum(1 for c in skills_counts if c > 0)
    offers_without_uri = total_offers - offers_with_uri
    coverage_ratio = _percent(offers_with_uri, total_offers)

    mean_skills_uri = round(sum(skills_counts) / total_offers, 2) if total_offers else 0.0
    median_skills_uri = _median(skills_counts)
    p90_skills_uri = _p90(skills_counts)
    max_skills_uri = max(skills_counts) if skills_counts else 0

    # finalize cluster stats
    for c in CLUSTERS:
        stats = cluster_stats[c]
        counts = stats.pop("_skills_counts", [])
        stats["coverage_ratio"] = _percent(stats["offers_with_esco"], stats["offer_count"])
        stats["mean_skills_uri"] = round(sum(counts) / stats["offer_count"], 2) if stats["offer_count"] else 0.0

    report = {
        "db_path": str(DB_PATH),
        "total_offers": total_offers,
        "offers_with_any_skill_rows": offers_with_any_skill_rows,
        "offers_with_esco": offers_with_uri,
        "offers_with_uri": offers_with_uri,
        "offers_without_esco": offers_without_uri,
        "offers_without_uri": offers_without_uri,
        "coverage_ratio": coverage_ratio,
        "uri_coverage_ratio": coverage_ratio,
        "skills_uri_count_distribution": dist,
        "stats": {
            "mean_skills_uri": mean_skills_uri,
            "median_skills_uri": median_skills_uri,
            "p90_skills_uri": p90_skills_uri,
            "max_skills_uri": max_skills_uri,
        },
        "cluster_macro_stats": cluster_stats,
        "top_skill_labels": top_skill_labels,
        "skill_uri_column_present": has_skill_uri,
    }

    OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("\nESCO COVERAGE REPORT")
    print(f"total offers: {total_offers}")
    print(f"uri coverage ratio: {coverage_ratio}%")
    for c in CLUSTERS:
        stats = cluster_stats[c]
        print(f"{c} coverage: {stats['coverage_ratio']}% (offers={stats['offer_count']})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
