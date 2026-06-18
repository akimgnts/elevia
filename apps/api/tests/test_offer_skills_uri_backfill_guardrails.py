from __future__ import annotations

import pytest

from api.utils.offer_skills_uri_backfill import (
    assert_non_regression,
    detect_other_bucket_subfamily,
)


def test_detect_other_bucket_subfamily_maps_recurring_patterns():
    assert detect_other_bucket_subfamily(
        title="Product Owner",
        labels=["Agile methodologies", "product backlog management", "Requirements Gathering"],
    ) == "operations"
    assert detect_other_bucket_subfamily(
        title="User Acquisition Specialist",
        labels=["performance marketing", "user acquisition campaigns", "data-driven approach"],
    ) == "marketing"
    assert detect_other_bucket_subfamily(
        title="IT Buyer",
        labels=["supplier relationship management", "procurement", "contract negotiation"],
    ) == "supply"


def test_assert_non_regression_rejects_worse_coverage():
    before = {
        "skills_uri_coverage": 60.16,
        "canonical_skills_coverage": 99.89,
        "other_count": 130,
        "needs_review_count": 143,
    }
    after = {
        "skills_uri_coverage": 59.0,
        "canonical_skills_coverage": 99.89,
        "other_count": 129,
        "needs_review_count": 143,
    }

    with pytest.raises(RuntimeError):
        assert_non_regression(before, after)


def test_assert_non_regression_allows_other_and_needs_review_growth_when_disabled():
    before = {
        "skills_uri_coverage": 60.16,
        "canonical_skills_coverage": 99.89,
        "other_count": 130,
        "needs_review_count": 143,
    }
    after = {
        "skills_uri_coverage": 60.5,
        "canonical_skills_coverage": 99.89,
        "other_count": 132,
        "needs_review_count": 145,
    }

    assert_non_regression(
        before,
        after,
        check_other_bucket=False,
        check_needs_review=False,
    )
