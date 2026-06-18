from __future__ import annotations

from api.utils.offer_skills_uri_resolver import (
    resolve_label_to_canonical_id,
    resolve_canonical_id_to_uris,
    resolve_offer_skill_rows_to_uris,
)


def test_resolve_label_to_canonical_id_handles_known_variants():
    assert resolve_label_to_canonical_id("PowerBI") == "skill:power_bi"
    assert resolve_label_to_canonical_id("Microsoft Power BI") == "skill:power_bi"
    assert resolve_label_to_canonical_id("BI reporting") == "skill:business_intelligence"
    assert resolve_label_to_canonical_id("Microsoft Excel") == "skill:excel"
    assert resolve_label_to_canonical_id("Technical Sales") == "skill:b2b_sales"
    assert resolve_label_to_canonical_id("Contract Management") == "skill:vendor_management"
    assert resolve_label_to_canonical_id("Data Management") == "skill:data_governance"
    assert resolve_label_to_canonical_id("Amélioration des processus") == "skill:process_optimization"
    assert resolve_label_to_canonical_id("Political Analysis") == "skill:public_affairs_analysis"
    assert resolve_label_to_canonical_id("Event Organization") == "skill:event_coordination"
    assert resolve_label_to_canonical_id("Public Relations") == "skill:public_relations"
    assert resolve_label_to_canonical_id("Website Management") == "skill:website_management"
    assert resolve_label_to_canonical_id("HPLC") == "skill:hplc"
    assert resolve_label_to_canonical_id("UPLC") == "skill:uplc"
    assert resolve_label_to_canonical_id("GLP") == "skill:glp"
    assert resolve_label_to_canonical_id("GMP") == "skill:gmp"
    assert resolve_label_to_canonical_id("Validation of Computerized Systems") == "skill:computerized_systems_validation"
    assert resolve_label_to_canonical_id("supplier performance") == "skill:vendor_management"
    assert resolve_label_to_canonical_id("documentation management") == "skill:process_documentation"
    assert resolve_label_to_canonical_id("quality assurance") == "skill:quality_engineering"
    assert resolve_label_to_canonical_id("contract negotiation") == "skill:negotiation"
    assert resolve_label_to_canonical_id("quality audits") == "skill:audit"


def test_resolve_canonical_id_to_uris_uses_deterministic_exact_esco_candidates():
    sap_uris = resolve_canonical_id_to_uris("skill:sap", raw_label="SAP")
    process_uris = resolve_canonical_id_to_uris(
        "skill:process_optimization",
        raw_label="Process Optimization",
    )
    market_uris = resolve_canonical_id_to_uris(
        "skill:market_analysis",
        raw_label="Market Analysis",
    )
    vendor_uris = resolve_canonical_id_to_uris(
        "skill:vendor_management",
        raw_label="Contract Management",
    )
    governance_uris = resolve_canonical_id_to_uris(
        "skill:data_governance",
        raw_label="Data Management",
    )
    sales_uris = resolve_canonical_id_to_uris(
        "skill:b2b_sales",
        raw_label="Technical Sales",
    )
    affairs_uris = resolve_canonical_id_to_uris(
        "skill:public_affairs_analysis",
        raw_label="Political Analysis",
    )
    event_uris = resolve_canonical_id_to_uris(
        "skill:event_coordination",
        raw_label="Event Organization",
    )
    pr_uris = resolve_canonical_id_to_uris(
        "skill:public_relations",
        raw_label="Public Relations",
    )
    website_uris = resolve_canonical_id_to_uris(
        "skill:website_management",
        raw_label="Website Management",
    )
    hplc_uris = resolve_canonical_id_to_uris(
        "skill:hplc",
        raw_label="HPLC",
    )
    uplc_uris = resolve_canonical_id_to_uris(
        "skill:uplc",
        raw_label="UPLC",
    )
    glp_uris = resolve_canonical_id_to_uris(
        "skill:glp",
        raw_label="GLP",
    )
    gmp_uris = resolve_canonical_id_to_uris(
        "skill:gmp",
        raw_label="GMP",
    )
    csv_uris = resolve_canonical_id_to_uris(
        "skill:computerized_systems_validation",
        raw_label="Validation of Computerized Systems",
    )
    supplier_uris = resolve_canonical_id_to_uris(
        "skill:vendor_management",
        raw_label="supplier performance",
    )
    doc_mgmt_uris = resolve_canonical_id_to_uris(
        "skill:process_documentation",
        raw_label="documentation management",
    )
    qa_uris = resolve_canonical_id_to_uris(
        "skill:quality_engineering",
        raw_label="quality assurance",
    )
    negotiation_uris = resolve_canonical_id_to_uris(
        "skill:negotiation",
        raw_label="contract negotiation",
    )
    audit_uris = resolve_canonical_id_to_uris(
        "skill:audit",
        raw_label="quality audits",
    )

    assert "http://data.europa.eu/esco/skill/f0393af3-bcd9-41af-a36e-0cfb83b60081" in sap_uris
    assert "http://data.europa.eu/esco/skill/940a70fa-7c58-423b-8d03-34920b59f0f7" in process_uris
    assert "http://data.europa.eu/esco/skill/b011c8b4-76e1-4bbc-8bb9-1d205e7b618a" in market_uris
    assert "http://data.europa.eu/esco/skill/fe1ec582-d63b-466c-9149-e7fc4fe93e22" in vendor_uris
    assert "http://data.europa.eu/esco/skill/1973c966-f236-40c9-b2d4-5d71a89019be" in governance_uris
    assert "http://data.europa.eu/esco/skill/0c0488b3-fca5-4deb-865b-8dc605c3d909" in sales_uris
    assert "http://data.europa.eu/esco/skill/c5449667-9b40-4114-8d74-f51177669984" in affairs_uris
    assert "http://data.europa.eu/esco/skill/2111dff8-f830-46ad-80ce-7885893b3134" in event_uris
    assert "http://data.europa.eu/esco/skill/5330b70e-16f5-43a7-a6de-18fd6a4bd063" in pr_uris
    assert "http://data.europa.eu/esco/skill/d04ee340-5378-4601-8181-19da6d5cbfe0" in website_uris
    assert "http://data.europa.eu/esco/skill/56d88178-99d4-400d-9415-d700ce6a29f3" in hplc_uris
    assert uplc_uris == []
    assert "http://data.europa.eu/esco/skill/1618ee1c-6753-456e-a171-3d7e5f75404a" in glp_uris
    assert "http://data.europa.eu/esco/skill/13f22eb5-e3a8-405a-9d89-c8124d4a239a" in gmp_uris
    assert csv_uris == []
    assert "http://data.europa.eu/esco/skill/fe1ec582-d63b-466c-9149-e7fc4fe93e22" in supplier_uris
    assert "http://data.europa.eu/esco/skill/580660a6-5d3a-421d-a54f-d85b706c2b2f" in doc_mgmt_uris
    assert "http://data.europa.eu/esco/skill/1973c966-f236-40c9-b2d4-5d71a89019be" in qa_uris
    assert "http://data.europa.eu/esco/skill/5f2efbdf-08a2-49cd-9c06-bd284e4f0fbf" in negotiation_uris
    assert "http://data.europa.eu/esco/skill/5b8a3dd2-de10-48a0-8ce5-522f1fff8450" in audit_uris


def test_resolve_offer_skill_rows_to_uris_merges_precomputed_overlay_and_tracks_unresolved():
    result = resolve_offer_skill_rows_to_uris(
        [
            {"label": "Power BI", "canonical_id": ""},
            {"label": "SAP", "canonical_id": "skill:sap"},
            {"label": "Unknown Skill XYZ", "canonical_id": ""},
        ]
    )

    assert "skill:power_bi" in result["resolved_canonical_ids"]
    assert "skill:sap" in result["resolved_canonical_ids"]
    assert "Unknown Skill XYZ" in result["unresolved_labels"]
    assert "http://data.europa.eu/esco/skill/f0393af3-bcd9-41af-a36e-0cfb83b60081" in result["skills_uri"]
    assert any(uri.startswith("http://data.europa.eu/esco/skill/") for uri in result["skills_uri"])
