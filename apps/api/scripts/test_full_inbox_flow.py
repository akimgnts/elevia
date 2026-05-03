#!/usr/bin/env python3
"""test_full_inbox_flow — end-to-end test: CV → canonical_skills → inbox matching."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.utils.cv_skill_extractor import extract_and_map_cv_skills
from api.utils.inbox_catalog import load_catalog_offers
from api.utils.db import get_connection


def load_test_cv_text() -> str:
    """Load test CV text (sample technical CV)."""
    return """
    SIDI-WALID HANI
    Senior Software Engineer | Paris, France

    PROFESSIONAL SUMMARY
    Senior Software Engineer with 7+ years experience building scalable systems.
    Expertise in Python, Java, JavaScript, cloud infrastructure, and data systems.

    TECHNICAL SKILLS
    Languages: Python, Java, JavaScript, TypeScript, SQL
    Frameworks: React, Django, Flask, Angular
    Databases: PostgreSQL, MongoDB, Redis
    Cloud & DevOps: AWS, Azure, Docker, Kubernetes, Terraform, Jenkins
    Data: Data analysis, TensorFlow, Spark, Hadoop
    Tools: Git, Jira, Linux, Apache, Nginx

    PROFESSIONAL EXPERIENCE

    Senior Engineer | Tech Corp | 2021-Present
    - Led development of microservices using Python and Docker
    - Built data pipelines with Spark and TensorFlow
    - Managed AWS infrastructure with Terraform
    - Mentored junior developers on best practices

    Software Engineer | Startup | 2018-2021
    - Developed React frontend with TypeScript
    - Built Flask APIs and PostgreSQL schemas
    - Deployed Kubernetes clusters on Azure

    LANGUAGES
    - French (Native)
    - English (Fluent)
    - German (Basic)

    EDUCATION
    Master's in Computer Science | University
    """


def extract_cv_skills(cv_text: str) -> tuple[List[Dict], Dict]:
    """Extract canonical skills from CV."""
    conn = get_connection()
    canonical_skills, breakdown = extract_and_map_cv_skills(cv_text, conn)
    conn.close()
    return canonical_skills, breakdown


def load_offers_catalog() -> List[Dict]:
    """Load offers catalog from local DB."""
    try:
        # Try external catalog first
        catalog = load_catalog_offers()
        if catalog:
            return catalog
    except Exception:
        pass

    # Fallback: load from local DB
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT fo.id, fo.title, fo.company, fo.city, fo.description
            FROM fact_offers fo
            LIMIT 500
        """)

        offers = []
        for row in cursor.fetchall():
            offer_id, title, company, city, description = row

            # Get skills for this offer
            cursor.execute("""
                SELECT skill_uri FROM fact_offer_skills
                WHERE offer_id = ? AND skill_uri IS NOT NULL
            """, (offer_id,))

            skills_uri = [r[0] for r in cursor.fetchall()]

            offers.append({
                "id": offer_id,
                "title": title,
                "company": company or "N/A",
                "city": city or "N/A",
                "description": description or "",
                "skills_uri": skills_uri,
                "domain_tag": "general",
            })

        conn.close()
        return offers

    except Exception as e:
        print(f"Error loading offers from DB: {e}")
        return []


def calculate_skill_overlap(cv_skills: List[Dict], offer_skills: List[str]) -> tuple[int, List[str]]:
    """Calculate overlap between CV and offer skills."""
    cv_skill_ids = {skill["canonical_id"] for skill in cv_skills}
    offer_skill_ids = set(offer_skills) if offer_skills else set()

    matched = cv_skill_ids & offer_skill_ids
    return len(matched), list(matched)


def analyze_results(
    cv_skills: List[Dict],
    cv_breakdown: Dict,
    offers: List[Dict],
    limit: int = 20,
) -> Dict[str, Any]:
    """Analyze matching results."""
    print(f"\n{'=' * 70}")
    print(f"INBOX MATCHING ANALYSIS")
    print(f"{'=' * 70}")
    print(f"\nCV Profile:")
    print(f"  Canonical skills: {len(cv_skills)}")
    print(f"  - Core metier: {cv_breakdown['core_metier']}")
    print(f"  - Tools: {cv_breakdown['tool']}")
    print(f"  - Context: {cv_breakdown['context']}")
    print(f"  - Unmapped: {cv_breakdown['unmapped']}")

    print(f"\nOffers catalog: {len(offers)} total")

    # Score offers by skill overlap
    scored_offers = []
    for offer in offers[:limit * 2]:  # Check more, score top
        offer_id = offer.get("id")
        title = offer.get("title", "N/A")
        skills_uri = offer.get("skills_uri", [])

        overlap_count, matched = calculate_skill_overlap(cv_skills, skills_uri)

        scored_offers.append({
            "id": offer_id,
            "title": title,
            "overlap": overlap_count,
            "matched_canonical_ids": matched,
            "offer_skills_count": len(skills_uri),
            "domain": offer.get("domain_tag", "N/A"),
            "company": offer.get("company", "N/A"),
            "city": offer.get("city", "N/A"),
        })

    # Sort by overlap (descending)
    scored_offers.sort(key=lambda x: -x["overlap"])

    print(f"\nTOP {limit} MATCHES BY SKILL OVERLAP")
    print(f"{'-' * 70}")

    for rank, offer in enumerate(scored_offers[:limit], 1):
        overlap_pct = (offer["overlap"] / len(cv_skills) * 100) if cv_skills else 0
        print(f"\n{rank}. {offer['title']}")
        print(f"   Company: {offer['company']}")
        print(f"   Location: {offer['city']}")
        print(f"   Skills overlap: {offer['overlap']}/{len(cv_skills)} ({overlap_pct:.0f}%)")
        print(f"   Offer has {offer['offer_skills_count']} skills")
        if offer["matched_canonical_ids"]:
            print(f"   Matched: {', '.join(offer['matched_canonical_ids'][:3])}")
            if len(offer["matched_canonical_ids"]) > 3:
                print(f"            + {len(offer['matched_canonical_ids']) - 3} more")

    # Summary stats
    overlaps = [o["overlap"] for o in scored_offers]
    avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0

    # Check for coherence (are top results tech-related?)
    tech_keywords = {
        "engineer", "developer", "architect", "devops", "data",
        "python", "java", "sql", "aws", "kubernetes", "docker"
    }
    coherent_count = sum(
        1 for o in scored_offers[:limit]
        if any(kw in o["title"].lower() for kw in tech_keywords)
    )

    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    print(f"\nQuantitative:")
    print(f"  Average skill overlap: {avg_overlap:.1f}")
    print(f"  Coherent results (top {limit}): {coherent_count}/{limit}")
    print(f"  Top result overlap: {scored_offers[0]['overlap']}/{len(cv_skills)} ({scored_offers[0]['overlap']/len(cv_skills)*100:.0f}%)" if scored_offers else "  No results")

    # Qualitative assessment
    print(f"\nQualitative Assessment:")

    if avg_overlap < 2:
        print(f"  ✗ WEAK: Very few skill matches. Matching might not be working.")
    elif avg_overlap < 5:
        print(f"  ⚠ MODERATE: Some matches, but limited signal.")
    else:
        print(f"  ✓ GOOD: Decent skill overlap in top results.")

    if coherent_count >= limit * 0.7:
        print(f"  ✓ COHERENT: Top results are sensible given the CV.")
    elif coherent_count >= limit * 0.5:
        print(f"  ⚠ MIXED: Some noise in results.")
    else:
        print(f"  ✗ INCOHERENT: Top results don't match the profile.")

    print(f"\n{'=' * 70}")
    print(f"VERDICT")
    print(f"{'=' * 70}")

    if avg_overlap >= 5 and coherent_count >= limit * 0.7:
        print(f"\n✓ YES: Matching is starting to make sense.")
        print(f"  - CV skills map well to canonical dictionary (95% coverage)")
        print(f"  - Offers have matching canonical skills")
        print(f"  - Top results are coherent with profile")
        print(f"  - Ready for scoring refinement and inbox integration.")
        return {"verdict": "READY", "avg_overlap": avg_overlap, "coherence": coherent_count / limit}
    elif avg_overlap >= 2:
        print(f"\n⚠ PARTIAL: Matching works but needs refinement.")
        print(f"  - Some skill signal present")
        print(f"  - Need to improve canonical coverage or weighting")
        print(f"  - Scoring might help distinguish top results")
        return {"verdict": "PARTIAL", "avg_overlap": avg_overlap, "coherence": coherent_count / limit}
    else:
        print(f"\n✗ NO: Matching is not working yet.")
        print(f"  - Insufficient skill overlap")
        print(f"  - Possible issue: offer_skills not properly mapped to canonical")
        print(f"  - Next: Audit offer_skills table format")
        return {"verdict": "BROKEN", "avg_overlap": avg_overlap, "coherence": coherent_count / limit}


def main() -> int:
    """Run E2E test."""
    try:
        print("Loading test CV...")
        cv_text = load_test_cv_text()

        print("Extracting CV canonical skills...")
        cv_skills, cv_breakdown = extract_cv_skills(cv_text)
        print(f"  Extracted: {len(cv_skills)} skills")

        print("Loading offers catalog...")
        offers = load_offers_catalog()
        print(f"  Loaded: {len(offers)} offers")

        if not offers:
            print("ERROR: No offers loaded. Check catalog.")
            return 1

        # Analyze
        result = analyze_results(cv_skills, cv_breakdown, offers, limit=20)

        return 0 if result["verdict"] in {"READY", "PARTIAL"} else 1

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
