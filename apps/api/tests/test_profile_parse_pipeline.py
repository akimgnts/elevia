from __future__ import annotations

import io
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.pipeline.contracts import ParseFilePipelineRequest
from compass.pipeline import profile_parse_pipeline as parse_pipeline
from compass.pipeline.profile_parse_pipeline import (
    build_parse_baseline_response_payload,
    build_parse_file_response_payload,
    should_use_ai_raw_cv_reconstruction,
)
from compass import ai_raw_cv_reconstruction as raw_cv


TECH_CV = "Python SQL Excel"


def test_parse_pipeline_is_deterministic(monkeypatch):
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    request = ParseFilePipelineRequest(
        request_id="test-request",
        raw_filename="cv.txt",
        content_type="text/plain",
        file_bytes=TECH_CV.encode("utf-8"),
        enrich_llm=0,
    )

    a = build_parse_file_response_payload(request)
    b = build_parse_file_response_payload(request)

    assert a["skills_raw"] == b["skills_raw"]
    assert a["skills_canonical"] == b["skills_canonical"]
    assert a["canonical_skills_count"] == b["canonical_skills_count"]
    assert a["matching_input_trace"] == b["matching_input_trace"]
    assert a["profile"] == b["profile"]
    assert a["preserved_explicit_skills"] == b["preserved_explicit_skills"]
    assert a["profile_summary_skills"] == b["profile_summary_skills"]
    assert a["top_signal_units"] == b["top_signal_units"]
    assert a["structured_signal_stats"] == b["structured_signal_stats"]
    assert a["enriched_signals"] == b["enriched_signals"]
    assert a["concept_signals"] == b["concept_signals"]
    assert a["profile_intelligence"] == b["profile_intelligence"]
    assert a["profile_intelligence_ai_assist"] == b["profile_intelligence_ai_assist"]


def test_raw_cv_reconstruction_flag_off_is_skipped_and_non_destructive(monkeypatch):
    monkeypatch.delenv("ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION", raising=False)
    request = ParseFilePipelineRequest(
        request_id="raw-off",
        raw_filename="cv.txt",
        content_type="text/plain",
        file_bytes=b"Data Analyst\nPython SQL Excel",
        enrich_llm=0,
    )

    body = build_parse_file_response_payload(request)

    assert body["raw_cv_reconstruction"]["status"] == "skipped"
    assert body["raw_cv_reconstruction"]["rebuilt_profile_text"] == ""
    assert body["extracted_text_length"] == len("Data Analyst\nPython SQL Excel")
    assert body["profile"].get("career_profile") is not None


def test_raw_cv_reconstruction_flag_on_stub_is_transportable(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION", "1")
    cv_text = "Data Analyst\nExperience\nPython SQL Excel"
    monkeypatch.setattr(
        parse_pipeline,
        "evaluate_ai_raw_cv_reconstruction_decision",
        lambda context: {
            "enabled": True,
            "reasons": ["no_experience", "low_structured_signal"],
            "metrics": {
                "experiences": 0,
                "structured_signal_units": 3,
                "validated_items": 8,
                "canonical_skills": 15,
            },
        },
    )
    monkeypatch.setattr(
        raw_cv,
        "call_llm_reconstruction",
        lambda prompt: {
            "rebuilt_profile_text": cv_text,
            "sections": [],
            "raw_experiences": [],
            "raw_projects": [],
            "raw_education": [],
            "raw_certifications": [],
            "raw_languages": [],
            "raw_skills": [],
            "warnings": [],
        },
    )
    request = ParseFilePipelineRequest(
        request_id="raw-on",
        raw_filename="cv.txt",
        content_type="text/plain",
        file_bytes=cv_text.encode("utf-8"),
        enrich_llm=0,
    )

    body = build_parse_file_response_payload(request)
    reconstruction = body["raw_cv_reconstruction"]

    assert reconstruction["version"] == "raw_cv_reconstruction_v1"
    assert reconstruction["status"] == "ok"
    assert reconstruction["rebuilt_profile_text"] == cv_text
    assert isinstance(reconstruction["sections"], list)
    assert isinstance(reconstruction["raw_experiences"], list)
    assert isinstance(reconstruction["raw_projects"], list)
    assert isinstance(reconstruction["raw_education"], list)
    assert isinstance(reconstruction["raw_certifications"], list)
    assert isinstance(reconstruction["raw_languages"], list)
    assert isinstance(reconstruction["raw_skills"], list)
    assert isinstance(reconstruction["warnings"], list)
    assert body["profile"].get("career_profile") is not None
    assert body["canonical_skills_count"] >= 0
    assert "skills_uri" in body["profile"] or body["profile"].get("skills") is not None


def test_ai1_dirty_policy_blocks_clean_profile():
    assert should_use_ai_raw_cv_reconstruction(
        {
            "career_profile": {"experiences": [{"title": "A"}, {"title": "B"}]},
            "structured_signal_units": [{} for _ in range(5)],
            "validated_items": [{} for _ in range(10)],
            "canonical_skills": [{} for _ in range(20)],
            "cv_text": "clean cv",
        }
    ) is False


def test_ai1_dirty_policy_enables_noisy_profile():
    assert should_use_ai_raw_cv_reconstruction(
        {
            "career_profile": {"experiences": []},
            "structured_signal_units": [{} for _ in range(3)],
            "validated_items": [{} for _ in range(12)],
            "canonical_skills": [{} for _ in range(25)],
            "cv_text": "noisy cv",
        }
    ) is True


def test_ai1_dirty_policy_enables_no_experience_with_low_validated_items():
    assert should_use_ai_raw_cv_reconstruction(
        {
            "career_profile": {"experiences": []},
            "structured_signal_units": [{} for _ in range(6)],
            "validated_items": [{} for _ in range(8)],
            "canonical_skills": [{} for _ in range(25)],
            "cv_text": "no experience with weak validation",
        }
    ) is True


def test_ai1_dirty_policy_enables_no_experience_with_low_canonical_skills():
    assert should_use_ai_raw_cv_reconstruction(
        {
            "career_profile": {"experiences": []},
            "structured_signal_units": [{} for _ in range(6)],
            "validated_items": [{} for _ in range(12)],
            "canonical_skills": [{} for _ in range(15)],
            "cv_text": "no experience with weak canonical skills",
        }
    ) is True


def test_ai1_dirty_policy_keeps_no_experience_but_strong_signals_off():
    assert should_use_ai_raw_cv_reconstruction(
        {
            "career_profile": {"experiences": []},
            "structured_signal_units": [{} for _ in range(4)],
            "validated_items": [{} for _ in range(9)],
            "canonical_skills": [{} for _ in range(16)],
            "cv_text": "no experience but otherwise usable",
        }
    ) is False


def test_ai1_dirty_policy_keeps_medium_profile_off():
    assert should_use_ai_raw_cv_reconstruction(
        {
            "career_profile": {"experiences": [{"title": "A"}]},
            "structured_signal_units": [{} for _ in range(3)],
            "validated_items": [{} for _ in range(8)],
            "canonical_skills": [{} for _ in range(15)],
            "cv_text": "medium cv",
        }
    ) is False


def test_ai1_dirty_policy_hard_blocks_threshold_profile():
    assert should_use_ai_raw_cv_reconstruction(
        {
            "career_profile": {"experiences": [{"title": "A"}, {"title": "B"}]},
            "structured_signal_units": [{} for _ in range(5)],
            "validated_items": [{} for _ in range(5)],
            "canonical_skills": [{} for _ in range(10)],
            "cv_text": "threshold cv",
        }
    ) is False


def test_ai1_pipeline_does_not_call_provider_when_policy_blocks(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION", "1")
    monkeypatch.setattr(
        parse_pipeline,
        "evaluate_ai_raw_cv_reconstruction_decision",
        lambda context: {
            "enabled": False,
            "reasons": ["good_skills_signal"],
            "metrics": {
                "experiences": 2,
                "structured_signal_units": 5,
                "validated_items": 10,
                "canonical_skills": 20,
            },
        },
    )

    def fail_provider(**kwargs):
        raise AssertionError("AI1 provider should not be called for a protected profile")

    monkeypatch.setattr(parse_pipeline, "build_raw_cv_reconstruction", fail_provider)

    body = build_parse_file_response_payload(
        ParseFilePipelineRequest(
            request_id="ai1-policy-block",
            raw_filename="cv.txt",
            content_type="text/plain",
            file_bytes=b"Data Analyst\nPython SQL Excel",
            enrich_llm=0,
        )
    )

    assert body["raw_cv_reconstruction"]["status"] == "skipped"


def test_ai1_pipeline_calls_provider_when_policy_enables(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION", "1")
    monkeypatch.setattr(
        parse_pipeline,
        "evaluate_ai_raw_cv_reconstruction_decision",
        lambda context: {
            "enabled": True,
            "reasons": ["no_experience", "very_low_structured_signal"],
            "metrics": {
                "experiences": 0,
                "structured_signal_units": 2,
                "validated_items": 8,
                "canonical_skills": 15,
            },
        },
    )

    calls: list[str] = []

    def fake_provider(**kwargs):
        calls.append(kwargs["cv_text"])
        return raw_cv.RawCvReconstructionV1(
            status="ok",
            rebuilt_profile_text=kwargs["cv_text"],
        )

    monkeypatch.setattr(parse_pipeline, "build_raw_cv_reconstruction", fake_provider)

    body = build_parse_file_response_payload(
        ParseFilePipelineRequest(
            request_id="ai1-policy-on",
            raw_filename="cv.txt",
            content_type="text/plain",
            file_bytes=b"Data Analyst\nPython SQL Excel",
            enrich_llm=0,
        )
    )

    assert calls == ["Data Analyst\nPython SQL Excel"]
    assert body["raw_cv_reconstruction"]["status"] == "ok"


def test_profile_reconstruction_flag_off_is_skipped(monkeypatch):
    monkeypatch.delenv("ELEVIA_ENABLE_AI_PROFILE_RECONSTRUCTION", raising=False)
    body = build_parse_file_response_payload(
        ParseFilePipelineRequest(
            request_id="profile-reconstruction-off",
            raw_filename="cv.txt",
            content_type="text/plain",
            file_bytes=b"Data Analyst\nPython SQL Excel",
            enrich_llm=0,
        )
    )

    reconstruction = body["profile_reconstruction"]
    assert reconstruction["version"] == "v2"
    assert reconstruction["source"] == "ai2_stub"
    assert reconstruction["status"] == "skipped"
    assert reconstruction["suggested_summary"] == {"text": "", "confidence": 0.0, "evidence": []}
    assert reconstruction["suggested_experiences"] == []
    assert reconstruction["suggested_skills"] == []
    assert reconstruction["suggested_projects"] == []
    assert reconstruction["suggested_certifications"] == []
    assert reconstruction["suggested_languages"] == []
    assert reconstruction["link_suggestions"] == []
    assert isinstance(reconstruction["warnings"], list)


def test_profile_reconstruction_flag_on_stub_is_transportable(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_AI_PROFILE_RECONSTRUCTION", "1")
    body = build_parse_file_response_payload(
        ParseFilePipelineRequest(
            request_id="profile-reconstruction-on",
            raw_filename="cv.txt",
            content_type="text/plain",
            file_bytes=b"Data Analyst\nPython SQL Excel",
            enrich_llm=0,
        )
    )

    reconstruction = body["profile_reconstruction"]
    assert reconstruction["version"] == "v2"
    assert reconstruction["source"] == "ai2_stub"
    assert reconstruction["status"] == "ok"
    assert reconstruction["warnings"] == [{"code": "STUB", "message": "No provider connected"}]
    assert body["profile"].get("career_profile") is not None
    assert body["canonical_skills_count"] >= 0


def test_ai1_ai2_flags_coexist_without_mutating_profile_outputs(monkeypatch):
    cv_text = "Data Analyst\nPython SQL Excel"
    monkeypatch.setattr(
        parse_pipeline,
        "evaluate_ai_raw_cv_reconstruction_decision",
        lambda context: {
            "enabled": True,
            "reasons": ["no_experience", "low_structured_signal"],
            "metrics": {
                "experiences": 0,
                "structured_signal_units": 3,
                "validated_items": 8,
                "canonical_skills": 15,
            },
        },
    )
    monkeypatch.setattr(
        raw_cv,
        "call_llm_reconstruction",
        lambda prompt: {
            "rebuilt_profile_text": cv_text,
            "sections": [],
            "raw_experiences": [],
            "raw_projects": [],
            "raw_education": [],
            "raw_certifications": [],
            "raw_languages": [],
            "raw_skills": [],
            "warnings": [],
        },
    )
    request = ParseFilePipelineRequest(
        request_id="ai-coexist",
        raw_filename="cv.txt",
        content_type="text/plain",
        file_bytes=cv_text.encode("utf-8"),
        enrich_llm=0,
    )

    monkeypatch.delenv("ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION", raising=False)
    monkeypatch.delenv("ELEVIA_ENABLE_AI_PROFILE_RECONSTRUCTION", raising=False)
    both_off = build_parse_file_response_payload(request)

    monkeypatch.setenv("ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION", "1")
    monkeypatch.delenv("ELEVIA_ENABLE_AI_PROFILE_RECONSTRUCTION", raising=False)
    ai1_on = build_parse_file_response_payload(request)

    monkeypatch.delenv("ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION", raising=False)
    monkeypatch.setenv("ELEVIA_ENABLE_AI_PROFILE_RECONSTRUCTION", "1")
    ai2_on = build_parse_file_response_payload(request)

    monkeypatch.setenv("ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION", "1")
    monkeypatch.setenv("ELEVIA_ENABLE_AI_PROFILE_RECONSTRUCTION", "1")
    both_on = build_parse_file_response_payload(request)

    assert ai1_on["raw_cv_reconstruction"]["status"] == "ok"
    assert ai1_on["profile_reconstruction"]["status"] == "skipped"
    assert ai2_on["raw_cv_reconstruction"]["status"] == "skipped"
    assert ai2_on["profile_reconstruction"]["status"] == "ok"
    assert both_on["raw_cv_reconstruction"]["status"] == "ok"
    assert both_on["profile_reconstruction"]["status"] == "ok"

    for body in [ai1_on, ai2_on, both_on]:
        assert body["profile"].get("career_profile") == both_off["profile"].get("career_profile")
        assert body["canonical_skills"] == both_off["canonical_skills"]
        assert body["profile"].get("skills_uri") == both_off["profile"].get("skills_uri")


def test_parse_route_and_pipeline_share_same_contract(monkeypatch):
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    from api.main import app

    client = TestClient(app)
    response = client.post(
        "/profile/parse-file",
        files={"file": ("cv.txt", io.BytesIO(TECH_CV.encode("utf-8")), "text/plain")},
    )
    assert response.status_code == 200
    route_body = response.json()

    pipeline_body = build_parse_file_response_payload(
        ParseFilePipelineRequest(
            request_id="n/a",
            raw_filename="cv.txt",
            content_type="text/plain",
            file_bytes=TECH_CV.encode("utf-8"),
            enrich_llm=0,
        )
    )

    for key in [
        "source",
        "pipeline_used",
        "pipeline_variant",
        "skills_raw",
        "skills_canonical",
        "canonical_skills_count",
        "mapping_inputs_count",
        "preserved_explicit_skills",
        "profile_summary_skills",
        "top_signal_units",
        "structured_signal_stats",
        "enriched_signals",
        "concept_signals",
        "profile_intelligence",
        "profile_intelligence_ai_assist",
    ]:
        assert route_body[key] == pipeline_body[key]
    assert route_body["matching_input_trace"] == json.loads(
        json.dumps(pipeline_body["matching_input_trace"])
    )
    assert route_body["analyze_dev"] == json.loads(json.dumps(pipeline_body["analyze_dev"]))
    assert "semantic_rag_assist" not in route_body
    assert "semantic_rag_assist" not in pipeline_body
    assert "ai_parsing_assist" not in route_body
    assert "ai_parsing_assist" not in pipeline_body


def test_parse_baseline_route_and_pipeline_share_same_contract(monkeypatch):
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    from api.main import app

    client = TestClient(app)
    response = client.post("/profile/parse-baseline", json={"cv_text": TECH_CV})
    assert response.status_code == 200
    route_body = response.json()

    pipeline_body = build_parse_baseline_response_payload(
        cv_text=TECH_CV,
        request_id="n/a",
    )

    assert route_body == json.loads(json.dumps(pipeline_body))


def test_parse_pipeline_v12_recovers_non_tech_domain_skills_without_ml_false_positive(monkeypatch):
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    hr_cv = (
        "Chargee RH generaliste\n"
        "Administration du personnel recrutement onboarding Excel\n"
        "suivi dossiers salaries plan de formation\n"
        "J ai travaille sur l integration et l organisation d entretiens"
    )

    body = build_parse_file_response_payload(
        ParseFilePipelineRequest(
            request_id="hr-v12",
            raw_filename="hr.txt",
            content_type="text/plain",
            file_bytes=hr_cv.encode("utf-8"),
            enrich_llm=0,
        )
    )

    preserved = {item["label"] for item in body["preserved_explicit_skills"]}
    canonical = {item.get("label") for item in body["canonical_skills"] if item.get("label")}
    top_domains = {item.get("domain") for item in body.get("top_signal_units") or []}

    assert "HR Administration" in preserved
    assert "Recruitment" in preserved
    assert "Onboarding" in preserved
    assert "Machine Learning" not in canonical
    assert "hr" in top_domains
    assert body["profile_intelligence"]["dominant_role_block"] == "hr_ops"
    assert body["profile_intelligence_ai_assist"]["enabled"] is False
    assert "ai_parsing_assist" not in body


def test_parse_pipeline_structured_tightening_blocks_tableau_leak(monkeypatch):
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    cv_text = (
        "Coordinateur logistique\n"
        "Mon role a souvent consiste a gerer des priorites de livraison, securiser des departs et tenir des tableaux de suivi.\n"
        "Excel TMS interne Outlook\n"
    )

    body = build_parse_file_response_payload(
        ParseFilePipelineRequest(
            request_id="ops-tightening",
            raw_filename="ops.txt",
            content_type="text/plain",
            file_bytes=cv_text.encode("utf-8"),
            enrich_llm=0,
        )
    )

    preserved = {item["label"] for item in body["preserved_explicit_skills"]}
    stats = body.get("structured_signal_stats") or {}

    assert "Tableau" not in preserved
    assert stats.get("structured_units_promoted_count", 0) <= 6
