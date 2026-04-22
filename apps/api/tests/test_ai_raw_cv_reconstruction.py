from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass import ai_raw_cv_reconstruction as raw_cv


def test_ai1_flag_off_does_not_call_provider(monkeypatch):
    monkeypatch.delenv("ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION", raising=False)
    calls: list[str] = []

    def fake_call(prompt: str) -> dict:
        calls.append(prompt)
        return {}

    monkeypatch.setattr(raw_cv, "call_llm_reconstruction", fake_call, raising=False)

    result = raw_cv.build_raw_cv_reconstruction(
        cv_text="Data Analyst\nPython SQL",
        request_id="off",
        filename="cv.txt",
        content_type="text/plain",
    )

    assert result.status == "skipped"
    assert calls == []


def test_ai1_provider_response_is_mapped_to_contract(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION", "1")

    def fake_call(prompt: str) -> dict:
        assert "Return valid JSON only" in prompt
        assert "Data Analyst" in prompt
        assert "Do not freely rewrite, compress, summarize, or elegantly paraphrase the CV." in prompt
        assert "Preserve maximum source content." in prompt
        assert "Keep the original order when possible." in prompt
        assert "Do light normalization only" in prompt
        assert "Rebuild line-by-line or block-by-block when useful" in prompt
        return {
            "rebuilt_profile_text": "Data Analyst\nSidel\n2023-2025\nBuilt Power BI dashboards",
            "sections": [
                {
                    "type": "experience",
                    "title": "Experience",
                    "text": "Data Analyst at Sidel",
                    "evidence": ["Data Analyst", "Sidel"],
                    "confidence": 0.9,
                }
            ],
            "raw_experiences": [
                {
                    "title": "Data Analyst",
                    "organization": "Sidel",
                    "period": "2023-2025",
                    "missions": ["Built Power BI dashboards"],
                    "tools": ["Power BI"],
                    "evidence": ["Built Power BI dashboards"],
                    "confidence": 0.9,
                }
            ],
            "raw_projects": [],
            "raw_education": [],
            "raw_certifications": [],
            "raw_languages": [],
            "raw_skills": [
                {
                    "label": "Power BI",
                    "source_section": "experience",
                    "evidence": ["Power BI"],
                    "confidence": 0.8,
                }
            ],
            "warnings": [],
        }

    monkeypatch.setattr(raw_cv, "call_llm_reconstruction", fake_call, raising=False)

    result = raw_cv.build_raw_cv_reconstruction(
        cv_text="Data Analyst\nSidel\nPower BI",
        request_id="on",
        filename="cv.txt",
        content_type="text/plain",
    )

    assert result.status == "ok"
    assert result.rebuilt_profile_text.startswith("Data Analyst")
    assert result.sections[0].type == "experience"
    assert result.raw_experiences[0].title == "Data Analyst"
    assert result.raw_experiences[0].organization == "Sidel"
    assert result.raw_skills[0].label == "Power BI"
    assert result.warnings == []


def test_ai1_noisy_cv_uses_rebuilt_provider_text(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION", "1")

    def fake_call(prompt: str) -> dict:
        return {
            "rebuilt_profile_text": "Experience\nData Analyst - Sidel\nMissions: data cleaning, reporting",
            "sections": [
                {
                    "type": "experience",
                    "title": "Experience",
                    "text": "Data Analyst - Sidel",
                    "evidence": ["Data Analyst|Sidel"],
                    "confidence": 0.8,
                }
            ],
            "raw_experiences": [],
            "raw_projects": [],
            "raw_education": [],
            "raw_certifications": [],
            "raw_languages": [],
            "raw_skills": [],
            "warnings": [],
        }

    monkeypatch.setattr(raw_cv, "call_llm_reconstruction", fake_call, raising=False)

    result = raw_cv.build_raw_cv_reconstruction(
        cv_text="Data Analyst|Sidel|data cleaning|reporting",
        request_id="noisy",
        filename="cv.txt",
        content_type="text/plain",
    )

    assert result.status == "ok"
    assert result.rebuilt_profile_text == "Experience\nData Analyst - Sidel\nMissions: data cleaning, reporting"
    assert "|" not in result.rebuilt_profile_text


def test_ai1_provider_error_falls_back_to_original_text(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION", "1")

    def fake_call(prompt: str) -> dict:
        raise TimeoutError("provider timeout")

    monkeypatch.setattr(raw_cv, "call_llm_reconstruction", fake_call, raising=False)

    result = raw_cv.build_raw_cv_reconstruction(
        cv_text="Original extracted CV text",
        request_id="fallback",
        filename="cv.txt",
        content_type="text/plain",
    )

    assert result.status == "ok"
    assert result.rebuilt_profile_text == "Original extracted CV text"
    assert result.warnings
    assert result.warnings[0].code == "provider_fallback"


def test_ai1_invalid_provider_payload_falls_back_to_original_text(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION", "1")

    def fake_call(prompt: str) -> dict:
        return ["not", "a", "json", "object"]  # type: ignore[return-value]

    monkeypatch.setattr(raw_cv, "call_llm_reconstruction", fake_call, raising=False)

    result = raw_cv.build_raw_cv_reconstruction(
        cv_text="Original extracted CV text",
        request_id="fallback-invalid",
        filename="cv.txt",
        content_type="text/plain",
    )

    assert result.status == "ok"
    assert result.rebuilt_profile_text == "Original extracted CV text"
    assert result.warnings[0].code == "provider_fallback"
