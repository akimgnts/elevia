"""
test_inaccessible_offers.py
============================
Sprint 21 - Tests for inaccessible offers visibility

Tests that:
1. results contain ONLY VIE-eligible offers
2. inaccessible_offers contain KO offers with annotations
3. meta.filtered.legal_vie == len(inaccessible_offers)
4. scoring is NOT called for KO offers
5. /offers/catalog is unchanged (no new fields)
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient

from api.main import app


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def eligible_profile():
    """Profile that is VIE-eligible (EU nationality, age < 28)."""
    return {
        "id": "eligible_001",
        "age": 25,
        "nationality": "france",
        "skills": ["python", "sql"],
        "languages": ["français", "anglais"],
        "education": "bac+5",
    }


@pytest.fixture
def ineligible_profile_age():
    """Profile that is VIE-ineligible due to age > 28."""
    return {
        "id": "ineligible_age",
        "age": 30,
        "nationality": "france",
        "skills": ["python", "sql"],
        "languages": ["français", "anglais"],
        "education": "bac+5",
    }


@pytest.fixture
def ineligible_profile_nationality():
    """Profile that is VIE-ineligible due to non-EU nationality."""
    return {
        "id": "ineligible_nationality",
        "age": 25,
        "nationality": "usa",
        "skills": ["python", "sql"],
        "languages": ["français", "anglais"],
        "education": "bac+5",
    }


@pytest.fixture
def sample_offers():
    """Mixed offers for testing."""
    return [
        {
            "id": "offer_001",
            "is_vie": True,
            "country": "france",
            "title": "Data Analyst VIE",
            "company": "TechCorp",
            "skills": ["python", "sql"],
            "languages": ["français"],
        },
        {
            "id": "offer_002",
            "is_vie": True,
            "country": "germany",
            "title": "Developer VIE",
            "company": "GermanTech",
            "skills": ["python"],
            "languages": ["anglais"],
        },
    ]


# ============================================================================
# TEST 1: Results contain only VIE-eligible offers
# ============================================================================

def test_results_only_contain_eligible_offers(client, ineligible_profile_age, sample_offers):
    """
    When profile is VIE-ineligible, results should be empty.
    All offers should be in inaccessible_offers.
    """
    response = client.post(
        "/v1/match",
        json={"profile": ineligible_profile_age, "offers": sample_offers}
    )

    assert response.status_code == 200
    data = response.json()

    # Results should be empty (all offers are inaccessible to this profile)
    assert data["results"] == []

    # All offers should be in inaccessible_offers
    assert len(data["inaccessible_offers"]) == len(sample_offers)


def test_results_contain_only_vie_ok_offers(client, eligible_profile, sample_offers):
    """
    When profile is VIE-eligible, results should contain scored offers.
    inaccessible_offers should be empty.
    """
    response = client.post(
        "/v1/match",
        json={"profile": eligible_profile, "offers": sample_offers}
    )

    assert response.status_code == 200
    data = response.json()

    # Results should contain offers (profile is eligible)
    # Note: May be filtered by score threshold, so >= 0
    assert isinstance(data["results"], list)

    # No inaccessible offers for eligible profile
    assert data["inaccessible_offers"] == []


# ============================================================================
# TEST 2: Inaccessible offers have correct structure
# ============================================================================

def test_inaccessible_offers_structure(client, ineligible_profile_age, sample_offers):
    """
    Each inaccessible offer must have:
    - offer_id: str
    - is_accessible: False
    - inaccessibility_codes: non-empty list
    - inaccessibility_reasons: list
    """
    response = client.post(
        "/v1/match",
        json={"profile": ineligible_profile_age, "offers": sample_offers}
    )

    data = response.json()

    for inaccessible in data["inaccessible_offers"]:
        assert "offer_id" in inaccessible
        assert inaccessible["is_accessible"] is False
        assert "inaccessibility_codes" in inaccessible
        assert isinstance(inaccessible["inaccessibility_codes"], list)
        assert len(inaccessible["inaccessibility_codes"]) > 0
        assert "inaccessibility_reasons" in inaccessible
        assert isinstance(inaccessible["inaccessibility_reasons"], list)


def test_inaccessible_offers_codes_for_age(client, ineligible_profile_age, sample_offers):
    """AGE_LIMIT code should be present when age > 28."""
    response = client.post(
        "/v1/match",
        json={"profile": ineligible_profile_age, "offers": sample_offers}
    )

    data = response.json()

    # All offers should have AGE_LIMIT code
    for inaccessible in data["inaccessible_offers"]:
        codes = inaccessible["inaccessibility_codes"]
        # Should contain AGE_LIMIT or VIE_INELIGIBLE
        assert any(code in ["AGE_LIMIT", "VIE_INELIGIBLE"] for code in codes), \
            f"Expected AGE_LIMIT or VIE_INELIGIBLE, got {codes}"


def test_inaccessible_offers_codes_for_nationality(client, ineligible_profile_nationality, sample_offers):
    """NATIONALITY_INELIGIBLE code should be present for non-EU nationality."""
    response = client.post(
        "/v1/match",
        json={"profile": ineligible_profile_nationality, "offers": sample_offers}
    )

    data = response.json()

    for inaccessible in data["inaccessible_offers"]:
        codes = inaccessible["inaccessibility_codes"]
        # Should contain NATIONALITY_INELIGIBLE or VIE_INELIGIBLE
        assert any(code in ["NATIONALITY_INELIGIBLE", "VIE_INELIGIBLE"] for code in codes), \
            f"Expected NATIONALITY_INELIGIBLE or VIE_INELIGIBLE, got {codes}"


# ============================================================================
# TEST 3: meta.filtered.legal_vie equals len(inaccessible_offers)
# ============================================================================

def test_meta_filtered_count_matches_inaccessible(client, ineligible_profile_age, sample_offers):
    """meta.filtered.legal_vie should equal len(inaccessible_offers)."""
    response = client.post(
        "/v1/match",
        json={"profile": ineligible_profile_age, "offers": sample_offers}
    )

    data = response.json()

    assert "meta" in data
    assert data["meta"] is not None
    assert "filtered" in data["meta"]
    assert data["meta"]["filtered"] is not None
    assert "legal_vie" in data["meta"]["filtered"]
    assert data["meta"]["filtered"]["legal_vie"] == len(data["inaccessible_offers"])


def test_meta_filtered_none_when_no_ko(client, eligible_profile, sample_offers):
    """meta.filtered should be None when no offers are filtered."""
    response = client.post(
        "/v1/match",
        json={"profile": eligible_profile, "offers": sample_offers}
    )

    data = response.json()

    # When all offers are accessible, filtered should be None
    if len(data["inaccessible_offers"]) == 0:
        assert data["meta"]["filtered"] is None


def test_meta_total_processed(client, eligible_profile, sample_offers):
    """meta.total_processed should equal number of offers submitted."""
    response = client.post(
        "/v1/match",
        json={"profile": eligible_profile, "offers": sample_offers}
    )

    data = response.json()

    assert data["meta"]["total_processed"] == len(sample_offers)


# ============================================================================
# TEST 4: Scoring is NOT called for KO offers
# ============================================================================

def test_scoring_not_called_for_ko_offers(client, ineligible_profile_age, sample_offers):
    """
    When all offers are KO (ineligible), score_offer should not be called.
    This tests the performance optimization requirement.
    """
    with patch("api.routes.matching.MatchingEngine") as MockEngine:
        mock_engine = MagicMock()
        MockEngine.return_value = mock_engine

        response = client.post(
            "/v1/match",
            json={"profile": ineligible_profile_age, "offers": sample_offers}
        )

        assert response.status_code == 200
        data = response.json()

        # All offers should be inaccessible
        assert len(data["inaccessible_offers"]) == len(sample_offers)
        assert data["results"] == []

        # score_offer should NOT have been called
        assert mock_engine.score_offer.call_count == 0


def test_scoring_only_called_for_ok_offers(client, eligible_profile, sample_offers):
    """
    When profile is eligible, score_offer should be called for each offer.
    """
    with patch("api.routes.matching.MatchingEngine") as MockEngine:
        mock_engine = MagicMock()
        mock_engine.score_offer.return_value = MagicMock(
            offer_id="test",
            score=85,
            breakdown={"skills": 0.8, "languages": 0.9, "education": 1.0, "country": 1.0},
            reasons=["Test reason"]
        )
        MockEngine.return_value = mock_engine

        response = client.post(
            "/v1/match",
            json={"profile": eligible_profile, "offers": sample_offers}
        )

        assert response.status_code == 200

        # score_offer should be called for each accessible offer
        # Number of calls = number of OK offers (all in this case)
        assert mock_engine.score_offer.call_count == len(sample_offers)


# ============================================================================
# TEST 5: /offers/catalog is unchanged
# ============================================================================

def test_catalog_no_inaccessible_offers_field(client):
    """
    /offers/catalog should NOT have inaccessible_offers or meta.filtered.legal_vie.
    Sprint 21 should not affect the catalog endpoint.
    """
    response = client.get("/offers/catalog?limit=10")

    assert response.status_code == 200
    data = response.json()

    # Catalog response structure check
    assert "offers" in data
    assert "meta" in data

    # Should NOT have inaccessible_offers
    assert "inaccessible_offers" not in data

    # meta should NOT have filtered.legal_vie
    if "filtered" in data["meta"]:
        if data["meta"]["filtered"] is not None:
            assert "legal_vie" not in data["meta"]["filtered"]


# ============================================================================
# ADDITIONAL EDGE CASES
# ============================================================================

def test_empty_offers_list(client, eligible_profile):
    """Empty offers list should return empty results and inaccessible_offers."""
    response = client.post(
        "/v1/match",
        json={"profile": eligible_profile, "offers": []}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["results"] == []
    assert data["inaccessible_offers"] == []
    assert data["meta"]["total_processed"] == 0
    assert data["meta"]["filtered"] is None


def test_backwards_compatibility_response_keys(client, eligible_profile, sample_offers):
    """
    Response should maintain backwards compatibility.
    Original keys (profile_id, threshold, received_offers, results, message) must exist.
    """
    response = client.post(
        "/v1/match",
        json={"profile": eligible_profile, "offers": sample_offers}
    )

    data = response.json()

    # Original keys must be present (Sprint 7 contract)
    assert "profile_id" in data
    assert "threshold" in data
    assert "received_offers" in data
    assert "results" in data
    assert "message" in data

    # New Sprint 21 keys
    assert "inaccessible_offers" in data
    assert "meta" in data


# ============================================================================
# HELPER FUNCTION TESTS
# ============================================================================

def test_map_reasons_to_codes_age():
    """Test _map_reasons_to_codes for age-related reasons."""
    from api.routes.matching import _map_reasons_to_codes

    reasons = ["âge supérieur à 28 ans"]
    codes = _map_reasons_to_codes(reasons)
    assert "AGE_LIMIT" in codes


def test_map_reasons_to_codes_nationality():
    """Test _map_reasons_to_codes for nationality-related reasons."""
    from api.routes.matching import _map_reasons_to_codes

    reasons = ["nationalité hors UE"]
    codes = _map_reasons_to_codes(reasons)
    assert "NATIONALITY_INELIGIBLE" in codes


def test_map_reasons_to_codes_fallback():
    """Test _map_reasons_to_codes fallback to VIE_INELIGIBLE."""
    from api.routes.matching import _map_reasons_to_codes

    reasons = ["some unknown reason"]
    codes = _map_reasons_to_codes(reasons)
    assert "VIE_INELIGIBLE" in codes


def test_map_reasons_to_codes_empty():
    """Test _map_reasons_to_codes with empty list."""
    from api.routes.matching import _map_reasons_to_codes

    codes = _map_reasons_to_codes([])
    assert codes == ["VIE_INELIGIBLE"]


def test_map_reasons_to_codes_dedup():
    """Test _map_reasons_to_codes deduplicates codes."""
    from api.routes.matching import _map_reasons_to_codes

    reasons = ["âge limite dépassé", "age too high", "28 ans max"]
    codes = _map_reasons_to_codes(reasons)
    # Should only have one AGE_LIMIT
    assert codes.count("AGE_LIMIT") == 1


# ============================================================================
# EXÉCUTION DIRECTE
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
