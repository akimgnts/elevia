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
from compass.pipeline.profile_parse_pipeline import (
    build_parse_baseline_response_payload,
    build_parse_file_response_payload,
)


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


def test_parse_pipeline_includes_document_understanding_in_profile(monkeypatch):
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    request = ParseFilePipelineRequest(
        request_id="test-request",
        raw_filename="cv.txt",
        content_type="text/plain",
        file_bytes=TECH_CV.encode("utf-8"),
        enrich_llm=0,
    )

    body = build_parse_file_response_payload(request)

    assert "document_understanding" in body["profile"]


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
