from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.structuring.profile_structuring_agent import ProfileStructuringAgent


def _profile_input() -> dict:
    return {
        "career_profile": {
            "schema_version": "v2",
            "experiences": [
                {
                    "title": "Data Analyst",
                    "company": "ACME",
                    "responsibilities": [
                        "Analyse de performance avec Python et SQL",
                        "Analyse de performance avec Python et SQL",
                        "Production de tableaux de bord Power BI pour le reporting",
                    ],
                    "tools": ["Python", "SQL", "Power BI", "Power BI"],
                    "skills": ["Analyse de données", "Reporting"],
                    "autonomy_level": "autonomous",
                    "canonical_skills_used": [
                        {"label": "Analyse de données", "uri": "skill:data_analysis"},
                        {"label": "Reporting", "uri": "skill:reporting"},
                    ],
                    "skill_links": [],
                }
            ],
        },
        "raw_profile": {"skills": ["Python", "SQL", "Power BI"]},
        "canonical_skills": [
            {"label": "Analyse de données", "uri": "skill:data_analysis", "raw": "analyse"},
            {"label": "Reporting", "uri": "skill:reporting", "raw": "reporting"},
        ],
        "unresolved": [{"raw": "powerbi dashboards"}],
        "removed": [{"value": "communication", "reason": "generic_without_context"}],
    }


def test_agent_builds_skill_links_without_hallucinating():
    result = ProfileStructuringAgent().run(_profile_input())

    enriched = result["career_profile_enriched"]
    links = enriched["experiences"][0]["skill_links"]

    assert links
    assert {link["skill"]["label"] for link in links} <= {"Analyse de données", "Reporting"}
    assert any(tool["label"] == "Python" for link in links for tool in link["tools"])
    assert result["structuring_report"]["stats"]["experiences_processed"] == 1
    assert result["structuring_report"]["stats"]["skill_links_created"] == len(links)


def test_agent_is_deterministic():
    payload = _profile_input()
    first = ProfileStructuringAgent().run(copy.deepcopy(payload))
    second = ProfileStructuringAgent().run(copy.deepcopy(payload))

    assert first == second


def test_agent_maps_ambiguity_to_questions_and_uncertain_links():
    payload = _profile_input()
    payload["career_profile"]["experiences"][0]["tools"] = ["Excel"]
    payload["career_profile"]["experiences"][0]["responsibilities"] = [
        "Suivi des indicateurs mensuels",
        "Production de synthèses d'activité",
    ]

    result = ProfileStructuringAgent().run(payload)
    report = result["structuring_report"]

    assert report["questions_for_user"]
    assert any(question["type"] in {"tool", "skill", "context"} for question in report["questions_for_user"])
    assert report["uncertain_links"]


def test_agent_extracts_canonical_candidates_from_unresolved_inputs():
    result = ProfileStructuringAgent().run(_profile_input())
    report = result["structuring_report"]

    assert report["canonical_candidates"]
    assert any(candidate["raw_value"] == "powerbi dashboards" for candidate in report["canonical_candidates"])


def test_agent_keeps_removed_noise_in_report():
    result = ProfileStructuringAgent().run(_profile_input())
    report = result["structuring_report"]

    assert report["rejected_noise"] == [{"value": "communication", "reason": "generic_without_context"}]


def test_agent_uses_canonical_mapping_input_to_fill_experience_skills():
    payload = _profile_input()
    payload["career_profile"]["experiences"][0]["canonical_skills_used"] = []
    payload["career_profile"]["experiences"][0]["skills"] = []

    result = ProfileStructuringAgent().run(payload)
    links = result["career_profile_enriched"]["experiences"][0]["skill_links"]

    assert links
    assert {link["skill"]["label"] for link in links} == {"Analyse de données", "Reporting"}


def test_agent_generates_autonomy_question_when_autonomy_is_missing():
    payload = _profile_input()
    payload["career_profile"]["experiences"][0]["autonomy_level"] = None
    payload["career_profile"]["experiences"][0]["canonical_skills_used"] = []
    payload["career_profile"]["experiences"][0]["skills"] = []
    payload["career_profile"]["experiences"][0]["tools"] = ["Excel"]
    payload["career_profile"]["experiences"][0]["responsibilities"] = ["Suivi des indicateurs mensuels"]
    payload["canonical_skills"] = [{"label": "Analyse de données", "uri": "skill:data_analysis", "raw": "indicateurs"}]

    result = ProfileStructuringAgent().run(payload)
    questions = result["structuring_report"]["questions_for_user"]

    assert any(question["type"] == "autonomy" for question in questions)
