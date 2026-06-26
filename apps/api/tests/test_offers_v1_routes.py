from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app


def test_offers_recent_returns_v1_schema_payload(monkeypatch):
    import api.routes.offers_v1 as offers_v1

    class FakeRepository:
        def fetch_recent_offers(self, limit, country=None, source="business_france"):
            assert limit == 20
            assert country is None
            assert source == "business_france"
            return [
                {
                    "id": 42,
                    "source": "business_france",
                    "external_id": "BF-42",
                    "title": "Data Analyst",
                    "company": "Acme",
                    "location": "Berlin",
                    "country": "Germany",
                    "contract_type": "VIE",
                    "publication_date": "2026-06-21T00:00:00+00:00",
                    "start_date": "2026-09-01",
                    "url": "https://example.test/offers/42",
                    "last_seen_at": "2026-06-25T09:30:00+00:00",
                }
            ]

    monkeypatch.setattr(offers_v1, "OffersPgRepository", FakeRepository)

    client = TestClient(app)
    response = client.get("/offers/recent")

    assert response.status_code == 200
    assert response.json() == {
        "offers": [
            {
                "id": 42,
                "source": "business_france",
                "external_id": "BF-42",
                "title": "Data Analyst",
                "company": "Acme",
                "location": "Berlin",
                "country": "Germany",
                "contract_type": "VIE",
                "publication_date": "2026-06-21T00:00:00+00:00",
                "start_date": "2026-09-01",
                "url": "https://example.test/offers/42",
                "last_seen_at": "2026-06-25T09:30:00+00:00",
            }
        ]
    }


def test_offers_recent_is_available_under_api_prefix(monkeypatch):
    import api.routes.offers_v1 as offers_v1

    class FakeRepository:
        def fetch_recent_offers(self, limit, country=None, source="business_france"):
            return [
                {
                    "id": 7,
                    "source": "business_france",
                    "external_id": "BF-7",
                    "title": "Backend Engineer",
                    "last_seen_at": "2026-06-25T09:30:00+00:00",
                }
            ]

    monkeypatch.setattr(offers_v1, "OffersPgRepository", FakeRepository)

    client = TestClient(app)
    response = client.get("/api/offers/recent")

    assert response.status_code == 200
    assert response.json()["offers"][0]["id"] == 7


def test_offers_recent_returns_503_with_stable_payload_when_repo_unavailable(monkeypatch):
    import api.routes.offers_v1 as offers_v1

    class FakeRepository:
        def fetch_recent_offers(self, limit, country=None, source="business_france"):
            raise RuntimeError("DATABASE_URL is not set")

    monkeypatch.setattr(offers_v1, "OffersPgRepository", FakeRepository)

    client = TestClient(app)
    response = client.get("/offers/recent")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "OFFERS_UNAVAILABLE",
            "message": "Offers V1 is temporarily unavailable",
        }
    }


def test_offer_detail_returns_v1_payload_when_offer_exists(monkeypatch):
    import api.routes.offers_v1 as offers_v1

    class FakeRepository:
        def fetch_offer_detail(self, offer_id):
            assert offer_id == 42
            return {
                "id": 42,
                "source": "business_france",
                "external_id": "BF-42",
                "title": "Data Analyst",
                "company": "Acme",
                "payload_json": {},
                "is_active": True,
                "evidence": ["sql"],
            }

    monkeypatch.setattr(offers_v1, "OffersPgRepository", FakeRepository)

    client = TestClient(app)
    response = client.get("/offers/42")

    assert response.status_code == 200
    assert response.json()["id"] == 42
    assert response.json()["external_id"] == "BF-42"
    assert response.json()["evidence"] == ["sql"]


def test_offer_detail_returns_404_when_offer_missing(monkeypatch):
    import api.routes.offers_v1 as offers_v1

    class FakeRepository:
        def fetch_offer_detail(self, offer_id):
            assert offer_id == 999
            return None

    monkeypatch.setattr(offers_v1, "OffersPgRepository", FakeRepository)

    client = TestClient(app)
    response = client.get("/offers/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Offer not found"}


def test_offer_detail_requires_numeric_offer_id(monkeypatch):
    import api.routes.offers_v1 as offers_v1

    monkeypatch.setattr(offers_v1, "OffersPgRepository", object)

    client = TestClient(app)
    response = client.get("/offers/not-a-number")

    assert response.status_code == 422
