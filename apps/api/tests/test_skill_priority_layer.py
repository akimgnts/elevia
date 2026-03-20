from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.extraction.skill_priority_layer import run_skill_priority_layer


def _labels(items: list[dict]) -> list[str]:
    return [item.get("label") for item in items]


def test_atomic_survives_abstraction():
    result = run_skill_priority_layer(
        cv_text="Skills: Python Statistical Programming",
        validated_labels=["Python (programmation informatique)"],
        mapping_inputs=["Python", "Statistical Programming"],
    )

    preserved = _labels(result.preserved_explicit_skills)
    summary = _labels(result.profile_summary_skills)

    assert "Python" in preserved
    assert "Statistical Programming" not in preserved
    assert "Python" in summary


def test_power_bi_ocr_alias_survives():
    result = run_skill_priority_layer(
        cv_text="Compétences: Power Bl",
        validated_labels=[],
        mapping_inputs=["Power Bl"],
    )

    preserved = result.preserved_explicit_skills
    assert any(item["label"] == "Power BI" for item in preserved)
    power_bi = next(item for item in preserved if item["label"] == "Power BI")
    assert power_bi["priority_level"] == "P1"
    assert "protected_explicit" in power_bi["matching_use_policy"]


def test_sql_survives_broad_concept():
    result = run_skill_priority_layer(
        cv_text="Skills: SQL Data Analysis",
        validated_labels=["SQL", "analyse de données"],
        mapping_inputs=["SQL", "Data Analysis"],
    )

    preserved = _labels(result.preserved_explicit_skills)
    summary = _labels(result.profile_summary_skills)

    assert "SQL" in preserved
    assert "Data Analysis" in summary
    assert "SQL" in summary


def test_audit_profile_not_crushed_by_tools():
    result = run_skill_priority_layer(
        cv_text="Compétences Audit Contrôle interne Excel",
        validated_labels=["audit interne", "utiliser un logiciel de tableur"],
        mapping_inputs=["Excel", "Audit", "Internal Control"],
    )

    preserved = _labels(result.preserved_explicit_skills)
    summary = _labels(result.profile_summary_skills)

    assert "Excel" in preserved
    assert "Audit" in preserved
    assert "Audit" in summary
    assert "Internal Control" in summary


def test_narrative_fragment_dropped():
    result = run_skill_priority_layer(
        cv_text="Improved 20 indicators of performance across workflows",
        validated_labels=[],
        mapping_inputs=["improved 20 indicators of performance"],
    )

    assert result.dropped_by_priority
    assert result.dropped_by_priority[0]["drop_reason"] == "dropped:narrative_fragment"


def test_matching_use_policy_assignment():
    result = run_skill_priority_layer(
        cv_text="Python Compliance Communication",
        validated_labels=["Python (programmation informatique)", "compliance", "communication"],
        mapping_inputs=["Python", "Compliance", "Communication"],
    )

    preserved = {item["label"]: item for item in result.preserved_explicit_skills}
    summary = {item["label"]: item for item in result.profile_summary_skills}

    assert preserved["Python"]["matching_use_policy"] == ["protected_explicit", "matching_core_candidate"]
    assert preserved["Compliance"]["matching_use_policy"] == ["protected_explicit", "representation_primary"]
    assert "Communication" not in summary or summary["Communication"]["matching_use_policy"] == ["display_only"]


def test_skill_priority_layer_is_deterministic():
    kwargs = {
        "cv_text": "Skills: Python SQL Power BI Audit Internal Control",
        "validated_labels": ["Python (programmation informatique)", "SQL", "audit interne"],
        "mapping_inputs": ["Python", "SQL", "Power BI", "Audit", "Internal Control"],
    }

    a = run_skill_priority_layer(**kwargs)
    b = run_skill_priority_layer(**kwargs)

    assert a == b


def test_v11_observed_stack_expansions_are_preserved_and_canonicalized():
    result = run_skill_priority_layer(
        cv_text="DevOps JavaScript Scala NLP Flask OpenCV Databricks Looker Studio",
        validated_labels=["DevOps", "JavaScript", "Scala", "PostgreSQL"],
        mapping_inputs=["DevOps", "JavaScript", "Scala", "NLP", "Flask", "OpenCV", "Databricks", "Looker Studio"],
    )

    preserved = {item["label"]: item for item in result.preserved_explicit_skills}
    assert preserved["DevOps"]["canonical_target"]["canonical_id"] == "skill:devops"
    assert preserved["JavaScript"]["canonical_target"]["canonical_id"] == "skill:frontend_development"
    assert preserved["Scala"]["canonical_target"]["canonical_id"] == "skill:backend_development"
    assert preserved["Natural Language Processing"]["canonical_target"]["canonical_id"] == "skill:nlp"
    assert preserved["Flask"]["canonical_target"]["canonical_id"] == "skill:backend_development"
    assert preserved["OpenCV"]["canonical_target"]["canonical_id"] == "skill:machine_learning"
    assert preserved["Databricks"]["canonical_target"]["canonical_id"] == "skill:data_engineering"
    assert preserved["Looker Studio"]["canonical_target"]["canonical_id"] == "skill:looker_studio"


def test_v11_domain_overlay_skills_get_canonical_targets():
    result = run_skill_priority_layer(
        cv_text="Audit internal control compliance legal counsel",
        validated_labels=["audit interne", "conformité"],
        mapping_inputs=["Audit", "Internal Control", "Compliance", "Legal Counsel"],
    )

    preserved = {item["label"]: item for item in result.preserved_explicit_skills}
    assert preserved["Audit"]["canonical_target"]["canonical_id"] == "skill:audit"
    assert preserved["Internal Control"]["canonical_target"]["canonical_id"] == "skill:internal_control"
    assert preserved["Compliance"]["canonical_target"]["canonical_id"] == "skill:compliance"
    assert preserved["Legal Analysis"]["canonical_target"]["canonical_id"] == "skill:legal_analysis"


def test_v12_non_tech_task_phrases_are_preserved_and_ranked_over_tools():
    result = run_skill_priority_layer(
        cv_text=(
            "Communication interne redaction de newsletters planning editorial Canva PowerPoint "
            "administration du personnel parcours d onboarding"
        ),
        validated_labels=[],
        mapping_inputs=["Canva", "PowerPoint", "communication interne", "administration du personnel"],
    )

    preserved = {item["label"]: item for item in result.preserved_explicit_skills}
    summary = [item["label"] for item in result.profile_summary_skills]

    assert preserved["Canva"]["canonical_target"]["canonical_id"] == "skill:canva"
    assert preserved["PowerPoint"]["canonical_target"]["canonical_id"] == "skill:powerpoint"
    assert preserved["Internal Communication"]["canonical_target"]["canonical_id"] == "skill:internal_communication"
    assert preserved["Newsletter Production"]["canonical_target"]["canonical_id"] == "skill:newsletter_production"
    assert preserved["HR Administration"]["canonical_target"]["canonical_id"] == "skill:hr_administration"
    assert preserved["Onboarding"]["canonical_target"]["canonical_id"] == "skill:onboarding"
    assert summary.index("Internal Communication") < summary.index("Canva")
    assert summary.index("HR Administration") < summary.index("PowerPoint")


def test_v12_finance_phrase_mapping_recovers_operational_accounting_skills():
    result = run_skill_priority_layer(
        cv_text=(
            "Comptabilite fournisseurs traitement des factures rapprochement avec commandes "
            "et receptions suivi des litiges preparation des paiements hebdomadaires SAP Excel"
        ),
        validated_labels=[],
        mapping_inputs=["SAP", "Excel", "traitement des factures", "rapprochement"],
    )

    preserved = {item["label"]: item for item in result.preserved_explicit_skills}
    assert preserved["Accounts Payable"]["canonical_target"]["canonical_id"] == "skill:accounts_payable"
    assert preserved["Invoice Processing"]["canonical_target"]["canonical_id"] == "skill:accounts_payable"
    assert preserved["Reconciliation"]["canonical_target"]["canonical_id"] == "skill:reconciliation"
    assert preserved["Dispute Handling"]["canonical_target"]["canonical_id"] == "skill:dispute_handling"
    assert preserved["Payment Scheduling"]["canonical_target"]["canonical_id"] == "skill:payment_scheduling"


def test_v13_logistics_procurement_phrases_are_preserved_and_ranked_over_tools():
    result = run_skill_priority_layer(
        cv_text=(
            "SAP Excel passation de commandes fournisseurs suivi fournisseurs "
            "gestion des stocks coordination avec les prestataires incidents de livraison"
        ),
        validated_labels=[],
        mapping_inputs=["SAP", "Excel", "passation de commandes fournisseurs", "suivi fournisseurs", "gestion des stocks"],
    )

    preserved = {item["label"]: item for item in result.preserved_explicit_skills}
    summary = [item["label"] for item in result.profile_summary_skills]

    assert preserved["Purchase Order Management"]["canonical_target"]["canonical_id"] == "skill:procurement_basics"
    assert preserved["Vendor Follow-up"]["canonical_target"]["canonical_id"] == "skill:vendor_management"
    assert preserved["Inventory Management"]["canonical_target"]["canonical_id"] == "skill:supply_chain_management"
    assert preserved["Logistics Coordination"]["canonical_target"]["canonical_id"] == "skill:logistics_coordination"
    assert preserved["Incident Management"]["canonical_target"]["canonical_id"] == "skill:incident_management"
    assert summary.index("Purchase Order Management") < summary.index("SAP")
    assert summary.index("Vendor Follow-up") < summary.index("Excel")


def test_v13_logistics_profile_drops_broad_data_abstraction_without_data_context():
    result = run_skill_priority_layer(
        cv_text="Supply chain approvisionnement fournisseurs stocks livraisons SAP Excel",
        validated_labels=["analyse de données", "achat"],
        mapping_inputs=["SAP", "Excel", "Data Analysis", "Supply Chain Management", "Procurement"],
    )

    preserved = [item["label"] for item in result.preserved_explicit_skills]
    assert "Data Analysis" not in preserved
    assert any(
        item.get("drop_reason") == "dropped:semantic_guard:logistics_without_data_context"
        for item in result.dropped_by_priority
    )


def test_final_exact_tools_and_email_marketing_are_preserved_without_overranking_language():
    result = run_skill_priority_layer(
        cv_text="Anglais courant campagnes email Looker Studio Salesforce Excel Power BI SAP",
        validated_labels=["anglais courant", "emailing"],
        mapping_inputs=["English", "Email Marketing", "Looker Studio", "Salesforce", "Excel", "Power BI", "SAP"],
    )

    preserved = {item["label"]: item for item in result.preserved_explicit_skills}
    summary = [item["label"] for item in result.profile_summary_skills]

    assert preserved["English"]["canonical_target"]["canonical_id"] == "skill:english_language"
    assert preserved["Email Marketing"]["canonical_target"]["canonical_id"] == "skill:email_marketing"
    assert preserved["Excel"]["canonical_target"]["canonical_id"] == "skill:excel"
    assert preserved["Power BI"]["canonical_target"]["canonical_id"] == "skill:power_bi"
    assert preserved["Salesforce"]["canonical_target"]["canonical_id"] == "skill:salesforce"
    assert preserved["SAP"]["canonical_target"]["canonical_id"] == "skill:sap"
    assert preserved["Looker Studio"]["canonical_target"]["canonical_id"] == "skill:looker_studio"
    assert "English" not in summary
