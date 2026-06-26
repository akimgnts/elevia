from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.repositories.offers_pg import OffersPgRepository


class FakeCursor:
    def __init__(self, *, rows=None, row=None):
        self.rows = rows or []
        self.row = row
        self.executed: list[tuple[str, object]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params=None):
        self.executed.append((str(query), params))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def test_fetch_recent_offers_filters_active_and_orders_latest_first():
    cursor = FakeCursor(
        rows=[
            {
                "id": 11,
                "source": "business_france",
                "external_id": "BF-11",
                "title": "Senior Analyst",
                "company": "Acme",
                "location": "Berlin",
                "country": "Germany",
                "contract_type": "VIE",
                "publication_date": "2026-06-21T00:00:00+00:00",
                "start_date": "2026-09-01",
                "url": "https://example.test/offers/11",
                "last_seen_at": "2026-06-25T09:30:00+00:00",
            }
        ]
    )
    repo = OffersPgRepository(lambda: FakeConnection(cursor))

    offers = repo.fetch_recent_offers(limit=5)

    assert offers == cursor.rows
    query, params = cursor.executed[0]
    assert "FROM clean_offers" in query
    assert "WHERE source = %s" in query
    assert "AND is_active = TRUE" in query
    assert "ORDER BY last_seen_at DESC, publication_date DESC, id DESC" in query
    assert "LIMIT %s" in query
    assert params == ("business_france", 5)


def test_fetch_recent_offers_applies_optional_country_filter():
    cursor = FakeCursor(rows=[])
    repo = OffersPgRepository(lambda: FakeConnection(cursor))

    repo.fetch_recent_offers(limit=3, country="Germany")

    query, params = cursor.executed[0]
    assert "AND country = %s" in query
    assert params == ("business_france", "Germany", 3)


def test_fetch_offer_detail_includes_domain_enrichment_when_available():
    cursor = FakeCursor(
        row={
            "id": 42,
            "source": "business_france",
            "external_id": "BF-42",
            "title": "Data Analyst",
            "company": "Acme",
            "country": "Germany",
            "domain": "data",
            "subdomain": "analytics",
            "domain_confidence": 0.91,
            "domain_source": "rules",
        }
    )
    repo = OffersPgRepository(lambda: FakeConnection(cursor))

    offer = repo.fetch_offer_detail(42)

    assert offer == cursor.row
    query, params = cursor.executed[0]
    assert "LEFT JOIN offer_domain_enrichment AS ode" in query
    assert "co.id = %s" in query
    assert params == (42,)


def test_fetch_latest_ingestion_orders_by_started_at_desc():
    cursor = FakeCursor(
        row={
            "id": 7,
            "source": "business_france",
            "status": "success",
            "started_at": "2026-06-25T08:00:00+00:00",
            "finished_at": "2026-06-25T08:03:00+00:00",
        }
    )
    repo = OffersPgRepository(lambda: FakeConnection(cursor))

    row = repo.fetch_latest_ingestion()

    assert row == cursor.row
    query, params = cursor.executed[0]
    assert "FROM ingestion_runs" in query
    assert "WHERE source = %s" in query
    assert "ORDER BY started_at DESC" in query
    assert "LIMIT 1" in query
    assert params == ("business_france",)


def test_fetch_latest_ingestion_timestamp_returns_started_at_value():
    cursor = FakeCursor(row=("2026-06-25T08:00:00+00:00",))
    repo = OffersPgRepository(lambda: FakeConnection(cursor))

    value = repo.fetch_latest_ingestion_timestamp()

    assert value == "2026-06-25T08:00:00+00:00"
    query, params = cursor.executed[0]
    assert "SELECT started_at" in query
    assert params == ("business_france",)
