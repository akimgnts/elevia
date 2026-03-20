from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.extraction.object_quality_filter import evaluate_object_quality


def test_object_quality_rejects_generic_and_fragment_objects():
    accepted, score, reasons = evaluate_object_quality("tableaux")
    assert accepted is False
    assert score < 0.58
    assert "single_token" in reasons or "generic_object" in reasons

    accepted, score, reasons = evaluate_object_quality("commandes clients c")
    assert accepted is False
    assert "weak_trailing_fragment" in reasons or "fragment_token" in reasons


def test_object_quality_accepts_concrete_business_objects():
    accepted, score, reasons = evaluate_object_quality("factures fournisseurs")
    assert accepted is True
    assert score >= 0.58
    assert "generic_object" not in reasons

    accepted, score, reasons = evaluate_object_quality("dossiers salaries")
    assert accepted is True
    assert score >= 0.58
