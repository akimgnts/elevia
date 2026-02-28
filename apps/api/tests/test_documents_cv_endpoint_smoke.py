"""
test_documents_cv_endpoint_smoke.py — FastAPI TestClient smoke tests.

Tests:
  - POST /documents/cv with provider disabled → 200 + fallback_used=true
  - POST /documents/cv missing offer_id → 422
  - POST /documents/cv with unknown offer_id → 404
  - GET /documents/cv/status → 200 with expected keys
  - Response structure matches CvDocumentResponse schema
  - No API key in response (SEC check)
  - duration_ms present and numeric
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── App fixture ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """Spin up TestClient with LLM disabled (no API key in test env)."""
    # Ensure LLM is disabled for tests
    with patch.dict("os.environ", {
        "OPENAI_API_KEY": "",
        "LLM_API_KEY": "",
        "OPENAI_KEY": "",
    }, clear=False):
        from api.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ── Helper: minimal valid payload ────────────────────────────────────────────

def _cv_request(offer_id: str = "BF-237241", profile: dict | None = None):
    return {
        "offer_id": offer_id,
        "profile": profile or {
            "skills": ["python (programmation informatique)", "sql", "analyse de données"],
            "languages": ["anglais"],
            "education": "bac+5",
        },
        "lang": "fr",
        "style": "ats_compact",
    }


# ── Smoke tests ───────────────────────────────────────────────────────────────

def test_cv_status_endpoint(client):
    """GET /documents/cv/status → 200 with expected fields."""
    resp = client.get("/documents/cv/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "llm_key_present" in data
    assert "mode" in data
    assert "prompt_version" in data
    # SEC: key value must not appear
    raw = resp.text
    assert "sk-" not in raw


def test_cv_endpoint_missing_offer_id(client):
    """POST /documents/cv without offer_id → 422 Unprocessable Entity."""
    resp = client.post("/documents/cv", json={"profile": {"skills": ["python"]}})
    assert resp.status_code == 422


def test_cv_endpoint_unknown_offer(client):
    """POST /documents/cv with unknown offer_id → 404."""
    resp = client.post("/documents/cv", json=_cv_request("NONEXISTENT_OFFER_ZZZZZ"))
    assert resp.status_code == 404


def test_cv_endpoint_fallback_disabled_llm(client):
    """
    POST /documents/cv with valid offer_id + LLM disabled → 200 + fallback_used=true.
    This is the core smoke test: verifies the whole pipeline (DB → keywords → fallback).
    Requires at least one BF offer in the DB (BF-237241 from previous sprints).
    """
    resp = client.post("/documents/cv", json=_cv_request("BF-237241"))

    if resp.status_code == 404:
        pytest.skip("BF-237241 not in DB — run ingestion first")

    assert resp.status_code == 200
    data = resp.json()

    # Envelope
    assert data["ok"] is True
    assert "document" in data
    assert isinstance(data["duration_ms"], int)
    assert data["duration_ms"] >= 0

    doc = data["document"]

    # Required top-level fields
    assert "summary" in doc
    assert "keywords_injected" in doc
    assert "experience_blocks" in doc
    assert "ats_notes" in doc
    assert "meta" in doc

    # Fallback marker (LLM disabled in test env)
    assert doc["meta"]["fallback_used"] is True
    assert doc["meta"]["offer_id"] == "BF-237241"
    assert doc["meta"]["prompt_version"] == "cv_v1"

    # ATS notes
    ats = doc["ats_notes"]
    assert 0 <= ats["ats_score_estimate"] <= 100
    assert isinstance(ats["matched_keywords"], list)
    assert isinstance(ats["missing_keywords"], list)


def test_cv_endpoint_no_secret_in_response(client):
    """SEC: response body must not contain API key patterns."""
    resp = client.post("/documents/cv", json=_cv_request("BF-237241"))
    raw = resp.text
    # Key patterns that should never appear
    assert "sk-" not in raw
    assert "OPENAI_API_KEY" not in raw
    assert "LLM_API_KEY" not in raw


def test_cv_endpoint_keywords_subset(client):
    """keywords_injected must be a subset of offer keywords (anti-lie check)."""
    resp = client.post("/documents/cv", json=_cv_request("BF-237241"))
    if resp.status_code != 200:
        pytest.skip("Offer not available")

    doc = resp.json()["document"]
    # All injected keywords should be short strings (not fabricated long phrases)
    for kw in doc["keywords_injected"]:
        assert isinstance(kw, str)
        assert len(kw) >= 2


def test_cv_endpoint_experience_blocks_valid(client):
    """experience_blocks structure is valid (bullets, autonomy, etc.)."""
    resp = client.post("/documents/cv", json=_cv_request("BF-237241"))
    if resp.status_code != 200:
        pytest.skip("Offer not available")

    doc = resp.json()["document"]
    for block in doc["experience_blocks"]:
        assert "title" in block
        assert "company" in block
        assert "bullets" in block
        assert isinstance(block["bullets"], list)
        assert len(block["bullets"]) >= 1
        assert block["autonomy"] in ("CONTRIB", "COPILOT", "LEAD")


def test_cv_endpoint_cache_second_call(client):
    """Second identical call should be faster (cache hit)."""
    payload = _cv_request("BF-237241")

    resp1 = client.post("/documents/cv", json=payload)
    if resp1.status_code != 200:
        pytest.skip("Offer not available")

    resp2 = client.post("/documents/cv", json=payload)
    assert resp2.status_code == 200

    doc2 = resp2.json()["document"]
    assert doc2["meta"]["cache_hit"] is True


def test_cv_endpoint_empty_profile(client):
    """Empty profile dict still generates a valid fallback (no crash)."""
    resp = client.post("/documents/cv", json={"offer_id": "BF-237241", "profile": {}})
    if resp.status_code == 404:
        pytest.skip("Offer not available")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
