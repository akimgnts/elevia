from __future__ import annotations

from compass.roles.occupation_signature_calibration import calibrate_occupation_signature_rows


def test_occupation_signature_calibration_keeps_medium_signal_skill_in_allowed_cluster_context():
    rows = [
        {
            "onetsoc_code": "15-1252.00",
            "canonical_skill_id": "skill:project_management",
            "canonical_label": "Project Management",
        },
        {
            "onetsoc_code": "15-1252.00",
            "canonical_skill_id": "skill:backend_development",
            "canonical_label": "Backend Development",
        },
        {
            "onetsoc_code": "15-1252.00",
            "canonical_skill_id": "skill:web_service_api",
            "canonical_label": "Web Service API",
        },
    ]

    calibrated = calibrate_occupation_signature_rows(rows, total_occupations=3)

    assert {row["canonical_skill_id"] for row in calibrated} == {
        "skill:project_management",
        "skill:backend_development",
        "skill:web_service_api",
    }


def test_occupation_signature_calibration_removes_medium_signal_skill_without_allowed_cluster_support():
    rows = [
        {
            "onetsoc_code": "31-9091.00",
            "canonical_skill_id": "skill:project_management",
            "canonical_label": "Project Management",
        },
        {
            "onetsoc_code": "31-9091.00",
            "canonical_skill_id": "skill:crm_management",
            "canonical_label": "CRM Management",
        },
        {
            "onetsoc_code": "31-9091.00",
            "canonical_skill_id": "skill:lead_generation",
            "canonical_label": "Lead Generation",
        },
        {
            "onetsoc_code": "31-9091.00",
            "canonical_skill_id": "skill:email_marketing",
            "canonical_label": "Email Marketing",
        },
    ]

    calibrated = calibrate_occupation_signature_rows(rows, total_occupations=3)

    assert {row["canonical_skill_id"] for row in calibrated} == {
        "skill:crm_management",
        "skill:lead_generation",
        "skill:email_marketing",
    }


def test_occupation_signature_calibration_is_deterministic():
    rows = [
        {
            "onetsoc_code": "13-1081.00",
            "canonical_skill_id": "skill:erp_usage",
            "canonical_label": "ERP Usage",
        },
        {
            "onetsoc_code": "13-1081.00",
            "canonical_skill_id": "skill:supply_chain_management",
            "canonical_label": "Supply Chain Management",
        },
        {
            "onetsoc_code": "13-1081.00",
            "canonical_skill_id": "skill:procurement_basics",
            "canonical_label": "Procurement Basics",
        },
    ]

    first = calibrate_occupation_signature_rows(rows, total_occupations=3)
    second = calibrate_occupation_signature_rows(rows, total_occupations=3)

    assert first == second
