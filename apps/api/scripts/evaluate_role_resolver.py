#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.roles.role_resolver import RoleResolver
from esco.extract import extract_raw_skills_from_offer
from profile.baseline_parser import run_baseline, run_baseline_from_tokens

SAMPLE_PROFILES = [
    {
        "id": "profile_1",
        "cv_text": """
        Alex Martin
        Senior Software Developer
        Built backend services in Python, Java, SQL, Git, Docker and AWS.
        Developed React and TypeScript applications and automated CI/CD pipelines.
        """,
    },
    {
        "id": "profile_2",
        "cv_text": """
        Claire Dupont
        Chef de projet digital
        Pilotage de projets web, coordination des parties prenantes, reporting KPI, CRM, SEO et campagnes marketing digital.
        """,
    },
    {
        "id": "profile_3",
        "cv_text": """
        Malik Ben Saïd
        Analyste de données
        Analyse de données, SQL, Power BI, visualisation de données et reporting opérationnel.
        """,
    },
]

SAMPLE_OFFERS = [
    {
        "id": "offer_1",
        "title": "Software Developer",
        "description": "Build Python APIs, maintain SQL data pipelines, use Git and Docker.",
    },
    {
        "id": "offer_2",
        "title": "Digital Project Manager",
        "description": "Manage digital projects, coordinate stakeholders, report KPIs, improve CRM and digital campaigns.",
    },
    {
        "id": "offer_3",
        "title": "Data Analyst",
        "description": "Analyze operational datasets with SQL and Power BI, build dashboards and reporting.",
    },
]


def evaluate_profiles(resolver: RoleResolver) -> list[dict[str, object]]:
    results = []
    for sample in SAMPLE_PROFILES:
        baseline = run_baseline(sample["cv_text"], profile_id=sample["id"])
        enriched = resolver.resolve_role_for_profile(
            {
                "cv_text": sample["cv_text"],
                "skills_canonical": baseline.get("skills_canonical") or [],
            },
            include_inferred_skills=True,
        )
        results.append(
            {
                "id": sample["id"],
                "type": "profile",
                "before_role_resolver": {
                    "canonical_skills": baseline.get("skills_canonical") or [],
                    "canonical_count": len(baseline.get("skills_canonical") or []),
                },
                "after_role_resolver": enriched,
            }
        )
    return results


def evaluate_offers(resolver: RoleResolver) -> list[dict[str, object]]:
    results = []
    for sample in SAMPLE_OFFERS:
        raw_tokens = extract_raw_skills_from_offer(sample)
        baseline = run_baseline_from_tokens(raw_tokens, profile_id=sample["id"], source="offer-baseline")
        enriched = resolver.resolve_role_for_offer(
            {
                "title": sample["title"],
                "description": sample["description"],
                "skills_canonical": baseline.get("skills_canonical") or [],
            },
            include_inferred_skills=True,
        )
        results.append(
            {
                "id": sample["id"],
                "type": "offer",
                "before_role_resolver": {
                    "canonical_skills": baseline.get("skills_canonical") or [],
                    "canonical_count": len(baseline.get("skills_canonical") or []),
                },
                "after_role_resolver": enriched,
            }
        )
    return results


def compute_metrics(items: list[dict[str, object]]) -> dict[str, float]:
    total = len(items)
    resolved = 0
    confidence_sum = 0.0
    added_sum = 0.0
    false_positive = 0
    for item in items:
        after = item["after_role_resolver"]
        confidence = float(after.get("occupation_confidence") or 0.0)
        has_resolution = bool(after.get("candidate_occupations"))
        if has_resolution:
            resolved += 1
            confidence_sum += confidence
        added_sum += len(after.get("inferred_skills") or [])
        if has_resolution and confidence < 0.6:
            false_positive += 1
    return {
        "occupation_resolution_rate": round((resolved / total), 4) if total else 0.0,
        "average_confidence": round((confidence_sum / resolved), 4) if resolved else 0.0,
        "skills_added_avg": round((added_sum / total), 4) if total else 0.0,
        "false_positive_rate": round((false_positive / total), 4) if total else 0.0,
    }


def main() -> int:
    resolver = RoleResolver()
    profile_results = evaluate_profiles(resolver)
    offer_results = evaluate_offers(resolver)
    payload = {
        "profiles": profile_results,
        "offers": offer_results,
        "metrics": {
            "profiles": compute_metrics(profile_results),
            "offers": compute_metrics(offer_results),
            "overall": compute_metrics(profile_results + offer_results),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
