from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.pipeline.structured_extraction_stage import run_structured_extraction_stage


def test_signal_ranking_prefers_short_domain_clear_objects(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_STRUCTURED_EXTRACTION", "1")
    text = (
        "Experience\n"
        "- extraction de donnees ERP et mise en forme Power BI\n"
        "- suivi des budgets mensuels\n"
    )
    result = run_structured_extraction_stage(
        cv_text=text,
        base_mapping_inputs=["Power BI", "budgets mensuels"],
    )
    assert result.top_signal_units
    top = result.top_signal_units[0]
    assert top["object"] == "budgets mensuels"
