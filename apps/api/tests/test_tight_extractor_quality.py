"""
test_tight_extractor_quality.py — Anti-fragment safeguards for tight extractor.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.extraction.tight_skill_extractor import extract_tight_skills


def test_tight_extractor_rejects_fragments_and_keeps_skills():
    text = (
        "data data data 2024 exp data tools 2023 "
        "python sql postgresql api rest power bi machine learning business intelligence"
    )
    result = extract_tight_skills(text, cluster="DATA_IT")
    candidates = [c.lower() for c in result.skill_candidates]

    for bad in ("data", "data data", "data 2024", "exp data", "tools 2023"):
        assert bad not in candidates, f"Fragment '{bad}' must be rejected. Got: {candidates}"

    for good in (
        "python", "sql", "postgresql", "api", "rest", "power bi",
        "machine learning", "business intelligence",
    ):
        assert good in candidates, f"Skill '{good}' must be preserved. Got: {candidates}"


def test_tight_extractor_deterministic():
    text = "python sql power bi machine learning data 2024"
    r1 = extract_tight_skills(text, cluster="DATA_IT")
    r2 = extract_tight_skills(text, cluster="DATA_IT")
    assert r1.skill_candidates == r2.skill_candidates
    assert r1.metrics == r2.metrics


def test_tight_extractor_empty_safe():
    result = extract_tight_skills("   ", cluster="DATA_IT")
    assert result.skill_candidates == []
    assert result.raw_tokens == []
