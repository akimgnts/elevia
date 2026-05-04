"""Test inbox sorting stability — same request = same order."""

from api.schemas.inbox import InboxItem


def test_inbox_sorting_deterministic():
    """Test that sorting items with tie-break yields deterministic order."""
    items = [
        InboxItem(
            offer_id="offer-3",
            title="Offer 3",
            score=90,
            reasons=[],
        ),
        InboxItem(
            offer_id="offer-1",
            title="Offer 1",
            score=80,
            reasons=[],
        ),
        InboxItem(
            offer_id="offer-5",
            title="Offer 5",
            score=60,
            reasons=[],
        ),
        InboxItem(
            offer_id="offer-2",
            title="Offer 2",
            score=60,
            reasons=[],
        ),
        InboxItem(
            offer_id="offer-4",
            title="Offer 4",
            score=40,
            reasons=[],
        ),
    ]

    def sort_items(item_list):
        """Mimic backend sort logic."""
        return sorted(
            item_list,
            key=lambda i: (
                -i.score,
                -(i.signal_score or 0.0),
                i.offer_id,
            ),
        )

    # Sort twice, should be identical
    sorted_1 = sort_items(items)
    sorted_2 = sort_items(items)

    order_1 = [item.offer_id for item in sorted_1]
    order_2 = [item.offer_id for item in sorted_2]

    assert order_1 == order_2, f"Order changed: {order_1} vs {order_2}"
    assert order_1 == ["offer-3", "offer-1", "offer-5", "offer-2", "offer-4"]
    print("✓ Sorting deterministic")


def test_limit_applied_after_sorting():
    """Test that limit is applied AFTER sorting, not before."""
    items = [
        InboxItem(offer_id=f"offer-{i}", title=f"Offer {i}", score=90 - i * 5, reasons=[])
        for i in range(1, 11)  # 10 items
    ]

    def sort_and_limit(item_list, limit=3):
        sorted_list = sorted(
            item_list,
            key=lambda i: (
                -i.score,
                -(i.signal_score or 0.0),
                i.offer_id,
            ),
        )
        return sorted_list[:limit]

    result = sort_and_limit(items, limit=3)
    assert len(result) == 3
    assert result[0].offer_id == "offer-1"  # score 90
    assert result[1].offer_id == "offer-2"  # score 85
    assert result[2].offer_id == "offer-3"  # score 80
    print("✓ Limit applied after sort correctly")


def test_tiebreak_with_same_scores():
    """Test that tie-break by offer_id is lexicographic and stable."""
    items = [
        InboxItem(offer_id="z-offer", title="Z", score=80, reasons=[]),
        InboxItem(offer_id="a-offer", title="A", score=80, reasons=[]),
        InboxItem(offer_id="m-offer", title="M", score=80, reasons=[]),
    ]

    def sort_items(item_list):
        return sorted(
            item_list,
            key=lambda i: (
                -i.score,
                -(i.signal_score or 0.0),
                i.offer_id,  # tie-break
            ),
        )

    sorted_list = sort_items(items)
    order = [item.offer_id for item in sorted_list]

    # Lexicographic order of offer_ids
    assert order == ["a-offer", "m-offer", "z-offer"], f"Got {order}"
    print("✓ Tie-break lexicographic order correct")
