"""
test_tight_generation_guardrails.py — guardrails against composite over-generation.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.extraction.tight_skill_extractor import extract_tight_skills


def test_rejects_composite_bi_sql_data():
    text = "BI SQL Data"
    result = extract_tight_skills(text, cluster="DATA_IT")
    candidates = [c.lower() for c in result.skill_candidates]
    assert "bi sql data" not in candidates


def test_rejects_composite_dataiku_chain():
    text = "Dataiku Core Designer Dataiku"
    result = extract_tight_skills(text, cluster="DATA_IT")
    candidates = [c.lower() for c in result.skill_candidates]
    assert "dataiku core designer dataiku" not in candidates


def test_keeps_power_bi_api_rest():
    text = "API REST JSON Power BI"
    result = extract_tight_skills(text, cluster="DATA_IT")
    candidates = [c.lower() for c in result.skill_candidates]
    assert "power bi" in candidates
    assert "api rest" in candidates


def test_deterministic():
    text = "API REST JSON Power BI"
    r1 = extract_tight_skills(text, cluster="DATA_IT")
    r2 = extract_tight_skills(text, cluster="DATA_IT")
    assert r1.skill_candidates == r2.skill_candidates
