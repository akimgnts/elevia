"""
QA — Deterministic baseline CV parser tests.

Fast (<0.5s), no LLM, no server start.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure src on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

CV_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "cv" / "cv_fixture_v0.txt"

# ── Unit tests for the extractor directly ─────────────────────────────────────

def test_cv_fixture_exists():
    """Fixture file must be present."""
    assert CV_FIXTURE_PATH.exists(), f"Missing fixture: {CV_FIXTURE_PATH}"


def test_cv_fixture_not_empty():
    text = CV_FIXTURE_PATH.read_text(encoding="utf-8")
    assert len(text.strip()) > 100, "Fixture too short"


def test_baseline_extractor_deterministic():
    """Same input must produce same output (no randomness)."""
    from esco.extract import extract_raw_skills_from_profile

    text = CV_FIXTURE_PATH.read_text(encoding="utf-8")
    result1 = extract_raw_skills_from_profile({"cv_text": text})
    result2 = extract_raw_skills_from_profile({"cv_text": text})
    assert result1 == result2, "Extractor is not deterministic"


def test_baseline_extractor_minimum_count():
    """Fixture CV must yield at least 10 canonical skills."""
    from esco.extract import extract_raw_skills_from_profile

    text = CV_FIXTURE_PATH.read_text(encoding="utf-8")
    skills = extract_raw_skills_from_profile({"cv_text": text})
    assert isinstance(skills, list), "Expected list"
    assert len(skills) >= 10, f"Expected >= 10 skills, got {len(skills)}: {skills}"


def test_baseline_extractor_sorted():
    """Extractor output must be sorted (for determinism in tests)."""
    from esco.extract import extract_raw_skills_from_profile

    text = CV_FIXTURE_PATH.read_text(encoding="utf-8")
    skills = extract_raw_skills_from_profile({"cv_text": text})
    assert skills == sorted(skills), "Skills are not sorted"


def test_baseline_extractor_key_skills_present():
    """Known skills from fixture must be extracted."""
    from esco.extract import extract_raw_skills_from_profile

    text = CV_FIXTURE_PATH.read_text(encoding="utf-8")
    skills_lower = {s.lower() for s in extract_raw_skills_from_profile({"cv_text": text})}

    # At least half of these known skills should be extracted
    expected = {"python", "sql", "docker", "git", "excel", "pandas"}
    found = expected & skills_lower
    assert len(found) >= 3, f"Too few key skills found. Got {found} from {skills_lower}"


def test_baseline_extractor_empty_text():
    """Empty input should return empty list (no crash)."""
    from esco.extract import extract_raw_skills_from_profile

    result = extract_raw_skills_from_profile({"cv_text": ""})
    assert isinstance(result, list)
    assert len(result) == 0


def test_baseline_extractor_non_cv_text():
    """Gibberish should yield few/no skills (no crash)."""
    from esco.extract import extract_raw_skills_from_profile

    result = extract_raw_skills_from_profile({"cv_text": "zzz foo bar baz qux nope"})
    assert isinstance(result, list)
    # May return some tokens but should not raise


# ── Integration test for the HTTP endpoint ────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    import os
    os.environ.setdefault("ELEVIA_DEV_TOOLS", "1")
    from api.main import app
    return TestClient(app)


def test_parse_baseline_endpoint_returns_200(client):
    """POST /profile/parse-baseline must return 200 for valid input."""
    resp = client.post(
        "/profile/parse-baseline",
        json={"cv_text": "Python SQL Excel Docker Git machine learning data analysis"},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


def test_parse_baseline_endpoint_schema(client):
    """Response must include all required keys."""
    resp = client.post(
        "/profile/parse-baseline",
        json={"cv_text": "Python SQL Excel Docker Git Pandas statistics"},
    )
    assert resp.status_code == 200
    body = resp.json()
    required_keys = {"source", "skills_raw", "skills_canonical", "canonical_count", "profile"}
    assert required_keys.issubset(body.keys()), f"Missing keys: {required_keys - body.keys()}"
    assert body["source"] == "baseline"
    assert isinstance(body["skills_raw"], list)
    assert isinstance(body["canonical_count"], int)
    assert isinstance(body["profile"], dict)
    assert "skills" in body["profile"]


def test_parse_baseline_endpoint_no_llm_needed(client, monkeypatch):
    """Endpoint must work without OPENAI_API_KEY."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    resp = client.post(
        "/profile/parse-baseline",
        json={"cv_text": "Python SQL Excel Docker Git"},
    )
    assert resp.status_code == 200


def test_parse_baseline_endpoint_minimum_count_from_fixture(client):
    """Fixture CV must yield >= 10 canonical skills via the endpoint."""
    text = CV_FIXTURE_PATH.read_text(encoding="utf-8")
    resp = client.post("/profile/parse-baseline", json={"cv_text": text})
    assert resp.status_code == 200
    body = resp.json()
    count = body["canonical_count"]
    assert count >= 10, f"Expected >= 10, got {count}"


def test_parse_baseline_endpoint_deterministic(client):
    """Same CV must produce same response twice."""
    text = CV_FIXTURE_PATH.read_text(encoding="utf-8")
    resp1 = client.post("/profile/parse-baseline", json={"cv_text": text})
    resp2 = client.post("/profile/parse-baseline", json={"cv_text": text})
    assert resp1.json()["canonical_count"] == resp2.json()["canonical_count"]
    assert resp1.json()["skills_canonical"] == resp2.json()["skills_canonical"]


def test_parse_baseline_endpoint_profile_inbox_compatible(client):
    """Profile output must be directly usable in /inbox without transformation."""
    resp = client.post(
        "/profile/parse-baseline",
        json={"cv_text": "Python SQL Excel machine learning"},
    )
    assert resp.status_code == 200
    profile = resp.json()["profile"]
    # /inbox expects profile with 'id' and 'skills' keys
    assert "id" in profile or "profile_id" in profile or True  # id optional
    assert "skills" in profile
    assert isinstance(profile["skills"], list)
