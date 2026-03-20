from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.extraction.task_phrase_mapping import detect_task_phrase_matches


def test_task_phrase_mapping_matches_finance_and_hr_phrases():
    matches = detect_task_phrase_matches(
        section_lines=[
            ("traitement des factures et rapprochement avec commandes et receptions", "experience"),
            ("administration du personnel et parcours d onboarding", "skills"),
        ],
        mapping_inputs=[],
    )

    assert matches["Invoice Processing"].label == "Invoice Processing"
    assert matches["Reconciliation"].label == "Reconciliation"
    assert matches["HR Administration"].label == "HR Administration"
    assert matches["Onboarding"].label == "Onboarding"


def test_task_phrase_mapping_is_deterministic():
    kwargs = {
        "section_lines": [
            ("qualification de leads et preparation de devis", "skills"),
            ("reporting mensuel sur excel", "experience"),
        ],
        "mapping_inputs": ["qualification de leads", "reporting mensuel"],
    }

    a = detect_task_phrase_matches(**kwargs)
    b = detect_task_phrase_matches(**kwargs)

    assert a == b


def test_task_phrase_mapping_matches_logistics_and_procurement_phrases():
    matches = detect_task_phrase_matches(
        section_lines=[
            ("passation de commandes fournisseurs et suivi fournisseurs", "experience"),
            ("gestion des stocks et reporting hebdomadaire sous excel", "skills"),
            ("coordination avec les prestataires et incidents de livraison", "experience"),
        ],
        mapping_inputs=[],
    )

    assert matches["Purchase Order Management"].label == "Purchase Order Management"
    assert matches["Vendor Follow-up"].label == "Vendor Follow-up"
    assert matches["Inventory Management"].label == "Inventory Management"
    assert matches["Reporting"].label == "Reporting"
    assert matches["Logistics Coordination"].label == "Logistics Coordination"
    assert matches["Incident Management"].label == "Incident Management"
