"""
test_tight_candidate_canonical_bias.py — OCR penalty + determinism.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.extraction.tight_skill_extractor import extract_tight_skills


def test_ocr_penalty_applied():
    text = "des donn es multi-sources pour"
    result = extract_tight_skills(text, cluster="DATA_IT")
    trace = result.metrics.get("selection_trace") or []
    penalties = [t for t in trace if "ocr_fragment_penalty" in (t.get("adjustments") or [])]
    assert penalties, "expected OCR penalty on broken fragment"


def test_determinism():
    text = "API REST JSON Power BI"
    r1 = extract_tight_skills(text, cluster="DATA_IT")
    r2 = extract_tight_skills(text, cluster="DATA_IT")
    assert r1.skill_candidates == r2.skill_candidates
    assert r1.metrics == r2.metrics
