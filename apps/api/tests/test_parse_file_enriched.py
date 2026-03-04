"""
QA — Optional LLM enrichment for /profile/parse-file.

Ensures baseline fallback when no key and mockable LLM flow when enabled.
"""
import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

TECH_CV = "Python SQL Excel"


@pytest.fixture(scope="module")
def client():
    import os
    os.environ.setdefault("ELEVIA_DEV_TOOLS", "1")
    from api.main import app
    return TestClient(app)


def _post_txt(client, text: str, filename: str = "cv.txt", *, enrich: bool = False):
    url = "/profile/parse-file"
    if enrich:
        url += "?enrich_llm=1"
    return client.post(
        url,
        files={"file": (filename, io.BytesIO(text.encode("utf-8")), "text/plain")},
    )


def test_parse_file_enrich_no_key_fallback(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    resp = _post_txt(client, TECH_CV, enrich=True)
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "baseline"
    assert body.get("ai_available") is False
    assert body.get("ai_error") == "missing_openai_api_key"


def test_parse_file_enrich_with_mock_llm(client, monkeypatch):
    def _fake_suggest(_cv_text: str):
        return {
            "skills": ["kubernetes", "data analysis"],
            "error": None,
            "warning": None,
            "model": "mock",
        }

    monkeypatch.setattr("profile.llm_skill_suggester.suggest_skills_from_cv", _fake_suggest)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    resp = _post_txt(client, TECH_CV, enrich=True)
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "llm"
    assert body.get("ai_available") is True
    assert body.get("ai_error") is None
    assert body.get("ai_added_count", 0) >= 1


def test_parse_file_enrich_llm_failure_fallback(client, monkeypatch):
    def _fake_suggest_fail(_cv_text: str):
        return {"skills": [], "error": "boom", "warning": "fail", "model": "mock"}

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("profile.llm_skill_suggester.suggest_skills_from_cv", _fake_suggest_fail)

    resp = _post_txt(client, TECH_CV, enrich=True)
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "baseline"
    assert body.get("ai_available") is True
    assert body.get("ai_error") == "llm_failed"
