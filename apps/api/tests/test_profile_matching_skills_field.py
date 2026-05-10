"""Test that profile.matching_skills field is populated correctly.

Ensures that /profile/parse-file response includes matching_skills field,
which is required by the frontend buildMatchingProfile function.
"""

import pytest
from pathlib import Path
from profile.baseline_parser import run_baseline_from_tokens


def test_baseline_parser_includes_matching_skills():
    """Verify run_baseline_from_tokens returns matching_skills in profile dict."""
    tokens = ["Python", "SQL", "Data Analysis", "Communication"]
    result = run_baseline_from_tokens(tokens)

    # Profile dict should have matching_skills field
    assert "profile" in result
    profile = result["profile"]

    # matching_skills should be populated (same as skills)
    assert "matching_skills" in profile
    assert isinstance(profile["matching_skills"], list)
    # Should have some skills
    assert len(profile["matching_skills"]) > 0


def test_baseline_parser_matching_skills_matches_canonical():
    """Verify matching_skills equals canonical skills from baseline."""
    tokens = ["Agile", "Project Management", "Excel"]
    result = run_baseline_from_tokens(tokens)

    profile = result["profile"]
    canonical = profile.get("skills", [])
    matching = profile.get("matching_skills", [])

    # matching_skills should match canonical skills
    assert set(matching) == set(canonical)


def test_baseline_parser_empty_tokens_has_empty_matching_skills():
    """Verify matching_skills is empty when no valid tokens provided."""
    result = run_baseline_from_tokens([])
    profile = result["profile"]

    # matching_skills should be empty list
    assert profile.get("matching_skills") == []


def test_canonical_fixture_parsing():
    """Test with actual CV fixture to verify matching_skills population."""
    fixture_path = Path(__file__).parent / "fixtures" / "cv_dev_team_member.txt"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}")

    cv_text = fixture_path.read_text(encoding="utf-8")

    from profile.baseline_parser import run_baseline
    result = run_baseline(cv_text)
    profile = result["profile"]

    # Profile should have matching_skills field
    assert "matching_skills" in profile
    assert isinstance(profile["matching_skills"], list)
    assert len(profile["matching_skills"]) > 0

    # Should match the canonical skills
    assert profile["matching_skills"] == profile.get("skills", [])


if __name__ == "__main__":
    test_baseline_parser_includes_matching_skills()
    test_baseline_parser_matching_skills_matches_canonical()
    test_baseline_parser_empty_tokens_has_empty_matching_skills()
    print("✓ All profile matching_skills tests passed")
