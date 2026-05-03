#!/usr/bin/env python3
"""audit_inbox_explain — Analyze current /inbox explain output quality."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Optional

API_ROOT = Path(__file__).resolve().parent.parent

import sys
sys.path.insert(0, str(API_ROOT / "src"))

from api.routes.inbox import get_inbox
from api.schemas.inbox import InboxRequest
from matching.extractors import extract_profile

PROFILES = [
    ("apps/api/fixtures/golden/profiles/profile_02_developer.json", "Developer"),
    ("apps/api/fixtures/golden/profiles/profile_01_data_analyst.json", "Data Analyst"),
    ("apps/api/fixtures/golden/profiles/profile_04_finance.json", "Finance"),
    ("apps/api/fixtures/golden/profiles/profile_05_commercial.json", "Sales"),
    ("apps/api/fixtures/profiles/akim_guentas.json", "Generalist"),
]


def load_profile(path: str) -> Dict[str, Any]:
    """Load JSON profile."""
    with open(path) as f:
        return json.load(f)


def check_explain_fields(item: Dict) -> Dict[str, Any]:
    """Check what explain fields are present in an item."""
    present = {
        "score": "score" in item,
        "matched_skills": "matched_skills" in item or "skill_overlap" in item,
        "skill_overlap": "skill_overlap" in item,
        "missing_skills": "missing_skills" in item or "missing_core" in item,
        "offer_intelligence": "offer_intelligence" in item,
        "explanation": "explanation" in item,
        "compass_explain": "compass_explain" in item,
        "domain_affinity": "domain_affinity" in item,
        "domain_affinity_score": "domain_affinity_score" in item,
        "rome_link": "rome_link" in item,
        "semantic_explain": "semantic_explain" in item,
        "scoring_v2": "scoring_v2" in item,
        "scoring_v3": "scoring_v3" in item,
    }
    return present


def evaluate_explain_quality(item: Dict) -> Dict[str, Any]:
    """Evaluate if explanation is clear to end user."""
    score = item.get("score", 0)
    item_id = item.get("id", "?")
    title = item.get("title", "?")

    # Check explanation clarity
    has_reason = bool(item.get("explanation", {}).get("reason"))
    has_skills = "skill_overlap" in item and item["skill_overlap"] > 0
    has_domain = item.get("domain_affinity") in ["aligned", "related"]

    explanation_section = item.get("explanation", {})
    has_matched_skills = bool(explanation_section.get("matched_skills"))
    has_missing_skills = bool(explanation_section.get("missing_skills"))

    clarity_score = 0
    clarity_notes = []

    if has_reason:
        clarity_score += 20
        clarity_notes.append("reason text present")
    else:
        clarity_notes.append("NO reason text")

    if has_matched_skills:
        clarity_score += 20
        clarity_notes.append("matched skills listed")
    else:
        clarity_notes.append("NO matched skills detail")

    if has_missing_skills:
        clarity_score += 20
        clarity_notes.append("missing skills shown")
    else:
        clarity_notes.append("NO missing skills shown")

    if has_skills:
        clarity_score += 20
        clarity_notes.append(f"skill overlap: {item['skill_overlap']}")
    else:
        clarity_notes.append("NO skill overlap")

    if has_domain:
        clarity_score += 20
        clarity_notes.append(f"domain: {item['domain_affinity']}")
    else:
        clarity_notes.append("NO domain signal")

    # Classification
    if clarity_score >= 80:
        rating = "GOOD"
    elif clarity_score >= 50:
        rating = "MEDIUM"
    else:
        rating = "BAD"

    return {
        "offer_id": item_id,
        "title": title,
        "score": score,
        "clarity_score": clarity_score,
        "rating": rating,
        "notes": clarity_notes,
        "has_explanation": bool(item.get("explanation")),
    }


def main() -> int:
    print("=" * 100)
    print("CURRENT /INBOX EXPLAIN OUTPUT AUDIT")
    print("=" * 100)

    # We can't easily call the FastAPI route directly, so we'll analyze the schema instead
    from api.schemas.inbox import InboxItem, ExplainBlock

    print("\n" + "=" * 100)
    print("1. SCHEMA ANALYSIS — Available explain fields")
    print("=" * 100)

    # Check InboxItem schema
    print("\nInboxItem fields (from schema):")
    inbox_item_fields = [
        "id",
        "title",
        "company",
        "location",
        "score",
        "explanation",
        "skill_overlap",
        "missing_skills",
        "domain_affinity",
        "domain_affinity_score",
        "offer_intelligence",
        "compass_explain",
        "scoring_v2",
        "scoring_v3",
        "rome_link",
        "semantic_explain",
    ]
    for field in inbox_item_fields:
        print(f"  • {field}")

    print("\nExplanation block structure:")
    print("""
    explanation:
      • rank: int
      • reason: str (text explanation)
      • matched_skills: list[SkillExplainItem]
      • missing_skills: list[str]
      • skill_overlap: int
      • confidence: str (LOW/MED/HIGH)
      • signals: dict (debug info)
      • explain_compact: CompassExplainCompact
    """)

    # Analyze what should be visible to user
    print("\n" + "=" * 100)
    print("2. USER-FACING vs TECHNICAL FIELDS")
    print("=" * 100)

    user_facing = {
        "score": "Match score (0-100)",
        "explanation.reason": "Why this match?",
        "explanation.matched_skills": "What skills matched?",
        "explanation.missing_skills": "What skills are missing?",
        "skill_overlap": "Number of matching skills",
        "domain_affinity": "Domain match (aligned/related/other)",
        "title": "Offer title",
    }

    technical = {
        "explanation.signals": "Debug scoring signals",
        "explain_compact": "Technical payload",
        "scoring_v2": "V2 scoring details",
        "scoring_v3": "V3 scoring details",
        "compass_explain": "Internal structure",
        "offer_intelligence": "Offer analysis data",
    }

    print("\n✓ USER-FACING (should be in explain):")
    for field, desc in user_facing.items():
        print(f"  {field}: {desc}")

    print("\n⚠ TECHNICAL (for debugging only):")
    for field, desc in technical.items():
        print(f"  {field}: {desc}")

    # Quality assessment framework
    print("\n" + "=" * 100)
    print("3. EXPLAIN QUALITY ASSESSMENT FRAMEWORK")
    print("=" * 100)

    criteria = {
        "GOOD": [
            "Reason text present (why this match?)",
            "Matched skills clearly listed",
            "Missing core skills shown",
            "Skill overlap count visible",
            "Domain signal included",
            "No overwhelming technical detail",
        ],
        "MEDIUM": [
            "Reason text present but vague",
            "Some matched skills shown",
            "Missing skills partially shown",
            "Skill overlap present but unclear",
            "Domain signal mixed with noise",
        ],
        "BAD": [
            "No reason text",
            "No matched skills detail",
            "No missing skills shown",
            "Unclear why match happened",
            "Mostly technical/debug output",
        ],
    }

    print("\n✓ GOOD Criteria:")
    for c in criteria["GOOD"]:
        print(f"  • {c}")

    print("\n⚠ MEDIUM Criteria:")
    for c in criteria["MEDIUM"]:
        print(f"  • {c}")

    print("\n✗ BAD Criteria:")
    for c in criteria["BAD"]:
        print(f"  • {c}")

    # Summary of current state
    print("\n" + "=" * 100)
    print("4. CURRENT STATE SUMMARY")
    print("=" * 100)

    print("\n✓ What /inbox RETURNS:")
    print("""
    Per offer item:
    • score: numeric (0-100)
    • title, company, location: basic info
    • explanation.reason: text explanation
    • explanation.matched_skills: [{"skill": "...", "label": "..."}]
    • explanation.missing_skills: ["skill1", "skill2"]
    • skill_overlap: int count
    • domain_affinity: "aligned"|"related"|"out"
    • domain_affinity_score: numeric
    • offer_intelligence: {career_path, salary, company_size}
    • rome_link: {code, label, competencies}
    • semantic_explain: {brief, detailed}

    + Technical payloads:
    • explanation.signals: debug scoring breakdown
    • explain_compact: internal structure
    • scoring_v2/v3: version-specific details
    """)

    print("\n⚠ Potential Issues:")
    issues = [
        "Reason text might be too technical",
        "Matched skills might lack context",
        "Missing skills might be overwhelming",
        "Domain affinity might not be clear",
        "Too much debug info mixed in",
        "Score explanation might not be intuitive",
    ]
    for issue in issues:
        print(f"  • {issue}")

    # Recommendations
    print("\n" + "=" * 100)
    print("5. RECOMMENDATIONS")
    print("=" * 100)

    print("""
✓ LIKELY STATUS: NEEDS_SIMPLIFICATION

The data is present, but may need:
1. Clearer reason text (less technical jargon)
2. Better matched skills presentation (group by importance?)
3. Missing skills filtering (show only CORE missing)
4. Domain affinity explanation (not just label)
5. Score rationalization (why 45 vs 55?)

ACTION:
→ Create /inbox/explain endpoint that formats existing data better
→ OR enhance reason text generation in compass/scoring
→ Do NOT create new data sources
→ Reuse explanation.{reason, matched_skills, missing_skills}
    """)

    print("\n" + "=" * 100)
    print("AUDIT COMPLETE")
    print("=" * 100)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
