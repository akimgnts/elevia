from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app
from api.routes import offers as offers_routes
from api.utils import inbox_catalog


def test_business_france_catalog_uses_postgres_only(monkeypatch):
    monkeypatch.setattr(
        offers_routes,
        "_load_catalog_db_first",
        lambda limit, source: (
            [
                {
                    "id": "BF-123",
                    "source": "business_france",
                    "title": "VIE Analyst",
                    "description": "Real BF offer from clean_offers",
                    "display_description": "Real BF offer from clean_offers",
                    "company": "Acme",
                    "city": "Berlin",
                    "country": "Germany",
                    "publication_date": "2026-04-17",
                    "contract_duration": None,
                    "start_date": None,
                }
            ],
            1,
            "live-db",
            None,
        ),
    )

    with TestClient(app) as client:
        response = client.get("/offers/catalog?source=business_france&limit=5")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["meta"]["data_source"] == "live-db"
    assert payload["offers"][0]["id"] == "BF-123"
    assert payload["offers"][0]["city"] == "Berlin"


def test_business_france_catalog_returns_explicit_missing_driver_detail(monkeypatch):
    monkeypatch.setattr(
        offers_routes,
        "_load_catalog_db_first",
        lambda limit, source: ([], 0, "error", offers_routes.FallbackReason.DB_ERROR),
    )
    monkeypatch.setenv("DATABASE_URL", "postgres://example")
    original_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "psycopg":
            raise ModuleNotFoundError("No module named 'psycopg'", name="psycopg")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with TestClient(app) as client:
        response = client.get("/offers/catalog?source=business_france&limit=5")

    assert response.status_code == 503, response.text
    payload = response.json()
    assert payload["error"] == "CATALOG_UNAVAILABLE"
    assert payload["reason"] == "DB_ERROR"
    assert payload["detail"] == "MISSING_DRIVER"


def test_business_france_detail_uses_postgres_mapping(monkeypatch):
    monkeypatch.setattr(
        offers_routes,
        "_load_offer_detail_from_postgres",
        lambda offer_id: (
            {
                "id": offer_id,
                "source": "business_france",
                "title": "VIE Data Analyst",
                "description": "Mission en analyse de données.",
                "company": "Acme",
                "city": "Munich",
                "country": "Germany",
                "publication_date": "2026-04-17",
                "contract_duration": None,
                "start_date": None,
            },
            None,
        ),
    )

    with TestClient(app) as client:
        response = client.get("/offers/BF-999/detail")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == "BF-999"
    assert payload["source"] == "business_france"
    assert payload["city"] == "Munich"


def test_inbox_catalog_does_not_fallback_to_fixtures_for_business_france(monkeypatch):
    monkeypatch.setattr(
        inbox_catalog,
        "_load_business_france_from_postgres",
        lambda: [
            {
                "id": "BF-123",
                "source": "business_france",
                "title": "VIE Analyst",
                "description": "Business France row from clean_offers",
                "company": "Acme",
                "city": "Berlin",
                "country": "Germany",
                "publication_date": "2026-04-17",
                "contract_duration": None,
                "start_date": None,
            }
        ],
    )
    monkeypatch.setattr(inbox_catalog, "_load_france_travail_from_sqlite", lambda: [])
    monkeypatch.setattr(inbox_catalog, "_get_cached_catalog", lambda: None)

    offers = inbox_catalog.load_catalog_offers()

    bf_offers = [offer for offer in offers if offer.get("source") == "business_france"]
    assert bf_offers
    assert bf_offers[0]["id"] == "BF-123"
