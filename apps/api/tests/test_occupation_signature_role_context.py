from compass.roles.occupation_signature_role_context import (
    OccupationSignatureRoleContextRefiner,
    RoleContextRefinementConfig,
    refine_occupation_signature_rows,
)


def test_role_context_refinement_keeps_project_management_with_strong_software_anchors():
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
        {
            "onetsoc_code": "15-1252.00",
            "canonical_skill_id": "skill:linux_administration",
            "canonical_label": "Linux Administration",
        },
    ]

    refined = refine_occupation_signature_rows(
        rows,
        config=RoleContextRefinementConfig(enable_phase2=False, enable_domain_refinement=False),
    )

    assert {row["canonical_skill_id"] for row in refined} == {
        "skill:project_management",
        "skill:backend_development",
        "skill:web_service_api",
        "skill:linux_administration",
    }


def test_role_context_refinement_removes_broad_skill_without_anchor_support():
    rows = [
        {
            "onetsoc_code": "41-4011.00",
            "canonical_skill_id": "skill:project_management",
            "canonical_label": "Project Management",
        },
        {
            "onetsoc_code": "41-4011.00",
            "canonical_skill_id": "skill:crm_management",
            "canonical_label": "CRM Management",
        },
        {
            "onetsoc_code": "41-4011.00",
            "canonical_skill_id": "skill:lead_generation",
            "canonical_label": "Lead Generation",
        },
    ]

    refined = refine_occupation_signature_rows(
        rows,
        config=RoleContextRefinementConfig(enable_phase2=False, enable_domain_refinement=False),
    )

    assert {row["canonical_skill_id"] for row in refined} == {
        "skill:crm_management",
        "skill:lead_generation",
    }


def test_role_context_refinement_requires_procurement_ops_context_for_erp_usage():
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
        {
            "onetsoc_code": "13-1081.00",
            "canonical_skill_id": "skill:vendor_management",
            "canonical_label": "Vendor Management",
        },
        {
            "onetsoc_code": "13-1081.00",
            "canonical_skill_id": "skill:process_mapping",
            "canonical_label": "Process Mapping",
        },
    ]

    refined = refine_occupation_signature_rows(
        rows,
        config=RoleContextRefinementConfig(enable_phase2=False, enable_domain_refinement=False),
    )

    assert {row["canonical_skill_id"] for row in refined} == {
        "skill:erp_usage",
        "skill:supply_chain_management",
        "skill:procurement_basics",
        "skill:vendor_management",
        "skill:process_mapping",
    }


def test_role_context_refinement_is_deterministic_and_exposes_anchor_diagnostics():
    rows = [
        {
            "onetsoc_code": "11-1021.00",
            "canonical_skill_id": "skill:operations_management",
            "canonical_label": "Operations Management",
        },
        {
            "onetsoc_code": "11-1021.00",
            "canonical_skill_id": "skill:workforce_scheduling",
            "canonical_label": "Workforce Scheduling",
        },
        {
            "onetsoc_code": "11-1021.00",
            "canonical_skill_id": "skill:supply_chain_management",
            "canonical_label": "Supply Chain Management",
        },
        {
            "onetsoc_code": "11-1021.00",
            "canonical_skill_id": "skill:vendor_management",
            "canonical_label": "Vendor Management",
        },
    ]

    refiner = OccupationSignatureRoleContextRefiner(
        config=RoleContextRefinementConfig(enable_phase2=False, enable_domain_refinement=False)
    )
    first_rows, first_decisions = refiner.filter_rows(rows, return_diagnostics=True)
    second_rows, second_decisions = refiner.filter_rows(rows, return_diagnostics=True)

    assert first_rows == second_rows
    assert first_decisions == second_decisions
    ops_decision = next(decision for decision in first_decisions if decision.canonical_skill_id == "skill:operations_management")
    assert ops_decision.retained is True
    assert set(ops_decision.matched_anchor_ids) == {
        "skill:supply_chain_management",
        "skill:vendor_management",
        "skill:workforce_scheduling",
    }
