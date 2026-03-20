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


def test_parse_file_exposes_explicit_matching_input_trace(client):
    resp = _post_txt(client, TECH_CV)
    assert resp.status_code == 200
    body = resp.json()
    trace = body.get("matching_input_trace") or {}
    assert "freeze_boundary" in trace
    assert "stage_order" in trace
    assert "stages" in trace
    assert "effective_skills" in trace
    assert isinstance(trace["stages"], list)
    assert trace["stage_order"] == [
        "baseline_extraction",
        "canonical_mapping",
        "domain_enrichment",
        "promotion_enrichment",
        "matching_preparation",
    ]


def test_parse_file_exposes_skill_priority_outputs(client):
    resp = _post_txt(client, "Python SQL Power BI Audit Internal Control")
    assert resp.status_code == 200
    body = resp.json()

    assert "preserved_explicit_skills" in body
    assert "profile_summary_skills" in body
    assert "dropped_by_priority" in body
    assert "priority_trace" in body
    assert "priority_stats" in body
    assert "structured_signal_units" in body
    assert "top_signal_units" in body
    assert "structured_signal_stats" in body
    assert "profile_intelligence" in body
    assert "profile_intelligence_ai_assist" in body
    assert "mapping_inputs_count" in body
    assert "mapping_inputs_count" in body["structured_signal_stats"]
    assert "structured_units_promoted_count" in body["structured_signal_stats"]
    assert "structured_units_rejected_count" in body["structured_signal_stats"]
    assert body["profile_intelligence"]["dominant_role_block"]
    assert any(item.get("label") == "Python" for item in body["preserved_explicit_skills"])
    assert any(item.get("label") == "Audit" for item in body["profile_summary_skills"])
    analyze_dev = body.get("analyze_dev") or {}
    assert "skill_priority" in analyze_dev
    assert "structured_extraction" in analyze_dev
    assert "profile_intelligence" in analyze_dev
    assert "profile_intelligence_ai_assist" in analyze_dev
    assert "semantic_rag_assist" not in body
    assert "semantic_rag_assist" not in analyze_dev
    assert "ai_parsing_assist" not in body
    assert "ai_parsing_assist" not in analyze_dev


def test_parse_file_matching_input_trace_is_consistent_with_profile(client):
    resp = _post_txt(client, TECH_CV)
    assert resp.status_code == 200
    body = resp.json()
    trace = body.get("matching_input_trace") or {}
    effective = trace.get("effective_skills") or {}
    profile = body.get("profile") or {}

    assert effective.get("base_count") == len(profile.get("skills_uri") or [])
    assert effective.get("promoted_count") == len(profile.get("skills_uri_promoted") or [])
    assert effective.get("domain_count") == len(profile.get("domain_uris") or [])
