"""
test_inbox.py - Contract + integration tests for inbox endpoints.
"""

import sys
import json
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.utils.db import DB_PATH, get_connection


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def profile_demo():
    fixtures_path = Path(__file__).parent.parent / "fixtures" / "profile_demo.json"
    with open(fixtures_path) as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def _clean_decisions():
    """Remove all decisions before each test."""
    if DB_PATH.exists():
        conn = get_connection()
        conn.execute("DELETE FROM offer_decisions")
        conn.commit()
        conn.close()
    yield


# ============================================================================
# 1. POST /inbox returns 200 with correct schema
# ============================================================================


def test_inbox_returns_schema(client, profile_demo):
    resp = client.post("/inbox", json={
        "profile_id": "test-user",
        "profile": profile_demo,
        "min_score": 0,
        "limit": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "profile_id" in data
    assert "items" in data
    assert "total_matched" in data
    assert "total_decided" in data
    assert isinstance(data["items"], list)
    for item in data["items"]:
        assert "offer_id" in item
        assert "score" in item
        assert "reasons" in item
        assert "title" in item


# ============================================================================
# 2. POST /offers/{id}/decision creates decision
# ============================================================================


def test_decision_creates(client):
    resp = client.post("/offers/offer-1/decision", json={
        "profile_id": "test-user",
        "status": "SHORTLISTED",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["offer_id"] == "offer-1"
    assert data["status"] == "SHORTLISTED"
    assert data["profile_id"] == "test-user"
    assert "decided_at" in data


# ============================================================================
# 3. POST /inbox excludes decided offers
# ============================================================================


def test_inbox_excludes_decided(client, profile_demo):
    # First, get some items
    resp1 = client.post("/inbox", json={
        "profile_id": "test-user",
        "profile": profile_demo,
        "min_score": 0,
        "limit": 100,
    })
    items_before = resp1.json()["items"]
    if not items_before:
        pytest.skip("No catalog offers in DB")

    # Decide on the first offer
    first_id = items_before[0]["offer_id"]
    client.post(f"/offers/{first_id}/decision", json={
        "profile_id": "test-user",
        "status": "DISMISSED",
    })

    # Inbox should no longer include it
    resp2 = client.post("/inbox", json={
        "profile_id": "test-user",
        "profile": profile_demo,
        "min_score": 0,
        "limit": 100,
    })
    ids_after = {i["offer_id"] for i in resp2.json()["items"]}
    assert first_id not in ids_after


# ============================================================================
# 4. Scores in [0, 100], reasons ≤ 3
# ============================================================================


def test_scores_and_reasons_bounds(client, profile_demo):
    resp = client.post("/inbox", json={
        "profile_id": "test-user",
        "profile": profile_demo,
        "min_score": 0,
        "limit": 50,
    })
    for item in resp.json()["items"]:
        assert 0 <= item["score"] <= 100
        assert len(item["reasons"]) <= 3


# ============================================================================
# 5. Upsert: second decision updates status
# ============================================================================


def test_decision_upsert(client):
    client.post("/offers/offer-u/decision", json={
        "profile_id": "test-user",
        "status": "SHORTLISTED",
    })
    resp = client.post("/offers/offer-u/decision", json={
        "profile_id": "test-user",
        "status": "DISMISSED",
        "note": "changed mind",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "DISMISSED"

    # Verify in DB
    conn = get_connection()
    row = conn.execute(
        "SELECT status, note FROM offer_decisions WHERE profile_id=? AND offer_id=?",
        ("test-user", "offer-u"),
    ).fetchone()
    conn.close()
    assert row["status"] == "DISMISSED"
    assert row["note"] == "changed mind"
