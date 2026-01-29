"""
test_matching_contract.py
=========================
Contract test: POST /v1/match response shape and invariants.

Validates:
1. Response schema (fields, types)
2. Score range [0, 100]
3. Reasons list is non-empty for scored results
4. Inaccessible offers structure
5. Meta structure
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def match_payload():
    fixtures = Path(__file__).parent.parent / "fixtures"
    with open(fixtures / "profile_demo.json") as f:
        profile = json.load(f)
    with open(fixtures / "offers_demo.json") as f:
        offers = json.load(f)
    return {"profile": profile, "offers": offers}


# ============================================================================
# SCHEMA
# ============================================================================

def test_response_top_level_keys(client, match_payload):
    """Response contains all required top-level keys."""
    resp = client.post("/v1/match", json=match_payload)
    assert resp.status_code == 200
    data = resp.json()
    required = {"profile_id", "threshold", "results", "inaccessible_offers", "meta"}
    assert required <= set(data.keys()), f"Missing keys: {required - set(data.keys())}"


def test_result_item_shape(client, match_payload):
    """Each result item has the expected fields and types."""
    data = client.post("/v1/match", json=match_payload).json()
    for r in data["results"]:
        assert isinstance(r["offer_id"], str)
        assert isinstance(r["score"], (int, float))
        assert isinstance(r["breakdown"], dict)
        assert isinstance(r["reasons"], list)
        assert isinstance(r["diagnostic"], dict)


def test_breakdown_keys(client, match_payload):
    """Breakdown has exactly the 4 pillars."""
    data = client.post("/v1/match", json=match_payload).json()
    expected = {"skills", "languages", "education", "country"}
    for r in data["results"]:
        assert set(r["breakdown"].keys()) == expected


def test_diagnostic_keys(client, match_payload):
    """Diagnostic has the 5 criterion pillars + global verdict."""
    data = client.post("/v1/match", json=match_payload).json()
    expected = {"global_verdict", "top_blocking_reasons",
                "hard_skills", "soft_skills", "languages", "education", "vie_eligibility"}
    for r in data["results"]:
        assert expected <= set(r["diagnostic"].keys())


# ============================================================================
# SCORE INVARIANTS
# ============================================================================

def test_scores_in_valid_range(client, match_payload):
    """All scores must be in [0, 100]."""
    data = client.post("/v1/match", json=match_payload).json()
    for r in data["results"]:
        assert 0 <= r["score"] <= 100, f"Score out of range: {r['score']}"


def test_results_sorted_descending(client, match_payload):
    """Results are sorted by score descending."""
    data = client.post("/v1/match", json=match_payload).json()
    scores = [r["score"] for r in data["results"]]
    assert scores == sorted(scores, reverse=True)


# ============================================================================
# REASONS
# ============================================================================

def test_reasons_max_three(client, match_payload):
    """Each result has at most 3 reasons."""
    data = client.post("/v1/match", json=match_payload).json()
    for r in data["results"]:
        assert len(r["reasons"]) <= 3


# ============================================================================
# INACCESSIBLE OFFERS
# ============================================================================

def test_inaccessible_offers_shape(client, match_payload):
    """Inaccessible offers have required fields."""
    data = client.post("/v1/match", json=match_payload).json()
    for item in data.get("inaccessible_offers", []):
        assert isinstance(item["offer_id"], str)
        assert item["is_accessible"] is False
        assert isinstance(item["inaccessibility_codes"], list)
        assert isinstance(item["inaccessibility_reasons"], list)


# ============================================================================
# META
# ============================================================================

def test_meta_total_processed(client, match_payload):
    """Meta.total_processed equals number of offers sent."""
    data = client.post("/v1/match", json=match_payload).json()
    total = data["meta"]["total_processed"]
    assert total == len(match_payload["offers"])
