"""
test_cv_structure_filter.py — minimal CV structure filter.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.extraction.tight_skill_extractor import extract_tight_skills


def test_cv_headings_removed():
    text = "Experience Education Skills Languages Contact Projects"
    result = extract_tight_skills(text, cluster="DATA_IT")
    candidates = [c.lower() for c in result.skill_candidates]
    for heading in ("experience", "education", "skills", "languages", "contact", "projects"):
        assert heading not in candidates


def test_skill_terms_preserved():
    text = "Python SQL Power BI"
    result = extract_tight_skills(text, cluster="DATA_IT")
    candidates = [c.lower() for c in result.skill_candidates]
    assert "python" in candidates
    assert "sql" in candidates
