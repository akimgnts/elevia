#!/usr/bin/env python3
"""test_multi_profile_matching — Test V3 canonical matching across multiple profiles."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, Set, List, Tuple, Any

API_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = API_ROOT / "data" / "db" / "offers.db"

import sys
sys.path.insert(0, str(API_ROOT / "src"))

from matching.extractors import extract_profile

# Selected profiles
PROFILES = [
    ("apps/api/fixtures/golden/profiles/profile_02_developer.json", "Developer"),
    ("apps/api/fixtures/golden/profiles/profile_01_data_analyst.json", "Data Analyst"),
    ("apps/api/fixtures/golden/profiles/profile_04_finance.json", "Finance"),
    ("apps/api/fixtures/golden/profiles/profile_05_commercial.json", "Sales"),
    ("apps/api/fixtures/profiles/akim_guentas.json", "Generalist/Data"),
]


def load_profile(path: str) -> Dict[str, Any]:
    """Load JSON profile."""
    with open(path) as f:
        return json.load(f)


def extract_canonical_skills(profile: Dict) -> Tuple[Set[str], Set[str], int]:
    """Extract skills from profile.

    Returns (raw_skills, canonical_metier_skills, total_canonical_count).
    """
    try:
        extracted = extract_profile(profile)
        raw = set(extracted.skills) if extracted.skills else set()
        metier = {s for s in raw if isinstance(s, str) and 'metier:' in s.lower()}
        canonical_count = len(extracted.skills_uri) if extracted.skills_uri else 0
        return raw, metier, canonical_count
    except Exception as e:
        print(f"    ERROR extracting: {e}")
        return set(), set(), 0


def normalize_skill(s: str) -> str:
    """Normalize skill for matching."""
    return s.lower().replace('_', ' ').replace('-', ' ').strip()


def get_top_matching_offers(
    conn: sqlite3.Connection,
    cv_skills: Set[str],
    limit: int = 10
) -> List[Tuple[str, int, List[Tuple[str, str]]]]:
    """Get top offers matching CV skills by metier:* overlap.

    Returns list of (offer_id, overlap_count, matched_pairs).
    """
    cursor = conn.cursor()

    # Get all offers with metier:* skills
    cursor.execute("""
        SELECT DISTINCT offer_id FROM fact_offer_skills
        WHERE skill_uri LIKE 'metier:%'
        ORDER BY offer_id
    """)
    offers = [row[0] for row in cursor.fetchall()]

    def normalize_skill_name(s: str) -> str:
        return normalize_skill(s)

    cv_normalized = {normalize_skill_name(s): s for s in cv_skills}
    scored = []

    for offer_id in offers:
        # Get metier:* skills for this offer
        cursor.execute("""
            SELECT skill, skill_uri FROM fact_offer_skills
            WHERE offer_id = ? AND skill_uri LIKE 'metier:%'
        """, (str(offer_id),))

        offer_skills = {(row[1], row[0]) for row in cursor.fetchall()}

        # Match against CV
        matched = []
        for uri, label in offer_skills:
            label_norm = normalize_skill_name(label)
            for cv_norm, cv_orig in cv_normalized.items():
                if cv_norm == label_norm or cv_norm in label_norm:
                    matched.append((cv_orig, label))
                    break

        if matched:
            scored.append((str(offer_id), len(matched), matched))

    # Sort by overlap count
    scored.sort(key=lambda x: (x[1], len(x[2])), reverse=True)
    return scored[:limit]


def coherence_check(overlap_count: int, cv_skills_count: int, offer_count: int) -> str:
    """Assess coherence of match."""
    if overlap_count == 0:
        return "BAD"
    pct = overlap_count / cv_skills_count * 100 if cv_skills_count > 0 else 0
    if pct >= 25:
        return "GOOD"
    elif pct >= 10:
        return "MEDIUM"
    else:
        return "BAD"


def main() -> int:
    print("=" * 90)
    print("MULTI-PROFILE V3 CANONICAL MATCHING TEST")
    print("=" * 90)

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    results = []

    for profile_path, domain in PROFILES:
        full_path = Path(profile_path)
        if not full_path.exists():
            print(f"\n⚠ SKIP {domain}: file not found at {profile_path}")
            continue

        print(f"\n{'=' * 90}")
        print(f"PROFILE: {domain} ({full_path.name})")
        print(f"{'=' * 90}")

        profile = load_profile(profile_path)
        profile_id = profile.get("profile_id", "unknown")
        raw_skills, metier_skills, canonical_count = extract_canonical_skills(profile)

        print(f"Profile ID: {profile_id}")
        print(f"Raw skills: {len(raw_skills)}")
        if raw_skills:
            print(f"  Sample: {', '.join(sorted(list(raw_skills)[:4]))}")
        print(f"Canonical count: {canonical_count}")
        print(f"Metier:* skills: {len(metier_skills)}")

        # Get top matching offers
        top_offers = get_top_matching_offers(conn, raw_skills, limit=10)

        print(f"\nTop 10 matching offers: {len(top_offers)}")

        if not top_offers:
            print("  (no matches)")
            avg_overlap = 0
            coherence = "BAD"
        else:
            avg_overlap = sum(x[1] for x in top_offers) / len(top_offers)
            print(f"  Average overlap: {avg_overlap:.1f} skills")

            for rank, (offer_id, overlap, pairs) in enumerate(top_offers, 1):
                pct = overlap / len(raw_skills) * 100 if raw_skills else 0
                print(f"  {rank}. Offer {offer_id}: {overlap}/{len(raw_skills)} ({pct:.0f}%)")
                if pairs:
                    pairs_str = ', '.join(f"{cv}→{offer}" for cv, offer in pairs[:2])
                    print(f"     Match: {pairs_str}")

            if top_offers:
                coherence = coherence_check(top_offers[0][1], len(raw_skills), len(top_offers))

        print(f"\nCOHERENCE: {coherence}")

        results.append({
            "domain": domain,
            "file": str(full_path),
            "profile_id": profile_id,
            "raw_skills": len(raw_skills),
            "canonical_count": canonical_count,
            "metier_skills": len(metier_skills),
            "top_10_matches": len(top_offers),
            "avg_overlap": avg_overlap if top_offers else 0,
            "coherence": coherence,
            "top_offers": top_offers,
        })

    conn.close()

    # Summary
    print(f"\n{'=' * 90}")
    print("SUMMARY")
    print(f"{'=' * 90}")

    print(f"\nProfiles tested: {len(results)}")
    for r in results:
        print(f"  {r['domain']}: {r['canonical_count']} canonical → {r['top_10_matches']} matches ({r['coherence']})")

    avg_canonical = sum(r["canonical_count"] for r in results) / len(results) if results else 0
    good_count = sum(1 for r in results if r["coherence"] == "GOOD")
    medium_count = sum(1 for r in results if r["coherence"] == "MEDIUM")
    bad_count = sum(1 for r in results if r["coherence"] == "BAD")

    print(f"\nCanonical coverage avg: {avg_canonical:.1f} skills/profile")
    print(f"Coherence distribution:")
    print(f"  GOOD: {good_count}/{len(results)}")
    print(f"  MEDIUM: {medium_count}/{len(results)}")
    print(f"  BAD: {bad_count}/{len(results)}")

    if good_count >= len(results) * 0.6:
        recommendation = "✓ V3 MATCHING VALIDATED"
    elif good_count + medium_count >= len(results) * 0.6:
        recommendation = "⚠ V3 MATCHING PARTIAL - needs tuning"
    else:
        recommendation = "✗ V3 MATCHING INSUFFICIENT DATA"

    print(f"\nRECOMMENDATION: {recommendation}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
