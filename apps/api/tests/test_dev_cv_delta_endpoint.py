import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_dev_cv_delta_requires_env(client, monkeypatch):
    monkeypatch.delenv("ELEVIA_DEV_TOOLS", raising=False)
    resp = client.post(
        "/dev/cv-delta",
        files={"file": ("sample.txt", b"python sql docker", "text/plain")},
    )
    assert resp.status_code == 403


def test_dev_cv_delta_with_llm_missing_key(client, monkeypatch):
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    resp = client.post(
        "/dev/cv-delta",
        data={"with_llm": "true"},
        files={"file": ("sample.txt", b"python sql docker", "text/plain")},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["meta"]["run_mode"] == "A"
    assert payload["meta"]["warning"]
    assert payload["canonical_count"] >= 1


def test_dev_cv_delta_schema_contract(client, monkeypatch):
    """Response must always include all required keys regardless of content."""
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    resp = client.post(
        "/dev/cv-delta",
        files={"file": ("cv.txt", b"Python Django React machine learning SQL", "text/plain")},
    )
    assert resp.status_code == 200
    payload = resp.json()
    required_keys = {
        "meta", "canonical_count", "added_skills",
        "removed_skills", "unchanged_skills_count", "added_esco", "removed_esco",
    }
    assert required_keys.issubset(payload.keys()), f"Missing: {required_keys - payload.keys()}"
    meta = payload["meta"]
    assert meta["run_mode"] in {"A", "A+B"}
    assert isinstance(payload["canonical_count"], int)
    assert isinstance(payload["added_skills"], list)
    assert isinstance(payload["removed_skills"], list)


def test_dev_cv_delta_get_not_allowed(client):
    """GET /dev/cv-delta must return 405, not 404."""
    resp = client.get("/dev/cv-delta")
    assert resp.status_code == 405
