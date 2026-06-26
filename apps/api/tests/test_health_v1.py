from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app


def test_fetch_postgres_signal_marks_missing_ingestion_as_not_ok(monkeypatch):
    import api.routes.health as health

    class FakeRepository:
        def fetch_latest_ingestion_timestamp(self, source="business_france"):
            assert source == "business_france"
            return None

    monkeypatch.setattr(health, "OffersPgRepository", FakeRepository)

    assert health._fetch_postgres_signal() == {
        "ok": False,
        "source": "business_france",
        "latest_ingestion_at": None,
        "error": "no_data",
    }


def test_health_includes_cached_postgres_signal_when_latest_ingestion_is_available(monkeypatch):
    import api.routes.health as health

    class FakeRepository:
        def fetch_latest_ingestion_timestamp(self, source="business_france"):
            assert source == "business_france"
            return "2026-06-25T08:00:00+00:00"

    monkeypatch.setattr(health, "OffersPgRepository", FakeRepository)
    monkeypatch.setattr(health, "_schedule_postgres_signal_refresh", lambda: None)
    health._refresh_postgres_signal_sync()

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "api"
    assert "version" in body
    assert "request_id" in body
    assert body["postgres"] == {
        "ok": True,
        "source": "business_france",
        "latest_ingestion_at": "2026-06-25T08:00:00+00:00",
    }


def test_health_postgres_signal_fails_open_on_runtime_error(monkeypatch):
    import api.routes.health as health

    class FakeRepository:
        def fetch_latest_ingestion_timestamp(self, source="business_france"):
            raise RuntimeError("DATABASE_URL is not set")

    monkeypatch.setattr(health, "OffersPgRepository", FakeRepository)
    monkeypatch.setattr(health, "_schedule_postgres_signal_refresh", lambda: None)
    health._refresh_postgres_signal_sync()

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["postgres"] == {
        "ok": False,
        "source": "business_france",
        "latest_ingestion_at": None,
        "error": "unavailable",
    }
