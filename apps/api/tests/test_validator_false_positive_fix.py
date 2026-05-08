"""
test_validator_false_positive_fix.py — Test that validator doesn't reject normal business text.

Ensures the fix for false positive matching "mar" in "marketing" as "March".
"""
import pytest


def test_marketing_word_not_matched():
    """Marketing word should not be flagged as date pattern."""
    from compass.profile.structured_cv_validator import _looks_like_job_title

    text = "Worked with business, marketing, and operational teams to translate needs."
    assert not _looks_like_job_title(text), "Should not match 'mar' in 'marketing'"


def test_management_word_not_matched():
    """Management word should not be flagged."""
    from compass.profile.structured_cv_validator import _looks_like_job_title

    text = "Led cross-functional teams in market management and strategy development."
    assert not _looks_like_job_title(text), "Should not match 'mar' in 'market'"


def test_march_with_year_is_matched():
    """March with year should be flagged (actual job title pattern)."""
    from compass.profile.structured_cv_validator import _looks_like_job_title

    text = "Data Analyst — March 2022, ABC Corp"
    assert _looks_like_job_title(text), "Should match 'March 2022' pattern"


def test_janvier_with_year_is_matched():
    """French janvier with year should be flagged."""
    from compass.profile.structured_cv_validator import _looks_like_job_title

    text = "Business Developer, Janvier 2021"
    assert _looks_like_job_title(text), "Should match 'Janvier 2021' pattern"


def test_feb_with_year_is_matched():
    """Feb with year should be flagged."""
    from compass.profile.structured_cv_validator import _looks_like_job_title

    text = "Project Manager – Feb 2020"
    assert _looks_like_job_title(text), "Should match 'Feb 2020' pattern"


def test_normal_business_responsibility_passes():
    """Normal responsibility text should pass."""
    from compass.profile.structured_cv_validator import _looks_like_job_title

    texts = [
        "Worked with business, marketing, and operational teams to translate business needs.",
        "Market analysis and strategic reporting on quarterly performance.",
        "Commercial marketing strategy and brand positioning.",
        "Management of cross-functional teams across regions.",
        "Support for marketplace operations and vendor relationships.",
    ]

    for text in texts:
        assert not _looks_like_job_title(text), f"Should not flag: {text}"


def test_suspicious_patterns_still_rejected():
    """Actual job title patterns should still be rejected."""
    from compass.profile.structured_cv_validator import _looks_like_job_title

    suspicious = [
        "Data Engineer — Acme — 2022-2023",
        "Consultant, March 2021",
        "Senior Manager, May 2020, TechCorp",
        "Developer – January 2023",
    ]

    for text in suspicious:
        assert _looks_like_job_title(text), f"Should flag suspicious: {text}"


def test_multiple_dashes_still_rejected():
    """Multiple dashes still indicate job title patterns."""
    from compass.profile.structured_cv_validator import _looks_like_job_title

    text = "Data Engineer — TechCorp — 2022-2023"
    assert _looks_like_job_title(text), "Should flag multiple dashes"


def test_dash_with_year_still_rejected():
    """Dash with year still indicates job title."""
    from compass.profile.structured_cv_validator import _looks_like_job_title

    text = "DevOps Engineer – 2023"
    assert _looks_like_job_title(text), "Should flag dash + year"
