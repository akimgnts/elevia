from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.structuring.skill_link_builder import build_skill_links_for_experience
from documents.career_profile import CareerExperience, CareerSkillSelection


def _tool_labels(links):
    return [[tool.label for tool in link.tools] for link in links]


def test_build_skill_links_attaches_tools_to_matching_canonical_skill():
    exp = CareerExperience(
        title="Data Analyst",
        company="ACME",
        responsibilities=[
            "Analyse de performance avec Python et SQL",
            "Production de tableaux de bord Power BI pour le reporting",
        ],
        tools=["Python", "SQL", "Power BI"],
        canonical_skills_used=[
            CareerSkillSelection(label="Analyse de données"),
            CareerSkillSelection(label="Reporting"),
        ],
        autonomy_level="autonomous",
    )

    links = build_skill_links_for_experience(exp)

    assert len(links) == 2
    assert {link.skill.label for link in links} == {"Analyse de données", "Reporting"}
    assert any("Python" in labels for labels in _tool_labels(links))
    assert any("SQL" in labels for labels in _tool_labels(links))
    assert any("Power BI" in labels for labels in _tool_labels(links))
    assert all(link.autonomy_level == "autonomous" for link in links)
    assert all(link.context for link in links)


def test_build_skill_links_skips_when_no_canonical_skills_exist():
    exp = CareerExperience(
        title="Assistant",
        company="ACME",
        responsibilities=["Support sur Excel et Outlook"],
        tools=["Excel", "Outlook"],
        canonical_skills_used=[],
    )

    links = build_skill_links_for_experience(exp)

    assert links == []


def test_build_skill_links_uses_closest_canonical_skill_for_unmatched_tool():
    exp = CareerExperience(
        title="Business Analyst",
        company="ACME",
        responsibilities=[
            "Analyse des écarts avec Excel",
            "Structuration du reporting hebdomadaire",
        ],
        tools=["Excel"],
        canonical_skills_used=[CareerSkillSelection(label="Analyse de données")],
        autonomy_level="partial",
    )

    links = build_skill_links_for_experience(exp)

    assert len(links) == 1
    assert links[0].skill.label == "Analyse de données"
    assert [tool.label for tool in links[0].tools] == ["Excel"]
    assert links[0].context
    assert links[0].autonomy_level == "partial"


def test_build_skill_links_is_deterministic():
    exp = CareerExperience(
        title="Consultant Data",
        company="ACME",
        responsibilities=[
            "Automatisation des reportings avec Python",
            "Analyse des données de performance avec SQL",
        ],
        tools=["Python", "SQL"],
        canonical_skills_used=[
            CareerSkillSelection(label="Analyse de données"),
            CareerSkillSelection(label="Reporting"),
        ],
        autonomy_level="ownership",
    )

    first = build_skill_links_for_experience(exp)
    second = build_skill_links_for_experience(exp)

    assert first == second


def test_build_skill_links_skips_ambiguous_unmatched_tool_with_multiple_skills():
    exp = CareerExperience(
        title="Consultant",
        company="ACME",
        responsibilities=[
            "Analyse des indicateurs de performance",
            "Structuration du reporting mensuel",
        ],
        tools=["Excel"],
        canonical_skills_used=[
            CareerSkillSelection(label="Analyse de données"),
            CareerSkillSelection(label="Reporting"),
        ],
    )

    links = build_skill_links_for_experience(exp)

    assert links
    assert all(tool.label != "Excel" for link in links for tool in link.tools)


def test_build_skill_links_skips_context_only_link_without_explicit_skill_evidence():
    exp = CareerExperience(
        title="Manager",
        company="ACME",
        responsibilities=["Managed budgets and vendor relations"],
        tools=[],
        canonical_skills_used=[CareerSkillSelection(label="Analyse de données")],
    )

    links = build_skill_links_for_experience(exp)

    assert links == []
