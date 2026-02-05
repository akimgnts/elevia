#!/usr/bin/env python3
"""
Test du profil Akim Guentas contre le moteur de matching.
Vérifie que les scores sont non-triviaux et explicables.

Usage:
    cd apps/api
    python3 scripts/test_profile_matching.py
"""

import json
import sys
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from matching import MatchingEngine, extract_profile

# Charger le profil
PROFILE_PATH = Path(__file__).parent.parent / "fixtures" / "profiles" / "akim_guentas_matching.json"

with open(PROFILE_PATH) as f:
    PROFILE = json.load(f)

# Offres de test simulées (variées pour tester les scores)
TEST_OFFERS = [
    {
        "id": "test_match_high",
        "title": "Data Analyst - Reporting & KPI",
        "company": "Test Corp",
        "country": "France",
        "is_vie": True,
        "skills": ["data analysis", "power bi", "sql", "excel", "kpi", "reporting"],
        "languages": ["français", "anglais"],
        "education": "bac+5",
    },
    {
        "id": "test_match_medium",
        "title": "Business Analyst Junior",
        "company": "Test Corp",
        "country": "France",
        "is_vie": True,
        "skills": ["excel", "sql", "analyse", "tableau"],
        "languages": ["français"],
        "education": "bac+3",
    },
    {
        "id": "test_match_low",
        "title": "Software Engineer Backend",
        "company": "Test Corp",
        "country": "France",
        "is_vie": True,
        "skills": ["java", "spring", "kubernetes", "docker", "microservices"],
        "languages": ["anglais"],
        "education": "bac+5",
    },
    {
        "id": "test_match_ml",
        "title": "Data Scientist ML",
        "company": "Test Corp",
        "country": "France",
        "is_vie": True,
        "skills": ["python", "tensorflow", "pytorch", "machine learning", "deep learning"],
        "languages": ["anglais"],
        "education": "bac+5",
    },
    {
        "id": "test_no_skills",
        "title": "Assistant Administratif",
        "company": "Test Corp",
        "country": "France",
        "is_vie": True,
        "skills": [],
        "languages": ["français"],
        "education": "bac",
    },
]


def main():
    print("=" * 60)
    print("TEST PROFIL MATCHING - Akim Guentas V0")
    print("=" * 60)

    # Extraire le profil
    extracted = extract_profile(PROFILE)
    print(f"\nProfil ID: {extracted.profile_id}")
    print(f"Skills ({len(extracted.skills)}): {sorted(extracted.skills)[:10]}...")
    print(f"Languages: {sorted(extracted.languages)}")
    print(f"Education level: {extracted.education_level}")
    print(f"Preferred countries: {sorted(extracted.preferred_countries) if extracted.preferred_countries else 'all'}")

    # Créer le moteur
    engine = MatchingEngine(offers=TEST_OFFERS)

    print("\n" + "-" * 60)
    print("RÉSULTATS DE MATCHING")
    print("-" * 60)

    for offer in TEST_OFFERS:
        result = engine.score_offer(extracted, offer)
        print(f"\n{offer['title']}")
        print(f"  Score: {result.score}%")
        print(f"  Breakdown: skills={result.breakdown['skills']:.0%}, "
              f"lang={result.breakdown['languages']:.0%}, "
              f"edu={result.breakdown['education']:.0%}, "
              f"country={result.breakdown['country']:.0%}")
        print(f"  Reasons: {result.reasons[:2]}")

    print("\n" + "=" * 60)
    print("ANALYSE")
    print("=" * 60)

    scores = [(o["title"], engine.score_offer(extracted, o).score) for o in TEST_OFFERS]
    scores.sort(key=lambda x: x[1], reverse=True)

    print("\nClassement par score:")
    for title, score in scores:
        marker = "✓" if score >= 80 else "○" if score >= 50 else "✗"
        print(f"  {marker} {score:3d}% - {title}")

    # Vérifications
    print("\n" + "-" * 60)
    print("VÉRIFICATIONS")
    print("-" * 60)

    # High match doit être > 80%
    high_score = next(s for t, s in scores if "Reporting" in t)
    print(f"✓ High match (Data Analyst Reporting): {high_score}% {'≥80%' if high_score >= 80 else '<80% ATTENTION'}")

    # Low match (Software) doit être < 50%
    low_score = next(s for t, s in scores if "Software" in t)
    print(f"✓ Low match (Software Engineer): {low_score}% {'<50%' if low_score < 50 else '≥50% ATTENTION'}")

    # ML match doit être partiel (python match, mais pas ML skills)
    ml_score = next(s for t, s in scores if "ML" in t)
    print(f"✓ Partial match (Data Scientist ML): {ml_score}% (python=oui, ML=non)")

    print("\n" + "=" * 60)
    print("CONCLUSION")
    print("=" * 60)

    if high_score >= 80 and low_score < 50:
        print("✅ Profil valide - Les scores sont non-triviaux et explicables")
    else:
        print("⚠️ Profil à ajuster - Certains scores sont inattendus")


if __name__ == "__main__":
    main()
