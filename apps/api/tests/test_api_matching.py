"""
test_api_matching.py
====================
Sprint 7 - Tests d'intégration API Matching

Tests via TestClient FastAPI.
"""

import sys
import json
from pathlib import Path

# Ajout du chemin src/ au path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient

from api.main import app


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def client():
    """Client de test FastAPI."""
    return TestClient(app)


@pytest.fixture
def profile_demo():
    """Charge le profil demo."""
    fixtures_path = Path(__file__).parent.parent / "fixtures" / "profile_demo.json"
    with open(fixtures_path) as f:
        return json.load(f)


@pytest.fixture
def offers_demo():
    """Charge les offres demo."""
    fixtures_path = Path(__file__).parent.parent / "fixtures" / "offers_demo.json"
    with open(fixtures_path) as f:
        return json.load(f)


# ============================================================================
# TESTS HEALTH
# ============================================================================

def test_health(client):
    """Test healthcheck endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert data["service"] == "Elevia API"


# ============================================================================
# TESTS MATCHING ENDPOINT
# ============================================================================

def test_match_status_200(client, profile_demo, offers_demo):
    """POST /v1/match retourne 200."""
    response = client.post(
        "/v1/match",
        json={"profile": profile_demo, "offers": offers_demo}
    )
    assert response.status_code == 200


def test_match_response_keys(client, profile_demo, offers_demo):
    """Réponse contient les clés attendues."""
    response = client.post(
        "/v1/match",
        json={"profile": profile_demo, "offers": offers_demo}
    )
    data = response.json()

    assert "profile_id" in data
    assert "threshold" in data
    assert "results" in data
    assert "message" in data


def test_match_threshold_default(client, profile_demo, offers_demo):
    """Seuil par défaut est 80."""
    response = client.post(
        "/v1/match",
        json={"profile": profile_demo, "offers": offers_demo}
    )
    data = response.json()
    assert data["threshold"] == 80


def test_match_results_score_above_threshold(client, profile_demo, offers_demo):
    """Tous les résultats ont score >= threshold."""
    response = client.post(
        "/v1/match",
        json={"profile": profile_demo, "offers": offers_demo}
    )
    data = response.json()

    for result in data["results"]:
        assert result["score"] >= data["threshold"], \
            f"Score {result['score']} < threshold {data['threshold']}"


def test_match_results_max_three_reasons(client, profile_demo, offers_demo):
    """Chaque résultat a max 3 raisons."""
    response = client.post(
        "/v1/match",
        json={"profile": profile_demo, "offers": offers_demo}
    )
    data = response.json()

    for result in data["results"]:
        assert len(result["reasons"]) <= 3, \
            f"Offre {result['offer_id']} a {len(result['reasons'])} raisons"


def test_match_results_breakdown_keys(client, profile_demo, offers_demo):
    """Breakdown contient les clés attendues."""
    response = client.post(
        "/v1/match",
        json={"profile": profile_demo, "offers": offers_demo}
    )
    data = response.json()

    expected_keys = {"skills", "languages", "education", "country"}

    for result in data["results"]:
        assert set(result["breakdown"].keys()) == expected_keys, \
            f"Breakdown keys incorrectes: {result['breakdown'].keys()}"


def test_match_no_forbidden_words(client, profile_demo, offers_demo):
    """Aucun mot interdit dans les raisons."""
    FORBIDDEN_WORDS = ["ia", "probabilité", "potentiel", "recommandation", "prédiction"]

    response = client.post(
        "/v1/match",
        json={"profile": profile_demo, "offers": offers_demo}
    )
    data = response.json()

    for result in data["results"]:
        for reason in result["reasons"]:
            reason_lower = reason.lower()
            for forbidden in FORBIDDEN_WORDS:
                assert forbidden not in reason_lower, \
                    f"Mot interdit '{forbidden}' trouvé dans: {reason}"


def test_match_vie_filter(client, profile_demo, offers_demo):
    """Seules les offres VIE sont retournées."""
    response = client.post(
        "/v1/match",
        json={"profile": profile_demo, "offers": offers_demo}
    )
    data = response.json()

    # Les offres non-VIE (is_vie=false/null) ne doivent pas apparaître
    non_vie_ids = {"offer_non_vie_001", "offer_vie_null"}
    result_ids = {r["offer_id"] for r in data["results"]}

    for non_vie_id in non_vie_ids:
        assert non_vie_id not in result_ids, \
            f"Offre non-VIE {non_vie_id} ne devrait pas apparaître"


def test_match_empty_offers(client, profile_demo):
    """Liste d'offres vide retourne message."""
    response = client.post(
        "/v1/match",
        json={"profile": profile_demo, "offers": []}
    )
    data = response.json()

    assert response.status_code == 200
    assert data["results"] == []


def test_match_no_matching_skills(client):
    """Profil sans skills communes retourne message."""
    profile = {
        "id": "no_match",
        "skills": ["cobol", "fortran"],
        "languages": ["latin"],
        "education": "bac"
    }
    offers = [
        {
            "id": "offer_modern",
            "is_vie": True,
            "country": "france",
            "title": "Dev Python VIE",
            "company": "ModernCorp",
            "skills": ["python", "react", "docker"],
            "languages": ["français"]
        }
    ]

    response = client.post(
        "/v1/match",
        json={"profile": profile, "offers": offers}
    )
    data = response.json()

    assert response.status_code == 200
    assert data["results"] == []
    assert data["message"] is not None
    assert "80%" in data["message"]


# ============================================================================
# EXÉCUTION DIRECTE
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
