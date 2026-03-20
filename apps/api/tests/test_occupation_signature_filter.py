from __future__ import annotations

from compass.roles.occupation_signature_filter import (
    OccupationSignatureFilter,
    filter_occupation_signature_rows,
)


def _rows() -> list[dict]:
    return [
        {
            "onetsoc_code": "15-1252.00",
            "canonical_skill_id": "skill:problem_solving",
            "canonical_label": "Problem Solving",
        },
        {
            "onetsoc_code": "15-1252.00",
            "canonical_skill_id": "skill:erp_usage",
            "canonical_label": "ERP Usage",
        },
        {
            "onetsoc_code": "13-1081.00",
            "canonical_skill_id": "skill:problem_solving",
            "canonical_label": "Problem Solving",
        },
        {
            "onetsoc_code": "13-1081.00",
            "canonical_skill_id": "skill:supply_chain_management",
            "canonical_label": "Supply Chain Management",
        },
        {
            "onetsoc_code": "41-4011.00",
            "canonical_skill_id": "skill:problem_solving",
            "canonical_label": "Problem Solving",
        },
        {
            "onetsoc_code": "41-4011.00",
            "canonical_skill_id": "skill:crm_management",
            "canonical_label": "CRM Management",
        },
    ]


def test_occupation_signature_filter_removes_seeded_low_discriminant_skills():
    filtered = filter_occupation_signature_rows(_rows(), total_occupations=3)

    assert {row["canonical_skill_id"] for row in filtered} == {
        "skill:erp_usage",
        "skill:supply_chain_management",
        "skill:crm_management",
    }


def test_occupation_signature_filter_is_deterministic_and_stable():
    filterer = OccupationSignatureFilter()
    first = filterer.filter_rows(_rows(), total_occupations=3)
    second = filterer.filter_rows(_rows(), total_occupations=3)

    assert first == second
    assert [row["canonical_skill_id"] for row in first] == [
        "skill:erp_usage",
        "skill:supply_chain_management",
        "skill:crm_management",
    ]


def test_occupation_signature_filter_preserves_domain_and_technical_signals():
    rows = [
        {
            "onetsoc_code": "15-1252.00",
            "canonical_skill_id": "skill:linux_administration",
            "canonical_label": "Linux Administration",
        },
        {
            "onetsoc_code": "15-1252.00",
            "canonical_skill_id": "skill:cloud_architecture",
            "canonical_label": "Cloud Architecture",
        },
        {
            "onetsoc_code": "15-1252.00",
            "canonical_skill_id": "skill:project_management",
            "canonical_label": "Project Management",
        },
    ]

    filtered = filter_occupation_signature_rows(rows, total_occupations=100)

    assert [row["canonical_skill_id"] for row in filtered] == [
        "skill:linux_administration",
        "skill:cloud_architecture",
        "skill:project_management",
    ]
