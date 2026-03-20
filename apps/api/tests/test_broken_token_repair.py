"""
test_broken_token_repair.py — verify minimal broken token repairs.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.extraction.tight_skill_extractor import extract_tight_skills


def _has_candidate(text: str, target: str) -> bool:
    result = extract_tight_skills(text, cluster="DATA_IT")
    return any(c.lower() == target for c in result.skill_candidates)


def test_repair_donnees():
    assert _has_candidate("donn es", "donnees")


def test_repair_comprehension():
    assert _has_candidate("compr hension", "comprehension")


def test_repair_coherence():
    assert _has_candidate("coh rence", "coherence")
