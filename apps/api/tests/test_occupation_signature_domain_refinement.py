from compass.roles.occupation_signature_role_context import (
    OccupationSignatureRoleContextRefiner,
    refine_occupation_signature_rows,
)


def _skill_ids(rows):
    return {row["canonical_skill_id"] for row in rows}


def test_domain_refinement_removes_supply_chain_management_without_execution_anchors():
    rows = [
        {"onetsoc_code": "11-2021.00", "canonical_skill_id": "skill:supply_chain_management", "canonical_label": "Supply Chain Management"},
        {"onetsoc_code": "11-2021.00", "canonical_skill_id": "skill:procurement_basics", "canonical_label": "Procurement Basics"},
        {"onetsoc_code": "11-2021.00", "canonical_skill_id": "skill:vendor_management", "canonical_label": "Vendor Management"},
        {"onetsoc_code": "11-2021.00", "canonical_skill_id": "skill:electronic_data_interchange", "canonical_label": "Electronic Data Interchange"},
        {"onetsoc_code": "11-2021.00", "canonical_skill_id": "skill:process_mapping", "canonical_label": "Process Mapping"},
    ]

    refined = refine_occupation_signature_rows(rows)

    assert "skill:supply_chain_management" not in _skill_ids(refined)


def test_domain_refinement_keeps_supply_chain_management_with_warehouse_and_vendor_anchors():
    rows = [
        {"onetsoc_code": "13-1081.00", "canonical_skill_id": "skill:supply_chain_management", "canonical_label": "Supply Chain Management"},
        {"onetsoc_code": "13-1081.00", "canonical_skill_id": "skill:procurement_basics", "canonical_label": "Procurement Basics"},
        {"onetsoc_code": "13-1081.00", "canonical_skill_id": "skill:vendor_management", "canonical_label": "Vendor Management"},
        {"onetsoc_code": "13-1081.00", "canonical_skill_id": "skill:warehouse_operations", "canonical_label": "Warehouse Operations"},
        {"onetsoc_code": "13-1081.00", "canonical_skill_id": "skill:electronic_data_interchange", "canonical_label": "Electronic Data Interchange"},
    ]

    refined = refine_occupation_signature_rows(rows)

    assert "skill:supply_chain_management" in _skill_ids(refined)


def test_domain_refinement_removes_project_management_without_required_version_control_or_ops_anchor():
    rows = [
        {"onetsoc_code": "11-2021.00", "canonical_skill_id": "skill:project_management", "canonical_label": "Project Management"},
        {"onetsoc_code": "11-2021.00", "canonical_skill_id": "skill:backend_development", "canonical_label": "Backend Development"},
        {"onetsoc_code": "11-2021.00", "canonical_skill_id": "skill:web_service_api", "canonical_label": "Web Service API"},
        {"onetsoc_code": "11-2021.00", "canonical_skill_id": "skill:linux_administration", "canonical_label": "Linux Administration"},
    ]

    refined = refine_occupation_signature_rows(rows)

    assert "skill:project_management" not in _skill_ids(refined)


def test_domain_refinement_is_deterministic_and_exposes_domain_decisions():
    rows = [
        {"onetsoc_code": "15-1299.09", "canonical_skill_id": "skill:project_management", "canonical_label": "Project Management"},
        {"onetsoc_code": "15-1299.09", "canonical_skill_id": "skill:backend_development", "canonical_label": "Backend Development"},
        {"onetsoc_code": "15-1299.09", "canonical_skill_id": "skill:web_service_api", "canonical_label": "Web Service API"},
        {"onetsoc_code": "15-1299.09", "canonical_skill_id": "skill:version_control", "canonical_label": "Version Control"},
    ]

    refiner = OccupationSignatureRoleContextRefiner()
    first_rows, first_decisions = refiner.filter_rows(rows, return_diagnostics=True)
    second_rows, second_decisions = refiner.filter_rows(rows, return_diagnostics=True)

    assert first_rows == second_rows
    assert first_decisions == second_decisions
    assert "skill:project_management" in _skill_ids(first_rows)
    domain_decision = next(
        decision
        for decision in first_decisions
        if decision.canonical_skill_id == "skill:project_management" and decision.phase == "domain"
    )
    assert domain_decision.retained is True
    assert "software_delivery_core" in set(domain_decision.matched_group_labels)
