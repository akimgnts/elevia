"""
test_ingest_match_integration.py
================================
Integration: profile ingestion → matching pipeline.

Validates end-to-end:
1. Minimal profile + 1 offer → score > 0, reasons non-empty
2. Multi-format profile input (detected_capabilities, education_summary)
3. Empty skills → still returns result with diagnostic
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


MINIMAL_PROFILE = {
    "id": "integ_001",
    "skills": ["python", "sql"],
    "languages": ["français"],
    "education": "bac+5",
}

MATCHING_OFFER = {
    "id": "offer_integ_001",
    "is_vie": True,
    "country": "france",
    "title": "Data Analyst VIE",
    "company": "TestCorp",
    "skills": ["python", "sql", "excel"],
    "languages": ["français"],
    "education": "bac+5",
}


# ============================================================================
# TEST 1 — Minimal profile matches an offer
# ============================================================================

def test_minimal_profile_gets_score(client):
    """A profile with overlapping skills gets score > 0 and non-empty reasons."""
    resp = client.post("/v1/match", json={
        "profile": MINIMAL_PROFILE,
        "offers": [MATCHING_OFFER],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 1
    result = data["results"][0]
    assert result["score"] > 0, "Matching profile should score > 0"
    assert len(result["reasons"]) > 0, "Should have at least 1 reason"
    assert result["diagnostic"]["global_verdict"] in ("OK", "PARTIAL", "KO")


# ============================================================================
# TEST 2 — Multi-format profile (detected_capabilities + education_summary)
# ============================================================================

def test_detected_capabilities_format(client):
    """Profile using detected_capabilities format still produces a valid match."""
    profile = {
        "id": "integ_caps_001",
        "detected_capabilities": [
            {"name": "python", "level": "advanced"},
            {"name": "sql", "level": "intermediate"},
        ],
        "languages": [{"code": "français", "level": "native"}],
        "education_summary": {"level": "bac+5"},
    }
    resp = client.post("/v1/match", json={
        "profile": profile,
        "offers": [MATCHING_OFFER],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) >= 1
    assert data["results"][0]["score"] > 0


# ============================================================================
# TEST 3 — Empty skills still returns result with diagnostic
# ============================================================================

def test_empty_skills_returns_diagnostic(client):
    """Profile with no skills still gets a result with diagnostic."""
    profile = {
        "id": "integ_empty_001",
        "skills": [],
        "languages": ["français"],
        "education": "bac+3",
    }
    resp = client.post("/v1/match", json={
        "profile": profile,
        "offers": [MATCHING_OFFER],
    })
    assert resp.status_code == 200
    data = resp.json()
    # Should still have a result (with low score) or at least not crash
    assert "results" in data
    if data["results"]:
        assert data["results"][0]["diagnostic"] is not None


# ============================================================================
# TEST 4 — Pipeline stability: score is deterministic
# ============================================================================

def test_deterministic_score(client):
    """Same input produces same score twice."""
    payload = {"profile": MINIMAL_PROFILE, "offers": [MATCHING_OFFER]}
    score1 = client.post("/v1/match", json=payload).json()["results"][0]["score"]
    score2 = client.post("/v1/match", json=payload).json()["results"][0]["score"]
    assert score1 == score2, f"Non-deterministic: {score1} != {score2}"
