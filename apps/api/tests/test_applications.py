"""
test_applications.py - Contract + integration tests for Applications Tracker V0.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.utils import db as db_utils
from api.routes import applications as applications_routes


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "offers.db"
    monkeypatch.setattr(db_utils, "DB_PATH", db_path)
    monkeypatch.setattr(applications_routes, "get_connection", db_utils.get_connection)
    db_utils._initialized = False
    yield


def test_create_application(client, monkeypatch):
    monkeypatch.setattr(applications_routes, "_utc_now", lambda: "2026-01-30T10:00:00Z")
    resp = client.post("/applications", json={
        "offer_id": "offer-1",
        "status": "shortlisted",
        "note": "First pass",
        "next_follow_up_date": "2026-02-01",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["offer_id"] == "offer-1"
    assert data["status"] == "shortlisted"
    assert data["note"] == "First pass"
    assert data["next_follow_up_date"] == "2026-02-01"
    assert data["created_at"] == "2026-01-30T10:00:00Z"
    assert data["updated_at"] == "2026-01-30T10:00:00Z"


def test_upsert_updates_fields_and_updated_at(client, monkeypatch):
    times = ["2026-01-30T10:00:00Z", "2026-01-30T11:00:00Z"]
    monkeypatch.setattr(applications_routes, "_utc_now", lambda: times.pop(0))

    resp1 = client.post("/applications", json={
        "offer_id": "offer-2",
        "status": "applied",
        "note": "Initial",
        "next_follow_up_date": "2026-02-02",
    })
    assert resp1.status_code == 201

    resp2 = client.post("/applications", json={
        "offer_id": "offer-2",
        "status": "dismissed",
        "note": "Updated",
        "next_follow_up_date": "2026-02-05",
    })
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["status"] == "dismissed"
    assert data["note"] == "Updated"
    assert data["next_follow_up_date"] == "2026-02-05"
    assert data["updated_at"] == "2026-01-30T11:00:00Z"


def test_list_sorted_by_updated_at_desc(client, monkeypatch):
    times = [
        "2026-01-30T09:00:00Z",
        "2026-01-30T10:00:00Z",
        "2026-01-30T11:00:00Z",
    ]
    monkeypatch.setattr(applications_routes, "_utc_now", lambda: times.pop(0))

    client.post("/applications", json={
        "offer_id": "offer-3",
        "status": "shortlisted",
    })
    client.post("/applications", json={
        "offer_id": "offer-4",
        "status": "applied",
    })
    client.patch("/applications/offer-3", json={
        "note": "bumped",
    })

    resp = client.get("/applications")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["offer_id"] == "offer-3"
    assert items[1]["offer_id"] == "offer-4"


def test_get_missing_returns_404(client):
    resp = client.get("/applications/missing")
    assert resp.status_code == 404


def test_patch_partial_update(client, monkeypatch):
    monkeypatch.setattr(applications_routes, "_utc_now", lambda: "2026-01-30T12:00:00Z")
    client.post("/applications", json={
        "offer_id": "offer-5",
        "status": "shortlisted",
    })

    monkeypatch.setattr(applications_routes, "_utc_now", lambda: "2026-01-30T12:30:00Z")
    resp = client.patch("/applications/offer-5", json={
        "note": "Updated note",
        "next_follow_up_date": "2026-02-10",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["note"] == "Updated note"
    assert data["next_follow_up_date"] == "2026-02-10"
    assert data["updated_at"] == "2026-01-30T12:30:00Z"


def test_delete_application(client):
    client.post("/applications", json={
        "offer_id": "offer-6",
        "status": "applied",
    })
    resp = client.delete("/applications/offer-6")
    assert resp.status_code == 204
    resp_missing = client.get("/applications/offer-6")
    assert resp_missing.status_code == 404


def test_invalid_status_returns_400(client):
    resp = client.post("/applications", json={
        "offer_id": "offer-7",
        "status": "invalid",
    })
    assert resp.status_code == 422


def test_invalid_date_returns_400(client):
    resp = client.post("/applications", json={
        "offer_id": "offer-8",
        "status": "shortlisted",
        "next_follow_up_date": "2026/02/01",
    })
    assert resp.status_code == 400
