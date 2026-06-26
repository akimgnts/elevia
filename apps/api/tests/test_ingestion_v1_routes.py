from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app


def test_ingestion_latest_returns_latest_business_france_run(monkeypatch):
    import api.routes.ingestion_v1 as ingestion_v1

    class FakeRepository:
        def fetch_latest_ingestion(self, source="business_france"):
            assert source == "business_france"
            return {
                "id": 7,
                "source": "business_france",
                "started_at": "2026-06-25T08:00:00+00:00",
                "finished_at": "2026-06-25T08:03:00+00:00",
                "status": "success",
                "fetched_count": 10,
                "persisted_count_raw": 10,
                "attempted_count_clean": 10,
                "persisted_count_clean": 9,
                "new_count": 4,
                "existing_count": 5,
                "missing_count": 1,
                "active_total": 123,
                "error": None,
            }

    monkeypatch.setattr(ingestion_v1, "OffersPgRepository", FakeRepository)

    client = TestClient(app)
    response = client.get("/ingestion/latest")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["active_total"] == 123


def test_ingestion_latest_is_available_under_api_prefix(monkeypatch):
    import api.routes.ingestion_v1 as ingestion_v1

    class FakeRepository:
        def fetch_latest_ingestion(self, source="business_france"):
            return {
                "id": 8,
                "source": "business_france",
                "started_at": "2026-06-25T08:00:00+00:00",
                "finished_at": "2026-06-25T08:03:00+00:00",
                "status": "success",
                "fetched_count": 12,
                "persisted_count_raw": 12,
                "attempted_count_clean": 12,
                "persisted_count_clean": 12,
                "new_count": 6,
                "existing_count": 6,
                "missing_count": 0,
                "active_total": 150,
                "error": None,
            }

    monkeypatch.setattr(ingestion_v1, "OffersPgRepository", FakeRepository)

    client = TestClient(app)
    response = client.get("/api/ingestion/latest")

    assert response.status_code == 200
    assert response.json()["id"] == 8


def test_ingestion_latest_returns_503_with_stable_payload_when_repo_unavailable(monkeypatch):
    import api.routes.ingestion_v1 as ingestion_v1

    class FakeRepository:
        def fetch_latest_ingestion(self, source="business_france"):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(ingestion_v1, "OffersPgRepository", FakeRepository)

    client = TestClient(app)
    response = client.get("/ingestion/latest")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "INGESTION_UNAVAILABLE",
            "message": "Ingestion status is temporarily unavailable",
        }
    }
