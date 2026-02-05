import sqlite3

from matching.matching_v1 import MatchingEngine
from matching.extractors import extract_profile


def test_matching_with_explicit_skills_intersection():
    profile = {
        "id": "p1",
        "matching_skills": ["sql", "kpi", "reporting"],
        "languages": ["français"],
        "education": "bac+5",
        "preferred_countries": [],
    }
    offer = {
        "id": "o1",
        "is_vie": True,
        "country": "france",
        "title": "Data Analyst",
        "company": "TestCorp",
        "skills": ["sql", "python"],
        "languages": ["français"],
        "education": "bac+3",
    }

    extracted = extract_profile(profile)
    engine = MatchingEngine([offer])
    result = engine.score_offer(extracted, offer)

    assert result.score > 15
    assert result.match_debug["skills"]["matched"] == ["sql"]


def test_profile_skills_empty_fallback_reason():
    profile = {
        "id": "p2",
        "skills": [],
        "languages": ["français"],
        "education": "bac+5",
        "preferred_countries": [],
    }
    offer = {
        "id": "o2",
        "is_vie": True,
        "country": "france",
        "title": "Data Analyst",
        "company": "TestCorp",
        "skills": ["sql"],
        "languages": ["français"],
        "education": "bac+3",
    }

    extracted = extract_profile(profile)
    engine = MatchingEngine([offer])
    result = engine.score_offer(extracted, offer)

    assert result.score == 15
    assert "Aucune compétence détectée en commun" in result.reasons


def test_normalization_not_dropping_all_skills():
    profile = {
        "id": "p3",
        "matching_skills": ["SQL", "Power BI", "API"],
        "languages": ["français"],
        "education": "bac+5",
        "preferred_countries": [],
    }
    extracted = extract_profile(profile)
    assert len(extracted.skills) >= 3
