#!/usr/bin/env python3
"""test_inbox_metier_only — Matching test with metier:* skills only (ignoring garbage)."""
from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from typing import Set, Dict, List, Tuple, Any

API_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = API_ROOT / "data" / "db" / "offers.db"
CV_FIXTURE = API_ROOT / "fixtures" / "golden" / "profiles" / "profile_02_developer.json"

import sys
sys.path.insert(0, str(API_ROOT / "src"))

from matching.extractors import extract_profile


def load_test_cv() -> Dict:
    """Load test CV fixture."""
    if not CV_FIXTURE.exists():
        return {}
    with open(CV_FIXTURE) as f:
        return json.load(f)


def extract_cv_metier_skills(cv: Dict) -> Set[str]:
    """Extract CV skills and normalize to compare with metier:* offers."""
    try:
        profile = extract_profile(cv)
        # Use raw skill names from CV (e.g., 'python', 'javascript', 'react')
        skills: Set[str] = set()
        if hasattr(profile, 'skills') and profile.skills:
            skills = set(profile.skills)
        return skills
    except Exception as e:
        print(f"  Error extracting profile: {e}")
        return set()


def get_offer_metier_skills(conn: sqlite3.Connection, offer_id: str) -> Tuple[Set[str], Dict[str, str]]:
    """Get all metier:* skills for an offer.

    Returns (skill_uris, uri_to_label_map).
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT skill_uri, skill FROM fact_offer_skills
        WHERE offer_id = ? AND skill_uri LIKE 'metier:%'
        ORDER BY skill_uri
    """, (str(offer_id),))
    skills = set()
    labels = {}
    for uri, label in cursor.fetchall():
        skills.add(uri)
        labels[uri] = label
    return skills, labels


def get_all_offers_with_metier(conn: sqlite3.Connection) -> List[str]:
    """Get all distinct offer_ids that have metier:* skills."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT offer_id FROM fact_offer_skills
        WHERE skill_uri LIKE 'metier:%'
        ORDER BY offer_id
    """)
    return [row[0] for row in cursor.fetchall()]


def main() -> int:
    print("=" * 80)
    print("METIER:* SKILLS ONLY MATCHING TEST")
    print("=" * 80)

    # Load CV
    print("\nLoading CV...")
    cv = load_test_cv()
    if not cv:
        print("ERROR: CV fixture not found at", CV_FIXTURE)
        return 1

    print("Extracting CV canonical skills...")
    cv_metier_skills = extract_cv_metier_skills(cv)
    print(f"  CV has {len(cv_metier_skills)} metier:* skills:")
    for skill in sorted(cv_metier_skills):
        print(f"    - {skill}")

    if not cv_metier_skills:
        print("  ERROR: No metier:* skills extracted from CV")
        return 1

    # Load offers from SQLite
    print("\nConnecting to SQLite...")
    conn = sqlite3.connect(str(DB_PATH), timeout=10)

    # Get all offers with metier:* skills
    print("Loading offers with metier:* skills...")
    offers_with_metier = get_all_offers_with_metier(conn)
    print(f"  Found {len(offers_with_metier)} offers with metier:* skills")

    # Score offers
    print("\nScoring offers by metier:* skill overlap...")
    scored_offers: List[Tuple[str, List[Tuple[str, str]], int, int, float]] = []

    def normalize_skill(s: str) -> str:
        """Normalize skill name for matching."""
        return s.lower().replace('_', ' ').replace('-', ' ').strip()

    cv_normalized = {normalize_skill(s): s for s in cv_metier_skills}

    for offer_id in offers_with_metier:
        offer_uris, uri_labels = get_offer_metier_skills(conn, offer_id)

        # Match CV skills against offer skill labels
        matched_pairs = []
        for uri in offer_uris:
            label = uri_labels.get(uri, uri)
            label_normalized = normalize_skill(label)

            for cv_normalized_skill, cv_original_skill in cv_normalized.items():
                if cv_normalized_skill == label_normalized or cv_normalized_skill in label_normalized:
                    matched_pairs.append((cv_original_skill, label))
                    break

        overlap_count = len(matched_pairs)
        offer_skill_count = len(offer_uris)
        overlap_pct = (overlap_count / len(cv_metier_skills) * 100) if cv_metier_skills else 0

        if overlap_count > 0:  # Only include offers with at least 1 match
            scored_offers.append((
                str(offer_id),
                matched_pairs,
                overlap_count,
                offer_skill_count,
                overlap_pct
            ))

    # Sort by overlap count (descending)
    scored_offers.sort(key=lambda x: (x[2], x[3]), reverse=True)

    print(f"  Offers with ≥1 match: {len(scored_offers)}")
    print(f"  Average overlap: {sum(x[2] for x in scored_offers) / len(scored_offers):.1f} skills" if scored_offers else "  No matches")

    # Top 20
    print("\n" + "=" * 80)
    print("TOP 20 OFFERS BY METIER:* SKILL OVERLAP")
    print("=" * 80)

    for i, (offer_id, matched_pairs, overlap_count, offer_skill_count, pct) in enumerate(scored_offers[:20], 1):
        print(f"\n{i}. Offer {offer_id}")
        print(f"   Matched: {overlap_count} / {len(cv_metier_skills)} CV skills ({pct:.0f}%)")
        print(f"   Offer has: {offer_skill_count} metier:* skills")
        if matched_pairs:
            print(f"   Matched: {', '.join(f'{cv}→{offer}' for cv, offer in matched_pairs)}")

    # Summary stats
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    matches_top10 = sum(1 for x in scored_offers[:10] if x[2] > 0)
    matches_top20 = sum(1 for x in scored_offers[:20] if x[2] > 0)
    avg_overlap_top10 = sum(x[2] for x in scored_offers[:10]) / min(10, len(scored_offers)) if scored_offers else 0
    avg_overlap_top20 = sum(x[2] for x in scored_offers[:20]) / min(20, len(scored_offers)) if scored_offers else 0

    print(f"Total offers with ≥1 metier:* match: {len(scored_offers)}")
    print(f"Top 10: {matches_top10}/10 with matches, avg overlap: {avg_overlap_top10:.1f} skills")
    print(f"Top 20: {matches_top20}/20 with matches, avg overlap: {avg_overlap_top20:.1f} skills")

    if len(scored_offers) > 0:
        print(f"\nTop offer: {scored_offers[0][0]} ({scored_offers[0][2]}/{len(cv_metier_skills)} match)")
        print(f"Worst in top 20: {scored_offers[19][0] if len(scored_offers) >= 20 else scored_offers[-1][0]} ({scored_offers[-1][2] if len(scored_offers) < 20 else scored_offers[19][2]}/{len(cv_metier_skills)} match)")

    # Coherence check
    print("\n" + "=" * 80)
    print("COHERENCE CHECK")
    print("=" * 80)

    if len(scored_offers) == 0:
        print("✗ INCOHERENT: No metier:* skill matches found")
        coherence = "FAILED"
    elif len(scored_offers) < 10:
        print(f"⚠ WEAK: Only {len(scored_offers)} offers with metier:* matches")
        coherence = "WEAK"
    elif avg_overlap_top20 >= 1.5:
        print(f"✓ STRONG: Top 20 average overlap {avg_overlap_top20:.1f} skills")
        coherence = "STRONG"
    elif avg_overlap_top20 >= 0.5:
        print(f"✓ MODERATE: Top 20 average overlap {avg_overlap_top20:.1f} skills")
        coherence = "MODERATE"
    else:
        print(f"⚠ WEAK: Top 20 average overlap {avg_overlap_top20:.1f} skills")
        coherence = "WEAK"

    print("\n" + "=" * 80)
    print(f"RESULT: {coherence}")
    print("=" * 80)

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
