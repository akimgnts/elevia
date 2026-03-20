from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.pipeline.structured_extraction_stage import _detect_actions, _load_verb_lexicon


def test_verb_mapping_detects_analysis_and_monitoring_categories():
    lexicon = _load_verb_lexicon()
    actions = _detect_actions("Suivi des performances commerciales et analyse des ventes mensuelles", lexicon)
    categories = [item["category"] for item in actions]
    verbs = [item["verb"] for item in actions]

    assert "monitoring" in categories
    assert "analysis" in categories
    assert "suivi" in verbs
    assert "analyse" in verbs


def test_verb_mapping_keeps_weak_contextual_verbs_distinct():
    lexicon = _load_verb_lexicon()
    actions = _detect_actions("gestion des factures et mise a jour des dossiers", lexicon)
    categories = [item["category"] for item in actions]

    assert "management" in categories
    assert "maintenance" in categories
