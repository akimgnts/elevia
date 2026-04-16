from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.structuring import ProfileEnrichmentAgent


def _payload() -> dict:
    return {
        "career_profile": {
            "schema_version": "v2",
            "enrichment_meta": {
                "source": "seed",
                "experiences": [
                    {
                        "note": "keep",
                        "skill_links": [
                            {
                                "tools": [
                                    {"label": "Python", "source": "seed", "confidence": 0.9}
                                ],
                                "context": {"source": "seed", "confidence": 0.8},
                                "autonomy_level": {"source": "seed", "confidence": 0.8},
                            },
                            {
                                "tools": [],
                                "context": None,
                                "autonomy_level": None,
                            },
                        ],
                    }
                ],
            },
            "experiences": [
                {
                    "title": "Data Analyst",
                    "company": "ACME",
                    "responsibilities": [
                        "Analyse de performance avec Python, SQL et Power BI pour le reporting mensuel",
                        "Production de tableaux de bord de performance",
                    ],
                    "tools": ["Python", "SQL", "Power BI"],
                    "autonomy_level": "autonomous",
                    "canonical_skills_used": [
                        {"label": "Analyse de données", "uri": "skill:data_analysis"},
                        {"label": "Reporting", "uri": "skill:reporting"},
                    ],
                    "skill_links": [
                        {
                            "skill": {"label": "Analyse de données", "uri": "skill:data_analysis"},
                            "tools": [{"label": "Python"}],
                            "context": "Analyse de performance",
                            "autonomy_level": "autonomous",
                        },
                        {
                            "skill": {"label": "Reporting", "uri": "skill:reporting"},
                            "tools": [],
                            "context": None,
                            "autonomy_level": None,
                        },
                    ],
                }
            ],
        },
        "structuring_report": {
            "used_signals": [
                {
                    "experience_index": 0,
                    "skill": "Analyse de données",
                    "tools": ["Python"],
                    "context": "Analyse de performance",
                }
            ],
            "uncertain_links": [],
            "questions_for_user": [],
            "canonical_candidates": [],
            "rejected_noise": [{"value": "communication", "reason": "generic_without_context"}],
            "unresolved_candidates": [{"raw_value": "powerbi dashboards"}],
        },
        "canonical_skills": [
            {"label": "Analyse de données", "uri": "skill:data_analysis", "raw": "analyse"},
            {"label": "Reporting", "uri": "skill:reporting", "raw": "reporting"},
        ],
        "unresolved": [{"raw": "powerbi dashboards"}],
        "rejected_noise": [{"value": "communication", "reason": "generic_without_context"}],
    }


def test_profile_enrichment_agent_is_deterministic():
    payload = _payload()
    first = ProfileEnrichmentAgent().run(copy.deepcopy(payload))
    second = ProfileEnrichmentAgent().run(copy.deepcopy(payload))

    assert first == second


def test_profile_enrichment_agent_preserves_existing_skill_link_fields():
    result = ProfileEnrichmentAgent().run(_payload())
    profile = result["career_profile_enriched"]
    links = result["career_profile_enriched"]["experiences"][0]["skill_links"]

    first, second = links
    assert first["skill"]["label"] == "Analyse de données"
    assert first["tools"] == [{"label": "Python"}]
    assert first["context"] == "Analyse de performance"
    assert first["autonomy_level"] == "autonomous"

    assert second["skill"]["label"] == "Reporting"
    assert second["context"]
    assert second["autonomy_level"] == "autonomous"
    assert profile["enrichment_meta"]["source"] == "seed"
    assert profile["enrichment_meta"]["experiences"][0]["note"] == "keep"
    assert profile["enrichment_meta"]["experiences"][0]["skill_links"][0]["context"] == {"source": "seed", "confidence": 0.8}


def test_profile_enrichment_agent_auto_fills_only_above_threshold_with_traceability():
    result = ProfileEnrichmentAgent().run(_payload())
    report = result["enrichment_report"]
    profile = result["career_profile_enriched"]

    assert report["auto_filled"]
    assert all(item["confidence"] >= 0.75 for item in report["auto_filled"])
    assert any(item["target_field"] == "context" for item in report["auto_filled"])
    assert any(item["target_field"] == "autonomy_level" for item in report["auto_filled"])
    assert report["confidence_scores"]
    assert all("context_coherence" in entry for entry in report["confidence_scores"])

    trace = profile["enrichment_meta"]["experiences"][0]["skill_links"][1]
    assert trace["context"]["source"] == "enrichment"
    assert trace["context"]["confidence"] >= 0.75


def test_profile_enrichment_agent_turns_uncertain_signals_into_suggestions_and_questions_without_hallucination():
    payload = _payload()
    payload["career_profile"]["enrichment_meta"] = {"source": "seed", "experiences": [{"note": "keep"}]}
    payload["career_profile"]["experiences"][0]["responsibilities"] = [
        "Suivi administratif et gestion de dossier",
        "Coordination des échanges avec les parties prenantes",
    ]
    payload["career_profile"]["experiences"][0]["tools"] = ["Excel"]
    payload["career_profile"]["experiences"][0]["canonical_skills_used"] = []
    payload["career_profile"]["experiences"][0]["skill_links"] = []
    payload["structuring_report"]["uncertain_links"] = [
        {
            "experience_index": 0,
            "tool": "Excel",
            "candidate_skills": ["Analyse de données", "Reporting"],
            "reason": "tool could not be attached with strong evidence",
        }
    ]

    result = ProfileEnrichmentAgent().run(payload)
    report = result["enrichment_report"]
    profile = result["career_profile_enriched"]

    assert report["suggestions"] or report["questions"]
    assert report["priority_signals"] == []
    assert report["learning_candidates"]
    assert profile["experiences"][0]["skill_links"] == []


def test_profile_enrichment_agent_keeps_empty_experiences_without_creating_skill_links():
    payload = _payload()
    payload["career_profile"]["enrichment_meta"] = {
        "source": "seed",
        "experiences": [{"note": "keep"}],
    }
    payload["career_profile"]["experiences"][0]["skill_links"] = []

    result = ProfileEnrichmentAgent().run(payload)
    profile = result["career_profile_enriched"]

    assert profile["enrichment_meta"]["source"] == "seed"
    assert profile["enrichment_meta"]["experiences"][0]["note"] == "keep"
    assert profile["experiences"][0]["skill_links"] == []
    assert result["enrichment_report"]["suggestions"] or result["enrichment_report"]["questions"]


def test_profile_enrichment_agent_exposes_priority_signals_and_learning_candidates():
    result = ProfileEnrichmentAgent().run(_payload())
    report = result["enrichment_report"]

    assert "priority_signals" in report
    assert "learning_candidates" in report
    assert isinstance(report["priority_signals"], list)
    assert isinstance(report["learning_candidates"], list)
    assert report["priority_signals"]
