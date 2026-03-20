from compass.roles.occupation_signature_role_context import (
    OccupationSignatureRoleContextRefiner,
    refine_occupation_signature_rows,
)


def _skill_ids(rows):
    return {row["canonical_skill_id"] for row in rows}


def test_phase2_refinement_keeps_scripting_automation_with_software_anchors():
    rows = [
        {"onetsoc_code": "15-1252.00", "canonical_skill_id": "skill:scripting_automation", "canonical_label": "Scripting Automation"},
        {"onetsoc_code": "15-1252.00", "canonical_skill_id": "skill:backend_development", "canonical_label": "Backend Development"},
        {"onetsoc_code": "15-1252.00", "canonical_skill_id": "skill:web_service_api", "canonical_label": "Web Service API"},
    ]

    refined = refine_occupation_signature_rows(rows)

    assert _skill_ids(refined) == {
        "skill:scripting_automation",
        "skill:backend_development",
        "skill:web_service_api",
    }


def test_phase2_refinement_removes_scripting_automation_without_context_anchors():
    rows = [
        {"onetsoc_code": "13-1081.00", "canonical_skill_id": "skill:scripting_automation", "canonical_label": "Scripting Automation"},
        {"onetsoc_code": "13-1081.00", "canonical_skill_id": "skill:supply_chain_management", "canonical_label": "Supply Chain Management"},
        {"onetsoc_code": "13-1081.00", "canonical_skill_id": "skill:procurement_basics", "canonical_label": "Procurement Basics"},
        {"onetsoc_code": "13-1081.00", "canonical_skill_id": "skill:erp_usage", "canonical_label": "ERP Usage"},
        {"onetsoc_code": "13-1081.00", "canonical_skill_id": "skill:vendor_management", "canonical_label": "Vendor Management"},
        {"onetsoc_code": "13-1081.00", "canonical_skill_id": "skill:process_mapping", "canonical_label": "Process Mapping"},
    ]

    refined = refine_occupation_signature_rows(rows)

    assert "skill:scripting_automation" not in _skill_ids(refined)


def test_phase2_refinement_keeps_statistical_programming_with_analytics_anchors():
    rows = [
        {"onetsoc_code": "15-2051.01", "canonical_skill_id": "skill:statistical_programming", "canonical_label": "Statistical Programming"},
        {"onetsoc_code": "15-2051.01", "canonical_skill_id": "skill:data_modeling", "canonical_label": "Data Modeling"},
        {"onetsoc_code": "15-2051.01", "canonical_skill_id": "skill:machine_learning", "canonical_label": "Machine Learning"},
    ]

    refined = refine_occupation_signature_rows(rows)

    assert "skill:statistical_programming" in _skill_ids(refined)


def test_phase2_refinement_keeps_cad_modeling_with_mechanical_design_anchors_and_is_deterministic():
    rows = [
        {"onetsoc_code": "17-2112.00", "canonical_skill_id": "skill:cad_modeling", "canonical_label": "CAD Modeling"},
        {"onetsoc_code": "17-2112.00", "canonical_skill_id": "skill:technical_drawing", "canonical_label": "Technical Drawing"},
        {"onetsoc_code": "17-2112.00", "canonical_skill_id": "skill:mechanical_design", "canonical_label": "Mechanical Design"},
        {"onetsoc_code": "17-2112.00", "canonical_skill_id": "skill:industrial_automation", "canonical_label": "Industrial Automation"},
    ]

    refiner = OccupationSignatureRoleContextRefiner()
    first_rows, first_decisions = refiner.filter_rows(rows, return_diagnostics=True)
    second_rows, second_decisions = refiner.filter_rows(rows, return_diagnostics=True)

    assert first_rows == second_rows
    assert first_decisions == second_decisions
    assert "skill:cad_modeling" in _skill_ids(first_rows)
    cad_decision = next(
        decision
        for decision in first_decisions
        if decision.canonical_skill_id == "skill:cad_modeling" and decision.phase == "phase2"
    )
    assert cad_decision.retained is True
    assert set(cad_decision.matched_anchor_ids) == {
        "skill:industrial_automation",
        "skill:mechanical_design",
        "skill:technical_drawing",
    }
