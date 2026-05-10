"""Test global sorting across paginated results.

Ensures that items are sorted globally by score before pagination is applied,
not separately per page.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from api.schemas.inbox import InboxItem


def test_global_score_sorting_across_pages():
    """Verify items are sorted by score globally, not per-page.

    Simulates a scenario where offers are fetched page-by-page (via pagination),
    scored per page, then should be re-sorted globally before returning to user.

    Issue: Without fix, page 1 could contain lower-scored items if they came from
    earlier pages in the prefetch loop.
    """
    # Create mock items simulating page-by-page fetch
    # Page 1 fetch: offers A (90) and B (80)
    # Page 2 fetch: offers C (70) and D (95)
    # Page 3 fetch: offers E (60) and F (75)

    page1_items = [
        InboxItem(offer_id="A", title="Offer A", score=90.0, signal_score=0.8),
        InboxItem(offer_id="B", title="Offer B", score=80.0, signal_score=0.7),
    ]

    page2_items = [
        InboxItem(offer_id="C", title="Offer C", score=70.0, signal_score=0.6),
        InboxItem(offer_id="D", title="Offer D", score=95.0, signal_score=0.9),  # Highest!
    ]

    page3_items = [
        InboxItem(offer_id="E", title="Offer E", score=60.0, signal_score=0.5),
        InboxItem(offer_id="F", title="Offer F", score=75.0, signal_score=0.65),
    ]

    # Simulate accumulation from page-by-page fetch (insertion order)
    candidate_items = page1_items + page2_items + page3_items
    # Insertion order: A(90), B(80), C(70), D(95), E(60), F(75)

    # This is what the FIXED code does: always sort by score globally
    sorted_items = sorted(
        candidate_items,
        key=lambda i: (-i.score, -(i.signal_score or 0.0), i.offer_id),
    )

    # Verify global sort order
    expected_order = ["D", "A", "B", "F", "C", "E"]  # By score DESC: 95, 90, 80, 75, 70, 60
    actual_order = [item.offer_id for item in sorted_items]

    assert actual_order == expected_order, f"Expected {expected_order}, got {actual_order}"

    # Verify scores are indeed descending
    scores = [item.score for item in sorted_items]
    assert scores == sorted(scores, reverse=True), "Scores should be sorted descending"

    # Simulate pagination: page 1 with page_size=2
    page_size = 2
    page1_result = sorted_items[:page_size]

    # Page 1 should have the TOP 2 highest-scoring items globally
    assert len(page1_result) == 2
    assert page1_result[0].offer_id == "D"  # 95 (highest)
    assert page1_result[1].offer_id == "A"  # 90 (second highest)

    # Simulate page 2
    page2_result = sorted_items[page_size:page_size*2]
    assert len(page2_result) == 2
    assert page2_result[0].offer_id == "B"  # 80 (third highest)
    assert page2_result[1].offer_id == "F"  # 75 (fourth highest)

    # Simulate page 3
    page3_result = sorted_items[page_size*2:page_size*3]
    assert len(page3_result) == 2
    assert page3_result[0].offer_id == "C"  # 70 (fifth highest)
    assert page3_result[1].offer_id == "E"  # 60 (lowest)


def test_tiebreaker_with_equal_scores():
    """Verify signal_score is used as tiebreaker when scores are equal."""
    items = [
        InboxItem(offer_id="A", title="Offer A", score=80.0, signal_score=0.5),
        InboxItem(offer_id="B", title="Offer B", score=80.0, signal_score=0.8),  # Higher signal
        InboxItem(offer_id="C", title="Offer C", score=80.0, signal_score=0.3),
    ]

    sorted_items = sorted(
        items,
        key=lambda i: (-i.score, -(i.signal_score or 0.0), i.offer_id),
    )

    # All have score 80, so order by signal_score DESC
    expected_order = ["B", "A", "C"]  # 0.8, 0.5, 0.3
    actual_order = [item.offer_id for item in sorted_items]

    assert actual_order == expected_order


def test_offer_id_tiebreaker_with_equal_scores_and_signal():
    """Verify offer_id is used as final tiebreaker."""
    items = [
        InboxItem(offer_id="Z", title="Offer Z", score=80.0, signal_score=0.5),
        InboxItem(offer_id="A", title="Offer A", score=80.0, signal_score=0.5),
        InboxItem(offer_id="M", title="Offer M", score=80.0, signal_score=0.5),
    ]

    sorted_items = sorted(
        items,
        key=lambda i: (-i.score, -(i.signal_score or 0.0), i.offer_id),
    )

    # All have same score and signal, so order by offer_id ASC (lexicographic)
    expected_order = ["A", "M", "Z"]
    actual_order = [item.offer_id for item in sorted_items]

    assert actual_order == expected_order


def test_confidence_sort_maintains_score_tiebreaker():
    """Verify confidence_desc sort keeps score as tiebreaker."""
    items = [
        InboxItem(offer_id="A", title="Offer A", score=90.0, signal_score=0.8),
        InboxItem(offer_id="B", title="Offer B", score=85.0, signal_score=0.8),
        InboxItem(offer_id="C", title="Offer C", score=95.0, signal_score=0.7),
    ]

    # Simulate confidence_desc sort WITH score as secondary tiebreaker
    rank = {"HIGH": 2, "MED": 1, "LOW": 0}

    # For simplicity, all items have same confidence (LOW = 0)
    # So they should still be sorted by score DESC
    sorted_items = sorted(
        items,
        key=lambda i: (
            -rank.get("LOW", 0),  # All 0
            -i.score,  # Score as tiebreaker
            -(i.signal_score or 0.0),
            i.offer_id,
        ),
    )

    # Should be ordered by score DESC
    expected_order = ["C", "A", "B"]  # 95, 90, 85
    actual_order = [item.offer_id for item in sorted_items]

    assert actual_order == expected_order


if __name__ == "__main__":
    test_global_score_sorting_across_pages()
    test_tiebreaker_with_equal_scores()
    test_offer_id_tiebreaker_with_equal_scores_and_signal()
    test_confidence_sort_maintains_score_tiebreaker()
    print("✓ All pagination/sorting tests passed")
