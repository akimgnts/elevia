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
from api.routes import inbox as inbox_routes


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
        assert "rome" in item


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


# ============================================================================
# 6. Inbox includes ROME link for FT offers (read-only)
# ============================================================================


def test_inbox_includes_rome_link(monkeypatch, client, profile_demo):
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE fact_offers (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            company TEXT,
            city TEXT,
            country TEXT,
            publication_date TEXT,
            contract_duration INTEGER,
            start_date TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE offer_rome_link (
            offer_id TEXT PRIMARY KEY,
            rome_code TEXT,
            rome_label TEXT,
            linked_at TEXT NOT NULL
        )
    """)

    ft_offer = {
        "id": "FT-TEST-001",
        "source": "france_travail",
        "title": "Data Analyst",
        "description": "Analyse de données, reporting, SQL.",
        "company": "DataBridge",
        "city": "Paris",
        "country": "FR",
        "publication_date": "2025-01-01",
        "contract_duration": 12,
        "start_date": "2025-03-01",
    }
    bf_offer = {
        "id": "BF-TEST-001",
        "source": "business_france",
        "title": "Développeur Full Stack",
        "description": "React, Node.js, API.",
        "company": "NovaStack",
        "city": "Berlin",
        "country": "DE",
        "publication_date": "2025-01-02",
        "contract_duration": 12,
        "start_date": "2025-04-01",
    }

    conn.execute(
        """
        INSERT INTO fact_offers
        (id, source, title, description, company, city, country, publication_date, contract_duration, start_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ft_offer["id"],
            ft_offer["source"],
            ft_offer["title"],
            ft_offer["description"],
            ft_offer["company"],
            ft_offer["city"],
            ft_offer["country"],
            ft_offer["publication_date"],
            ft_offer["contract_duration"],
            ft_offer["start_date"],
        ),
    )
    conn.execute(
        """
        INSERT INTO fact_offers
        (id, source, title, description, company, city, country, publication_date, contract_duration, start_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            bf_offer["id"],
            bf_offer["source"],
            bf_offer["title"],
            bf_offer["description"],
            bf_offer["company"],
            bf_offer["city"],
            bf_offer["country"],
            bf_offer["publication_date"],
            bf_offer["contract_duration"],
            bf_offer["start_date"],
        ),
    )
    conn.execute(
        "INSERT INTO offer_rome_link (offer_id, rome_code, rome_label, linked_at) VALUES (?, ?, ?, ?)",
        ("FT-TEST-001", "M1607", "Conseiller en emploi", "2025-01-15T10:00:00Z"),
    )
    conn.commit()

    before_rows = [
        tuple(row)
        for row in conn.execute(
            "SELECT id, source, title, description, company, city, country, publication_date, contract_duration, start_date FROM fact_offers"
        ).fetchall()
    ]

    def _catalog_stub():
        rows = conn.execute(
            "SELECT id, source, title, description, company, city, country, publication_date, contract_duration, start_date FROM fact_offers"
        ).fetchall()
        return [dict(r) for r in rows]

    monkeypatch.setattr(inbox_routes, "_load_catalog_offers", _catalog_stub)
    monkeypatch.setattr(inbox_routes, "_load_decided_ids", lambda _: set())
    monkeypatch.setattr(inbox_routes, "get_connection", lambda: conn)

    resp = client.post("/inbox", json={
        "profile_id": "rome-test",
        "profile": profile_demo,
        "min_score": 0,
        "limit": 10,
    })
    assert resp.status_code == 200
    data = resp.json()

    items_by_id = {item["offer_id"]: item for item in data["items"]}
    assert "FT-TEST-001" in items_by_id
    assert "BF-TEST-001" in items_by_id

    ft_item = items_by_id["FT-TEST-001"]
    bf_item = items_by_id["BF-TEST-001"]

    assert ft_item["rome"] == {"rome_code": "M1607", "rome_label": "Conseiller en emploi"}
    assert bf_item["rome"] is None

    after_rows = [
        tuple(row)
        for row in conn.execute(
            "SELECT id, source, title, description, company, city, country, publication_date, contract_duration, start_date FROM fact_offers"
        ).fetchall()
    ]
    assert before_rows == after_rows
    conn.close()
