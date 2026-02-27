import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from matching.matching_v1 import MatchingEngine
from matching.extractors import extract_profile


@pytest.fixture(autouse=True)
def _enable_uri_scoring(monkeypatch):
    monkeypatch.setenv("ELEVIA_SCORE_USE_URIS", "1")


def _make_offer(offer_id: str, skills):
    return {
        "id": offer_id,
        "is_vie": True,
        "country": "france",
        "title": "Data Analyst",
        "company": "TestCorp",
        "skills": skills,
        "languages": ["français"],
        "education": "bac+3",
    }


def test_score_invariant_under_surface_variants():
    profile = {
        "id": "p1",
        "skills": ["excel"],
        "languages": ["français"],
        "education": "bac+3",
    }
    offer_a = _make_offer("o1", ["utiliser un logiciel de tableur"])
    offer_b = _make_offer("o2", ["microsoft office excel"])

    engine = MatchingEngine([offer_a, offer_b])
    extracted = extract_profile(profile)

    score_a = engine.score_offer(extracted, offer_a).score
    score_b = engine.score_offer(extracted, offer_b).score

    assert score_a == score_b


def test_unmapped_never_enters_scoring():
    profile = {
        "id": "p2",
        "skills": ["sql"],
        "languages": ["français"],
        "education": "bac+3",
    }
    offer = _make_offer("o3", ["sql", "zzzznotaskill_12345"])

    engine = MatchingEngine([offer])
    extracted = extract_profile(profile)
    result = engine.score_offer(extracted, offer)

    assert result.breakdown["skills"] >= 0.99
    skills_debug = result.match_debug.get("skills", {}) if result.match_debug else {}
    assert skills_debug.get("missing") == []
