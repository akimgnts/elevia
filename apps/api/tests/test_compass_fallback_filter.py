"""
test_compass_fallback_filter.py — reject non-skill tokens from Compass fallback.
"""
from compass.cluster_library import is_skill_candidate


def test_compass_rejects_generic_tokens():
    for token in ["france", "contact", "school", "services", "technologies", "akim"]:
        assert is_skill_candidate(token) is False


def test_compass_accepts_skill_tokens():
    for token in ["python", "api", "etl", "kpi", "dashboard", "reporting", "analytics"]:
        assert is_skill_candidate(token) is True
