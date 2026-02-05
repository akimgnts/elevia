"""
test_profile_v1.py - Profil artificiel stable pour tests E2E matching
Sprint Debug - Harness de test reproductible
"""

# Profil test avec skills normalisées (lowercase, sans ponctuation)
# Format exact attendu par extract_profile() dans extractors.py
TEST_PROFILE_V1 = {
    "id": "test_profile_v1",
    "matching_skills": [
        "python",
        "sql",
        "power bi",
        "data analysis",
        "etl",
        "fastapi",
        "git",
        "excel",
        "pandas",
        "postgresql",
    ],
    "languages": ["fr", "en"],
    "education": "bac+5",
    "preferred_countries": ["france", "allemagne", "espagne"],
}


# Offres mock garantissant un match
# Offer A: fort match skills (python, sql, fastapi)
# Offer B: pas de match skills (sales, negotiation)
MOCK_OFFERS = [
    {
        "id": "mock_offer_a",
        "title": "Data Engineer VIE",
        "company": "TechCorp",
        "country": "France",
        "city": "Paris",
        "is_vie": True,
        "skills": ["python", "sql", "fastapi", "docker", "aws"],
        "languages": ["fr", "en"],
        "education": "bac+5",
    },
    {
        "id": "mock_offer_b",
        "title": "Sales Manager VIE",
        "company": "SalesCorp",
        "country": "Espagne",
        "city": "Madrid",
        "is_vie": True,
        "skills": ["sales", "negotiation", "crm", "cold calling"],
        "languages": ["en", "es"],
        "education": "bac+3",
    },
    {
        "id": "mock_offer_c",
        "title": "BI Analyst VIE",
        "company": "DataViz Inc",
        "country": "Allemagne",
        "city": "Berlin",
        "is_vie": True,
        "skills": ["power bi", "sql", "excel", "data analysis"],
        "languages": ["en"],
        "education": "bac+5",
    },
]


def get_test_profile():
    """Retourne le profil test (copie pour éviter mutation)."""
    return dict(TEST_PROFILE_V1)


def get_mock_offers():
    """Retourne les offres mock (copie pour éviter mutation)."""
    return [dict(o) for o in MOCK_OFFERS]
