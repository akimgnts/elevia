"""
test_tight_candidate_prioritization.py — verify narrative penalty and subchunk bonus.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.extraction.tight_skill_extractor import extract_tight_skills


def test_narrative_penalty_applied():
    text = "des donn es multi-sources pour API REST JSON Power BI"
    result = extract_tight_skills(text, cluster="DATA_IT")
    trace = result.metrics.get("selection_trace") or []
    penalties = [t for t in trace if "narrative_fragment_penalty" in (t.get("adjustments") or [])]
    assert penalties, "Expected at least one narrative penalty in selection trace."


def test_generated_subchunk_bonus_present():
    text = "API REST JSON Power BI"
    result = extract_tight_skills(text, cluster="DATA_IT")
    trace = result.metrics.get("selection_trace") or []
    generated = [t for t in trace if t.get("origin") == "generated_subchunk"]
    if generated:
        assert any(
            "technical_subchunk_bonus" in (t.get("adjustments") or [])
            for t in generated
        ), "generated subchunks should receive technical_subchunk_bonus"


def test_deterministic_order():
    text = "API REST JSON Power BI"
    r1 = extract_tight_skills(text, cluster="DATA_IT")
    r2 = extract_tight_skills(text, cluster="DATA_IT")
    assert r1.skill_candidates == r2.skill_candidates
    assert r1.metrics == r2.metrics
