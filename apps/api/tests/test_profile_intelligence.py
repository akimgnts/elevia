from __future__ import annotations

from pathlib import Path

from compass.pipeline.contracts import ParseFilePipelineRequest
from compass.pipeline.profile_parse_pipeline import build_parse_file_response_payload


def test_profile_intelligence_is_exposed_in_parse_payload():
    path = Path("apps/api/data/eval/synthetic_cv_dataset_v1/cv_09_ines_barbier.txt")
    body = build_parse_file_response_payload(
        ParseFilePipelineRequest(
            request_id="profile-intelligence",
            raw_filename=path.name,
            content_type="text/plain",
            file_bytes=path.read_bytes(),
            enrich_llm=0,
        )
    )

    profile_intelligence = body.get("profile_intelligence") or {}

    assert profile_intelligence["dominant_role_block"] == "hr_ops"
    assert "hr" in profile_intelligence["dominant_domains"]
    assert profile_intelligence["role_hypotheses"]
    assert profile_intelligence["profile_summary"].startswith("Profil orienté")
    assert profile_intelligence["top_profile_signals"]
    assert "role_block_scores" in profile_intelligence


def test_generic_noise_does_not_dominate_profile_intelligence(monkeypatch):
    monkeypatch.setattr(
        "compass.profile.profile_intelligence._safe_role_resolution",
        lambda _cv_text, _canonical_skills: {
            "raw_title": "",
            "normalized_title": "",
            "primary_role_family": None,
            "secondary_role_families": [],
            "candidate_occupations": [],
            "occupation_confidence": 0.0,
        },
    )

    from compass.profile.profile_intelligence import build_profile_intelligence

    result = build_profile_intelligence(
        cv_text="communication teamwork leadership",
        profile={},
        profile_cluster={"dominant_cluster": "OTHER", "confidence": 0.2},
        top_signal_units=[],
        secondary_signal_units=[],
        preserved_explicit_skills=[
            {"label": "Communication", "cluster_name": "GENERIC_TRANSVERSAL", "genericity_score": 0.7},
            {"label": "Excel", "cluster_name": "GENERIC_TRANSVERSAL", "genericity_score": 0.1},
            {"label": "Recruitment", "cluster_name": "GENERIC_TRANSVERSAL", "genericity_score": 0.2},
        ],
        profile_summary_skills=[],
        canonical_skills=[],
    )

    assert result["dominant_role_block"] == "hr_ops"
    assert "Recruitment" in result["top_profile_signals"]


def test_finance_controlling_profile_intelligence_prefers_finance_block():
    path = Path("apps/api/data/eval/synthetic_cv_dataset_v1/cv_07_pierre_lemaire.txt")
    body = build_parse_file_response_payload(
        ParseFilePipelineRequest(
            request_id="profile-intelligence-finance",
            raw_filename=path.name,
            content_type="text/plain",
            file_bytes=path.read_bytes(),
            enrich_llm=0,
        )
    )

    profile_intelligence = body.get("profile_intelligence") or {}

    assert profile_intelligence["dominant_role_block"] == "finance_ops"
    assert profile_intelligence["role_hypotheses"][0]["label"] in {"Contrôleur de gestion", "Financial Analyst"}
