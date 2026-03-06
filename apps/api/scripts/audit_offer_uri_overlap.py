#!/usr/bin/env python3
"""
audit_offer_uri_overlap.py
Read-only audit: ESCO URI coverage + overlap with a parsed profile.

Usage:
  python apps/api/scripts/audit_offer_uri_overlap.py \
    --profile-json /tmp/parse_esco_on.json --top 50 --cluster DATA_IT
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Set, Tuple

DEFAULT_DB = Path(__file__).parent.parent / "data" / "db" / "offers.db"
DEFAULT_PROFILE_JSON = Path("/tmp/parse_esco_on.json")
OUT_PATH = Path("/tmp/elevia_offer_uri_overlap.json")
ESCO_PREFIX = "http://data.europa.eu/esco/"
COMPASS_PREFIX = "compass:"


def _get_columns(conn: sqlite3.Connection, table: str) -> Set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _select_cluster_column(columns: Set[str]) -> str | None:
    for candidate in ("cluster_macro", "offer_cluster", "cluster"):
        if candidate in columns:
            return candidate
    return None


def _build_where(cluster_col: str | None, args, offers_cols: Set[str]) -> Tuple[str, List[object]]:
    where: List[str] = []
    params: List[object] = []

    if cluster_col:
        where.append(f"fo.{cluster_col} = ?")
        params.append(args.cluster)

    if args.source and "source" in offers_cols:
        where.append("fo.source = ?")
        params.append(args.source)

    if not cluster_col and "is_vie" in offers_cols:
        # fallback filter when no cluster column
        where.append("(fo.is_vie = 1 OR fo.is_vie = 'true' OR fo.is_vie = 'True')")

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    return where_sql, params


def _load_profile_sets(profile_json: Path) -> Dict[str, List[str]]:
    data = json.loads(profile_json.read_text(encoding="utf-8"))
    profile = data.get("profile") if isinstance(data, dict) else None
    if not isinstance(profile, dict):
        profile = data if isinstance(data, dict) else {}

    base = [str(u) for u in (profile.get("skills_uri") or []) if isinstance(u, str)]
    promoted = [str(u) for u in (profile.get("skills_uri_promoted") or []) if isinstance(u, str)]
    effective = sorted(set(base) | set(promoted))
    return {
        "skills_uri": sorted(set(base)),
        "skills_uri_promoted": sorted(set(promoted)),
        "skills_uri_effective": effective,
    }


def _split_namespaces(uris: Set[str]) -> Dict[str, Set[str]]:
    esco = {u for u in uris if u.startswith(ESCO_PREFIX)}
    compass = {u for u in uris if u.startswith(COMPASS_PREFIX)}
    other = {u for u in uris if u not in esco and u not in compass}
    return {"esco": esco, "compass": compass, "other": other}


def _namespace_set(uris: Set[str], namespace: str) -> Set[str]:
    if namespace == "esco":
        return {u for u in uris if u.startswith(ESCO_PREFIX)}
    if namespace == "compass":
        return {u for u in uris if u.startswith(COMPASS_PREFIX)}
    return set(uris)


def _build_overlap_gaps(
    *,
    offer_uri_counts: List[Dict[str, object]],
    offer_uri_set: Set[str],
    promoted_set: Set[str],
    effective_set: Set[str],
    gaps_top: int,
) -> Dict[str, object]:
    promoted_overlap = sorted(promoted_set & offer_uri_set)
    effective_overlap = sorted(effective_set & offer_uri_set)
    promoted_missing = sorted(promoted_set - offer_uri_set)
    effective_missing = sorted(effective_set - offer_uri_set)

    # Gaps: top offer URIs missing in profile effective (by count)
    offer_uri_count_map = {item["uri"]: item["count"] for item in offer_uri_counts}
    top_offer_missing = [
        item for item in offer_uri_counts if item["uri"] not in effective_set
    ][:gaps_top]

    # Gaps: profile URIs missing in offers (by offer_count asc)
    profile_missing = [
        {"uri": uri, "offer_count": offer_uri_count_map.get(uri, 0)}
        for uri in sorted(effective_set)
        if uri not in offer_uri_set
    ]
    profile_missing_sorted = sorted(
        profile_missing, key=lambda x: (x["offer_count"], x["uri"])
    )
    top_profile_missing = profile_missing_sorted[:gaps_top]

    return {
        "promoted_overlap_count": len(promoted_overlap),
        "effective_overlap_count": len(effective_overlap),
        "promoted_overlap_uris": promoted_overlap,
        "effective_overlap_uris": effective_overlap,
        "promoted_missing_uris": promoted_missing,
        "effective_missing_uris": effective_missing,
        "top_offer_missing": top_offer_missing,
        "top_profile_missing": top_profile_missing,
    }


def build_report(
    *,
    db_path: Path,
    profile_json: Path,
    cluster: str,
    top_n: int,
    gaps_top: int,
    source: str | None = None,
    namespace: str = "esco",
) -> Dict[str, object]:
    if not db_path.exists():
        return {"error": "DB_MISSING", "db_path": str(db_path)}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    offers_cols = _get_columns(conn, "fact_offers")
    skills_cols = _get_columns(conn, "fact_offer_skills")
    cluster_col = _select_cluster_column(offers_cols)

    class _Args:
        def __init__(self, cluster: str, source: str | None) -> None:
            self.cluster = cluster
            self.source = source

    where_sql, params = _build_where(cluster_col, _Args(cluster, source), offers_cols)

    # total offers in cluster filter
    row = conn.execute(
        f"SELECT COUNT(*) as cnt FROM fact_offers fo {where_sql}", params
    ).fetchone()
    offers_total = int(row["cnt"]) if row else 0

    # offers with uri
    row = conn.execute(
        f"""
        SELECT COUNT(DISTINCT fos.offer_id) as cnt
        FROM fact_offer_skills fos
        JOIN fact_offers fo ON fo.id = fos.offer_id
        {where_sql}
          AND fos.skill_uri IS NOT NULL AND fos.skill_uri != ''
        """,
        params,
    ).fetchone()
    offers_with_uri = int(row["cnt"]) if row else 0

    # distinct URI count
    row = conn.execute(
        f"""
        SELECT COUNT(DISTINCT fos.skill_uri) as cnt
        FROM fact_offer_skills fos
        JOIN fact_offers fo ON fo.id = fos.offer_id
        {where_sql}
          AND fos.skill_uri IS NOT NULL AND fos.skill_uri != ''
        """,
        params,
    ).fetchone()
    offer_unique_uri_count = int(row["cnt"]) if row else 0

    # total uri rows for share
    row = conn.execute(
        f"""
        SELECT COUNT(*) as cnt
        FROM fact_offer_skills fos
        JOIN fact_offers fo ON fo.id = fos.offer_id
        {where_sql}
          AND fos.skill_uri IS NOT NULL AND fos.skill_uri != ''
        """,
        params,
    ).fetchone()
    total_uri_rows = int(row["cnt"]) if row else 0

    # all URI counts (sorted), then slice for top N / gaps
    all_rows = conn.execute(
        f"""
        SELECT fos.skill_uri as uri, COUNT(*) as cnt
        FROM fact_offer_skills fos
        JOIN fact_offers fo ON fo.id = fos.offer_id
        {where_sql}
          AND fos.skill_uri IS NOT NULL AND fos.skill_uri != ''
        GROUP BY fos.skill_uri
        ORDER BY cnt DESC, uri ASC
        """,
        params,
    ).fetchall()

    all_offer_skill_uris = [
        {
            "uri": r["uri"],
            "count": int(r["cnt"]),
            "share": round((int(r["cnt"]) / total_uri_rows), 4) if total_uri_rows else 0.0,
        }
        for r in all_rows
    ]
    top_offer_skill_uris = all_offer_skill_uris[:top_n]

    # offer URI set
    uri_rows = conn.execute(
        f"""
        SELECT DISTINCT fos.skill_uri as uri
        FROM fact_offer_skills fos
        JOIN fact_offers fo ON fo.id = fos.offer_id
        {where_sql}
          AND fos.skill_uri IS NOT NULL AND fos.skill_uri != ''
        """,
        params,
    ).fetchall()
    offer_uri_set = {str(r["uri"]) for r in uri_rows if r["uri"]}

    conn.close()

    # profile sets
    profile_sets = _load_profile_sets(profile_json)
    base_set = set(profile_sets["skills_uri"])
    promoted_set = set(profile_sets["skills_uri_promoted"])
    effective_set = set(profile_sets["skills_uri_effective"])

    namespaces = _split_namespaces(effective_set)
    base_esco = {u for u in base_set if u.startswith(ESCO_PREFIX)}
    promoted_esco = {u for u in promoted_set if u.startswith(ESCO_PREFIX)}
    effective_esco = namespaces["esco"]

    # namespace scoping
    offer_uri_set_ns = _namespace_set(offer_uri_set, namespace)
    offer_uri_counts_ns = [
        item for item in all_offer_skill_uris if item["uri"] in offer_uri_set_ns
    ]
    effective_ns = _namespace_set(effective_set, namespace)

    esco_overlap = _build_overlap_gaps(
        offer_uri_counts=all_offer_skill_uris,
        offer_uri_set={u for u in offer_uri_set if u.startswith(ESCO_PREFIX)},
        promoted_set=promoted_esco,
        effective_set=effective_esco,
        gaps_top=gaps_top,
    )
    compass_overlap = _build_overlap_gaps(
        offer_uri_counts=all_offer_skill_uris,
        offer_uri_set={u for u in offer_uri_set if u.startswith(COMPASS_PREFIX)},
        promoted_set={u for u in promoted_set if u.startswith(COMPASS_PREFIX)},
        effective_set=namespaces["compass"],
        gaps_top=gaps_top,
    )
    namespace_overlap = _build_overlap_gaps(
        offer_uri_counts=offer_uri_counts_ns,
        offer_uri_set=offer_uri_set_ns,
        promoted_set=_namespace_set(promoted_set, namespace),
        effective_set=effective_ns,
        gaps_top=gaps_top,
    )

    report = {
        "namespace": namespace,
        "cluster": cluster,
        "top_n": top_n,
        "db_path": str(db_path),
        "profile_json": str(profile_json),
        "offers_total_in_cluster": offers_total,
        "offers_with_uri": offers_with_uri,
        "offer_unique_uri_count": offer_unique_uri_count,
        "top_offer_skill_uris": top_offer_skill_uris,
        "profile": {
            "skills_uri_count": len(base_set),
            "skills_uri_promoted_count": len(promoted_set),
            "skills_uri_effective_count": len(effective_set),
            "skills_uri_esco_count": len(base_esco),
            "skills_uri_promoted_esco_count": len(promoted_esco),
            "skills_uri_effective_esco_count": len(effective_esco),
            "skills_uri_compass_count": len(namespaces["compass"]),
            "skills_uri_other_count": len(namespaces["other"]),
            "promoted_uris": sorted(promoted_set),
            "effective_uris": sorted(effective_set),
            "compass_uris": sorted(namespaces["compass"]),
            "other_uris": sorted(namespaces["other"]),
        },
        "overlap": {
            "promoted_overlap_count": namespace_overlap["promoted_overlap_count"],
            "effective_overlap_count": namespace_overlap["effective_overlap_count"],
            "promoted_overlap_uris": namespace_overlap["promoted_overlap_uris"],
            "effective_overlap_uris": namespace_overlap["effective_overlap_uris"],
            "promoted_missing_uris": namespace_overlap["promoted_missing_uris"],
            "effective_missing_uris_top20": namespace_overlap["effective_missing_uris"][:20],
        },
        "gaps": {
            "top_offer_uris_missing_in_profile_top20": namespace_overlap["top_offer_missing"],
            "top_profile_uris_missing_in_offers_top20": namespace_overlap["top_profile_missing"],
        },
        "counts": {
            "offer_unique_esco_count": len({u for u in offer_uri_set if u.startswith(ESCO_PREFIX)}),
            "offer_unique_compass_count": len({u for u in offer_uri_set if u.startswith(COMPASS_PREFIX)}),
            "profile_effective_esco_count": len(effective_esco),
            "profile_effective_compass_count": len(namespaces["compass"]),
        },
        "skill_uri_column_present": "skill_uri" in skills_cols,
        "cluster_column_used": cluster_col,
    }

    if namespace == "all":
        report["overlap_esco"] = {
            "promoted_overlap_count": esco_overlap["promoted_overlap_count"],
            "effective_overlap_count": esco_overlap["effective_overlap_count"],
            "promoted_overlap_uris": esco_overlap["promoted_overlap_uris"],
            "effective_overlap_uris": esco_overlap["effective_overlap_uris"],
            "promoted_missing_uris": esco_overlap["promoted_missing_uris"],
            "effective_missing_uris": esco_overlap["effective_missing_uris"],
        }
        report["overlap_compass"] = {
            "promoted_overlap_count": compass_overlap["promoted_overlap_count"],
            "effective_overlap_count": compass_overlap["effective_overlap_count"],
            "promoted_overlap_uris": compass_overlap["promoted_overlap_uris"],
            "effective_overlap_uris": compass_overlap["effective_overlap_uris"],
            "promoted_missing_uris": compass_overlap["promoted_missing_uris"],
            "effective_missing_uris": compass_overlap["effective_missing_uris"],
        }
        report["gaps_esco"] = {
            "top_offer_uris_missing_in_profile_top20": esco_overlap["top_offer_missing"],
            "top_profile_uris_missing_in_offers_top20": esco_overlap["top_profile_missing"],
        }
        report["gaps_compass"] = {
            "top_offer_uris_missing_in_profile_top20": compass_overlap["top_offer_missing"],
            "top_profile_uris_missing_in_offers_top20": compass_overlap["top_profile_missing"],
        }

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ESCO URI overlap with profile")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--profile-json", default=str(DEFAULT_PROFILE_JSON))
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument("--cluster", default="DATA_IT")
    parser.add_argument("--source", default=None)
    parser.add_argument("--gaps-top", type=int, default=20)
    parser.add_argument("--namespace", default="esco", choices=["esco", "compass", "all"])
    args = parser.parse_args()

    report = build_report(
        db_path=Path(args.db),
        profile_json=Path(args.profile_json),
        cluster=args.cluster,
        top_n=args.top,
        gaps_top=args.gaps_top,
        source=args.source,
        namespace=args.namespace,
    )
    if report.get("error") == "DB_MISSING":
        print(json.dumps(report, indent=2))
        return 1

    OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Console summary
    print("ESCO URI OVERLAP REPORT")
    print(f"cluster: {args.cluster}")
    print(
        f"offers_with_uri / offers_total: "
        f"{report['offers_with_uri']} / {report['offers_total_in_cluster']}"
    )
    print("top 10 URIs:")
    for item in report["top_offer_skill_uris"][:10]:
        print(f"- {item['uri']}  count={item['count']}  share={item['share']}")
    if args.namespace == "all":
        print(f"ESCO promoted overlap count: {report['overlap_esco']['promoted_overlap_count']}")
        print(f"ESCO effective overlap count: {report['overlap_esco']['effective_overlap_count']}")
        print(f"COMPASS promoted overlap count: {report['overlap_compass']['promoted_overlap_count']}")
        print(f"COMPASS effective overlap count: {report['overlap_compass']['effective_overlap_count']}")
    else:
        print(f"promoted overlap count: {report['overlap']['promoted_overlap_count']}")
        print(f"effective overlap count: {report['overlap']['effective_overlap_count']}")
    print(
        f"profile ESCO count: {report['profile']['skills_uri_effective_esco_count']} "
        f"| compass count: {report['profile']['skills_uri_compass_count']}"
    )
    if report["overlap"]["promoted_missing_uris"]:
        print("promoted missing (top 10):")
        for uri in report["overlap"]["promoted_missing_uris"][:10]:
            print(f"- {uri}")
    if args.namespace == "all":
        print("TOP offer URIs missing in profile (ESCO, 10):")
        for item in report["gaps_esco"]["top_offer_uris_missing_in_profile_top20"][:10]:
            print(f"- {item['uri']}  count={item['count']}  share={item['share']}")
        print("TOP offer URIs missing in profile (COMPASS, 10):")
        for item in report["gaps_compass"]["top_offer_uris_missing_in_profile_top20"][:10]:
            print(f"- {item['uri']}  count={item['count']}  share={item['share']}")
        print("TOP profile URIs missing in offers (ESCO, 10):")
        for item in report["gaps_esco"]["top_profile_uris_missing_in_offers_top20"][:10]:
            print(f"- {item['uri']}  offer_count={item['offer_count']}")
        print("TOP profile URIs missing in offers (COMPASS, 10):")
        for item in report["gaps_compass"]["top_profile_uris_missing_in_offers_top20"][:10]:
            print(f"- {item['uri']}  offer_count={item['offer_count']}")
    else:
        print("TOP offer URIs missing in profile (10):")
        for item in report["gaps"]["top_offer_uris_missing_in_profile_top20"][:10]:
            print(f"- {item['uri']}  count={item['count']}  share={item['share']}")
        print("TOP profile URIs missing in offers (10):")
        for item in report["gaps"]["top_profile_uris_missing_in_offers_top20"][:10]:
            print(f"- {item['uri']}  offer_count={item['offer_count']}")
    print(f"\nReport written: {OUT_PATH}")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
