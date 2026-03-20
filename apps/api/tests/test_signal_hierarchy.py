from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.pipeline.structured_extraction_stage import run_structured_extraction_stage


def test_signal_hierarchy_prioritizes_domain_task_over_tool_only(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_STRUCTURED_EXTRACTION", "1")
    text = (
        "Profil\n"
        "Suivi des performances commerciales et analyse des ventes mensuelles.\n"
        "Outils\n"
        "Excel Salesforce\n"
    )
    result = run_structured_extraction_stage(cv_text=text, base_mapping_inputs=["Excel", "Salesforce", "suivi des performances commerciales"])
    assert result.top_signal_units
    top = result.top_signal_units[0]
    assert top["domain"] == "sales"
    assert "performances commerciales" in (top.get("object") or "")


def test_signal_hierarchy_penalizes_generic_or_fragment_objects(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_STRUCTURED_EXTRACTION", "1")
    text = (
        "Experience\n"
        "suivi des factures fournisseurs\n"
        "Skills\n"
        "Excel, Power BI, reporting, controle de gestion, analyse financiere, budgets, cloture\n"
    )
    result = run_structured_extraction_stage(
        cv_text=text,
        base_mapping_inputs=["Excel", "Power BI", "suivi des factures fournisseurs"],
    )
    top = result.top_signal_units[0]
    assert "factures fournisseurs" in (top.get("object") or "")
    assert top.get("domain") == "finance"
