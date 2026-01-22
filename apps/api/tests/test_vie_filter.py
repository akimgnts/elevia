"""
test_vie_filter.py - Tests du filtrage légal V.I.E
Sprint 11

Vérifie que les offres KO V.I.E sont TOUJOURS masquées.
"""

import pytest
from fastapi.testclient import TestClient

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app

client = TestClient(app)


# ============================================================================
# FIXTURES
# ============================================================================

PROFILE_ELIGIBLE = {
    "id": "candidate_eligible",
    "skills": ["python", "sql"],
    "languages": ["français"],
    "education": "bac+5",
    "age": 25,
    "nationality": "france",
}

PROFILE_TOO_OLD = {
    "id": "candidate_too_old",
    "skills": ["python", "sql"],
    "languages": ["français"],
    "education": "bac+5",
    "age": 30,  # > 28 → KO V.I.E
    "nationality": "france",
}

PROFILE_NON_EU = {
    "id": "candidate_non_eu",
    "skills": ["python", "sql"],
    "languages": ["français"],
    "education": "bac+5",
    "age": 25,
    "nationality": "usa",  # Hors UE → KO V.I.E
}

OFFER_VALID = {
    "id": "offer_valid",
    "is_vie": True,
    "country": "france",
    "title": "Data Analyst VIE",
    "company": "TechCorp",
    "skills": ["python", "sql"],
    "languages": ["français"],
}


# ============================================================================
# TESTS
# ============================================================================

def test_eligible_profile_sees_offer():
    """
    Un candidat éligible V.I.E voit l'offre.
    """
    response = client.post("/v1/match", json={
        "profile": PROFILE_ELIGIBLE,
        "offers": [OFFER_VALID],
    })

    assert response.status_code == 200
    data = response.json()

    # L'offre doit être présente
    assert len(data["results"]) == 1
    assert data["results"][0]["offer_id"] == "offer_valid"

    # Le diagnostic V.I.E doit être OK
    diag = data["results"][0]["diagnostic"]
    assert diag["vie_eligibility"]["status"] == "OK"


def test_too_old_profile_does_not_see_offer():
    """
    Un candidat > 28 ans ne voit PAS l'offre.
    Règle: KO V.I.E → offre masquée (barrière légale)
    """
    response = client.post("/v1/match", json={
        "profile": PROFILE_TOO_OLD,
        "offers": [OFFER_VALID],
    })

    assert response.status_code == 200
    data = response.json()

    # L'offre NE DOIT PAS être présente
    assert len(data["results"]) == 0

    # received_offers compte toujours l'offre envoyée
    assert data["received_offers"] == 1


def test_non_eu_profile_does_not_see_offer():
    """
    Un candidat hors UE ne voit PAS l'offre.
    Règle: KO V.I.E → offre masquée (barrière légale)
    """
    response = client.post("/v1/match", json={
        "profile": PROFILE_NON_EU,
        "offers": [OFFER_VALID],
    })

    assert response.status_code == 200
    data = response.json()

    # L'offre NE DOIT PAS être présente
    assert len(data["results"]) == 0


def test_mixed_offers_filters_only_ineligible():
    """
    Avec plusieurs offres, seules celles KO V.I.E sont masquées.
    Le reste reste intact (score, diagnostic conservés).
    """
    offers = [
        {
            "id": "offer_1",
            "is_vie": True,
            "country": "france",
            "title": "Offer 1",
            "company": "Company 1",
            "skills": ["python"],
            "languages": ["français"],
        },
        {
            "id": "offer_2",
            "is_vie": True,
            "country": "allemagne",
            "title": "Offer 2",
            "company": "Company 2",
            "skills": ["sql"],
            "languages": ["allemand"],  # KO langue mais pas KO V.I.E
        },
    ]

    # Profil éligible
    response = client.post("/v1/match", json={
        "profile": PROFILE_ELIGIBLE,
        "offers": offers,
    })

    assert response.status_code == 200
    data = response.json()

    # Les 2 offres doivent être présentes (aucune n'est KO V.I.E)
    assert len(data["results"]) == 2


def test_score_preserved_after_filter():
    """
    Le filtrage V.I.E ne modifie pas le score des offres restantes.
    """
    response = client.post("/v1/match", json={
        "profile": PROFILE_ELIGIBLE,
        "offers": [OFFER_VALID],
    })

    assert response.status_code == 200
    data = response.json()

    # Le score doit être présent et valide (0-100)
    assert len(data["results"]) == 1
    score = data["results"][0]["score"]
    assert isinstance(score, int)
    assert 0 <= score <= 100


def test_diagnostic_preserved_after_filter():
    """
    Le diagnostic complet est transmis pour les offres non-filtrées.
    """
    response = client.post("/v1/match", json={
        "profile": PROFILE_ELIGIBLE,
        "offers": [OFFER_VALID],
    })

    assert response.status_code == 200
    data = response.json()

    assert len(data["results"]) == 1
    diag = data["results"][0]["diagnostic"]

    # Tous les champs diagnostic doivent être présents
    assert "global_verdict" in diag
    assert "top_blocking_reasons" in diag
    assert "hard_skills" in diag
    assert "languages" in diag
    assert "education" in diag
    assert "vie_eligibility" in diag
