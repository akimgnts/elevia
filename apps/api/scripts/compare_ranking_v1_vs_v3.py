#!/usr/bin/env python3
"""compare_ranking_v1_vs_v3 — compare ranking quality for a real CV.

Parses a CV, extracts skills, and scores offers against both V1 (v2 skills)
and V3+fallback (v3_metier + v3_fallback skills) without modifying the core
scoring logic.

Usage:
    DATABASE_URL=postgresql://... python3 apps/api/scripts/compare_ranking_v1_vs_v3.py \
        --cv-path /path/to/cv.pdf
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT / "src"))

# Import compass pipeline
from compass.pipeline import build_parse_file_response_payload
from compass.pipeline.contracts import ParseFilePipelineRequest


def extract_skills_from_cv(cv_path: str) -> dict[str, Any]:
    """Parse CV and extract structured profile."""
    with open(cv_path, "rb") as f:
        file_bytes = f.read()

    request = ParseFilePipelineRequest(
        request_id="v1_vs_v3_comparison",
        raw_filename=Path(cv_path).name,
        content_type="application/pdf",
        file_bytes=file_bytes,
        enrich_llm=0,
    )

    response = build_parse_file_response_payload(request)
    return response


def score_offers_v1(conn, profile_skills_uri: list[str], limit: int = 10) -> list[dict[str, Any]]:
    """Score offers using V1 (v2_skills via offer_skills_v2)."""
    from matching.matching_v1 import MatchingEngine  # noqa: E402
    from matching.idf import IDFStore  # noqa: E402

    # Load catalog
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, source, external_id, title, description
            FROM clean_offers
            WHERE source = 'business_france'
            LIMIT 500
        """)
        offers = [
            {
                "id": r[0],
                "source": r[1],
                "external_id": r[2],
                "title": r[3],
                "description": r[4],
            }
            for r in cur.fetchall()
        ]

        # Load skills for offers (V1)
        cur.execute("""
            SELECT offer_id, canonical_id, label, importance_level
            FROM offer_skills
            WHERE enrichment_version = 'offer_skills_v2'
        """)
        offer_skills_map = {}
        for r in cur.fetchall():
            offer_id = r[0]
            if offer_id not in offer_skills_map:
                offer_skills_map[offer_id] = []
            offer_skills_map[offer_id].append(
                {
                    "id": r[1],
                    "label": r[2],
                    "importance_level": r[3],
                }
            )

    # Convert to frozensets for matching
    profile_skills_uri = frozenset(profile_skills_uri)
    offers_with_skills = []
    for offer in offers:
        skills = offer_skills_map.get(offer["id"], [])
        offer_skills_uri = frozenset(s["id"] for s in skills if s.get("id"))
        offers_with_skills.append({**offer, "skills_uri": offer_skills_uri, "skills": skills})

    # Score using V1 matching
    engine = MatchingEngine()
    idf = IDFStore()

    results = []
    for offer in offers_with_skills:
        score = engine.score(profile_skills_uri, offer["skills_uri"], idf)
        results.append(
            {
                "id": offer["id"],
                "title": offer["title"],
                "score": score,
                "skills_count": len(offer["skills"]),
                "version": "V1",
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def score_offers_v3(conn, profile_skills_uri: list[str], limit: int = 10) -> list[dict[str, Any]]:
    """Score offers using V3 (v3_metier + v3_fallback)."""
    from matching.matching_v1 import MatchingEngine  # noqa: E402
    from matching.idf import IDFStore  # noqa: E402

    # Load catalog
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, source, external_id, title, description
            FROM clean_offers
            WHERE source = 'business_france'
            LIMIT 500
        """)
        offers = [
            {
                "id": r[0],
                "source": r[1],
                "external_id": r[2],
                "title": r[3],
                "description": r[4],
            }
            for r in cur.fetchall()
        ]

        # Load skills for offers (V3)
        cur.execute("""
            SELECT offer_id, canonical_id, label, importance_level
            FROM offer_skills
            WHERE enrichment_version IN ('offer_skills_v3_metier', 'offer_skills_v3_fallback')
        """)
        offer_skills_map = {}
        for r in cur.fetchall():
            offer_id = r[0]
            if offer_id not in offer_skills_map:
                offer_skills_map[offer_id] = []
            offer_skills_map[offer_id].append(
                {
                    "id": r[1],
                    "label": r[2],
                    "importance_level": r[3],
                }
            )

    # Convert to frozensets for matching
    profile_skills_uri = frozenset(profile_skills_uri)
    offers_with_skills = []
    for offer in offers:
        skills = offer_skills_map.get(offer["id"], [])
        offer_skills_uri = frozenset(s["id"] for s in skills if s.get("id"))
        offers_with_skills.append({**offer, "skills_uri": offer_skills_uri, "skills": skills})

    # Score using V1 matching (same engine, different skills)
    engine = MatchingEngine()
    idf = IDFStore()

    results = []
    for offer in offers_with_skills:
        score = engine.score(profile_skills_uri, offer["skills_uri"], idf)
        results.append(
            {
                "id": offer["id"],
                "title": offer["title"],
                "score": score,
                "skills_count": len(offer["skills"]),
                "version": "V3+Fallback",
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cv-path", required=True, help="Path to CV PDF")
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        return 2

    cv_path = Path(args.cv_path)
    if not cv_path.exists():
        print(f"ERROR: CV file not found: {cv_path}", file=sys.stderr)
        return 2

    print(f"Parsing CV: {cv_path.name}")
    try:
        profile_response = extract_skills_from_cv(str(cv_path))
    except Exception as e:
        print(f"ERROR: Failed to parse CV: {e}", file=sys.stderr)
        return 1

    # Extract skills from profile
    career_profile = profile_response.get("career_profile", {})
    selected_skills = career_profile.get("selected_skills", [])
    canonical_skills = career_profile.get("canonical_skills", [])

    profile_skills_uri = [s.get("id") or s.get("canonical_id") for s in canonical_skills if s.get("id") or s.get("canonical_id")]

    print(f"Profile: {career_profile.get('inferred_domain')} domain")
    print(f"Skills extracted: {len(profile_skills_uri)}")
    print(f"Sample skills: {profile_skills_uri[:5]}")

    import psycopg

    with psycopg.connect(database_url, connect_timeout=15) as conn:
        print("\n" + "=" * 80)
        print("SCORING V1 (V2 skills)...")
        print("=" * 80)
        v1_results = score_offers_v1(conn, profile_skills_uri, limit=10)

        for idx, item in enumerate(v1_results, 1):
            print(f"{idx:2}. [{item['score']:3}] {item['title'][:60]}")

        print("\n" + "=" * 80)
        print("SCORING V3 (V3_metier + fallback)...")
        print("=" * 80)
        v3_results = score_offers_v3(conn, profile_skills_uri, limit=10)

        for idx, item in enumerate(v3_results, 1):
            print(f"{idx:2}. [{item['score']:3}] {item['title'][:60]}")

        # Comparison
        print("\n" + "=" * 80)
        print("COMPARISON")
        print("=" * 80)

        v1_ids = [r["id"] for r in v1_results]
        v3_ids = [r["id"] for r in v3_results]

        common = len(set(v1_ids) & set(v3_ids))
        only_v1 = len(set(v1_ids) - set(v3_ids))
        only_v3 = len(set(v3_ids) - set(v1_ids))

        print(f"Common in top 10: {common}")
        print(f"Only in V1: {only_v1}")
        print(f"Only in V3: {only_v3}")

        # Show differences
        if only_v1 > 0:
            print(f"\nOffers in V1 but not V3 top 10:")
            for v1_item in v1_results:
                if v1_item["id"] not in v3_ids:
                    print(f"  [{v1_item['score']}] {v1_item['title'][:60]}")

        if only_v3 > 0:
            print(f"\nOffers in V3 but not V1 top 10:")
            for v3_item in v3_results:
                if v3_item["id"] not in v1_ids:
                    print(f"  [{v3_item['score']}] {v3_item['title'][:60]}")

    print("\n✓ Comparison complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
