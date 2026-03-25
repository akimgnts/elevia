from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.canonical_pipeline import run_cv_pipeline
from compass.extraction.enriched_signal_builder import build_enriched_signals
from compass.pipeline.contracts import ParseFilePipelineRequest
from compass.pipeline.profile_parse_pipeline import build_parse_file_response_payload


def test_phrase_splitting_preserves_atomic_concepts():
    result = build_enriched_signals([], "data cleaning anomaly detection forecasting")
    normalized = {item["normalized"] for item in result["enriched_signals"]}

    assert "data cleaning" in normalized
    assert "anomaly detection" in normalized
    assert "forecasting" in normalized


def test_enriched_signals_are_additive_and_do_not_change_canonical_output():
    cv_text = "Python SQL Power BI\ndata cleaning anomaly detection forecasting"
    baseline = run_cv_pipeline(cv_text, profile_id="enriched-signals-baseline")
    body = build_parse_file_response_payload(
        ParseFilePipelineRequest(
            request_id="enriched-signals",
            raw_filename="cv.txt",
            content_type="text/plain",
            file_bytes=cv_text.encode("utf-8"),
            enrich_llm=0,
        )
    )

    assert body["skills_canonical"] == baseline.baseline_result["skills_canonical"]
    assert body["canonical_count"] == baseline.baseline_result["canonical_count"]
    assert body["canonical_skills_count"] >= 1
    assert len(body["enriched_signals"]) > body["canonical_skills_count"]


def test_noise_filtering_keeps_skill_list_without_language_metadata():
    result = build_enriched_signals([], "Francais · Anglais professionnel\nSAP, Excel, reporting")
    normalized = {item["normalized"] for item in result["enriched_signals"]}

    assert "francais" not in normalized
    assert "anglais professionnel" not in normalized
    assert "sap" in normalized
    assert "excel" in normalized
    assert "reporting" in normalized


def test_domain_preservation_keeps_sales_signal():
    result = build_enriched_signals([], "gestion portefeuille clients")
    signals = result["enriched_signals"]

    assert signals
    assert any(item["normalized"] in {"gestion portefeuille clients", "gestion portefeuille", "portefeuille clients"} for item in signals)
    assert any(item["domain"] in {"sales", "finance"} for item in signals)
