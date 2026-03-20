from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.extraction.domain_rules import infer_domain


def test_domain_inference_detects_sales_from_object_keywords():
    domain, weight, hits = infer_domain("performances commerciales", "analyse des ventes mensuelles")
    assert domain == "sales"
    assert weight > 0
    assert hits


def test_domain_inference_detects_hr_from_recruitment_language():
    domain, _, hits = infer_domain("dossiers salaries", "suivi des dossiers salaries")
    assert domain == "hr"
    assert "salaries" in ''.join(hits)


def test_domain_inference_does_not_match_substrings_inside_unrelated_words():
    domain, _, hits = infer_domain("appels et taux de transformation", "suivi des appels")
    assert domain != "hr"
    assert "formation" not in "".join(hits)
