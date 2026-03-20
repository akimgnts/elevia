from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.pipeline.structured_extraction_stage import run_structured_extraction_stage


def test_mapping_input_control_only_promotes_top_ranked_units(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_STRUCTURED_EXTRACTION", "1")
    text = (
        "Experience\n"
        "- suivi des budgets mensuels\n"
        "- preparation des devis commerciaux\n"
        "- coordination des expeditions logistiques\n"
        "- suivi des dossiers salaries\n"
        "- traitement des factures fournisseurs\n"
        "- gestion des stocks critiques\n"
        "- mise a jour des presentations\n"
        "- francais anglais professionnel\n"
    )
    result = run_structured_extraction_stage(cv_text=text, base_mapping_inputs=[line for line in text.splitlines() if line.strip()])
    assert result.stats["structured_units_promoted_count"] <= 6
    assert all(len(item.split()) <= 4 for item in result.mapping_inputs)
