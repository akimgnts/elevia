from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.pipeline.structured_extraction_stage import run_structured_extraction_stage


def test_structured_extraction_respects_flag_off(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_STRUCTURED_EXTRACTION", "0")
    result = run_structured_extraction_stage(cv_text="Suivi des ventes", base_mapping_inputs=["Suivi des ventes"])
    assert result.enabled is False
    assert result.structured_units == []


def test_structured_extraction_reconstructs_action_object_domain_and_tools(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_STRUCTURED_EXTRACTION", "1")
    text = (
        "Experience\n"
        "Suivi des performances commerciales et analyse des ventes mensuelles sous Excel et Salesforce.\n"
    )
    result = run_structured_extraction_stage(cv_text=text, base_mapping_inputs=["communication", "Excel", "Salesforce"])
    assert result.enabled is True
    assert result.structured_units
    unit = result.top_signal_units[0]
    assert unit["action"] in {"monitoring", "analysis"}
    assert unit["domain"] == "sales"
    assert "excel" in {tool.lower() for tool in unit["tools"]}
    assert "salesforce" in {tool.lower() for tool in unit["tools"]}
    assert "communication" not in [item.lower() for item in result.mapping_inputs]
    assert text.strip().splitlines()[-1] not in result.mapping_inputs


def test_structured_extraction_rejects_title_lines_and_tableau_ambiguity(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_STRUCTURED_EXTRACTION", "1")
    text = (
        "Experience\n"
        "Gestionnaire operations transport — Nordex Services\n"
        "Mon role a souvent consiste a gerer des priorites de livraison, securiser des departs et tenir des tableaux de suivi.\n"
        "Excel, TMS interne, Outlook\n"
    )
    result = run_structured_extraction_stage(cv_text=text, base_mapping_inputs=["tableau", "excel", "tms"])
    raw_texts = {unit["raw_text"] for unit in result.structured_units}
    assert "Gestionnaire operations transport — Nordex Services" not in raw_texts
    assert "tableau" not in {item.lower() for item in result.mapping_inputs}
    assert any(unit.get("domain") == "supply_chain" for unit in result.top_signal_units)


def test_structured_extraction_caps_promoted_units_and_rejects_list_like_skills(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_STRUCTURED_EXTRACTION", "1")
    text = (
        "Skills\n"
        "SAP, Excel, approvisionnement, suivi fournisseurs, gestion des stocks, analyse des besoins, coordination production\n"
        "Experience\n"
        "- traitement des factures fournisseurs\n"
        "- suivi des dossiers salaries\n"
        "- analyse des ventes mensuelles\n"
        "- coordination des expeditions logistiques\n"
        "- preparation des devis commerciaux\n"
        "- suivi des budgets mensuels\n"
        "- recrutement de profils junior\n"
    )
    result = run_structured_extraction_stage(cv_text=text, base_mapping_inputs=["excel", "sap"])
    assert result.stats["structured_units_promoted_count"] <= 6
    assert all(
        unit["raw_text"]
        != "SAP, Excel, approvisionnement, suivi fournisseurs, gestion des stocks, analyse des besoins, coordination production"
        for unit in result.structured_units
    )
