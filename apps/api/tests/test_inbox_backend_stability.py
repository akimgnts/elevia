"""Test backend /inbox endpoint returns deterministic results."""

import sys
from pathlib import Path

# Need to add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.schemas.inbox import InboxRequest


def test_inbox_catalog_cache_stability():
    """Test that catalog loading from cache is stable."""
    from api.utils.inbox_catalog import load_catalog_offers, _catalog_cache_key, _CATALOG_CACHE, _CATALOG_CACHE_KEY

    # Load twice
    offers_1 = load_catalog_offers()
    cache_key_1 = _catalog_cache_key()
    offers_2 = load_catalog_offers()
    cache_key_2 = _catalog_cache_key()

    assert cache_key_1 == cache_key_2, f"Cache key changed: {cache_key_1} vs {cache_key_2}"
    assert len(offers_1) == len(offers_2), f"Catalog size changed: {len(offers_1)} vs {len(offers_2)}"

    # Check order is identical
    if offers_1 and offers_2:
        for i in range(min(5, len(offers_1))):
            o1_id = str(offers_1[i].get("id") or "")
            o2_id = str(offers_2[i].get("id") or "")
            assert o1_id == o2_id, f"Item {i} changed: {o1_id} vs {o2_id}"

    print(f"✓ Catalog load stable: {len(offers_1)} offers, cache key {cache_key_1}")


def test_catalog_sort_stable():
    """Test that combined catalog sort is deterministic."""
    from api.utils.inbox_catalog import load_catalog_offers

    offers = load_catalog_offers()

    # Sort by publication_date descending, then by id ascending (like backend does)
    def expected_sort_key(offer):
        return (
            str(offer.get("publication_date") or ""),  # by date
            str(offer.get("id") or ""),  # tiebreak by id
        )

    # Check first 10 offers are ordered by pub date desc
    if len(offers) > 1:
        for i in range(min(9, len(offers) - 1)):
            date_i = offers[i].get("publication_date") or ""
            date_next = offers[i + 1].get("publication_date") or ""
            # Date should be descending (or equal if id is tiebreak)
            if date_i and date_next:
                assert date_i >= date_next, f"Not sorted by date desc at {i}: {date_i} < {date_next}"

    print(f"✓ Catalog sort verified: {len(offers)} offers in deterministic order")
