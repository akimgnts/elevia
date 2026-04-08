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
        assert "rome_competences" in item


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
# 5. matched_skills appear in inbox items
# ============================================================================


@pytest.fixture
def profile_akim():
    """Load Akim's profile for matching tests."""
    fixtures_path = Path(__file__).parent.parent / "fixtures" / "profiles" / "akim_guentas_matching.json"
    with open(fixtures_path) as f:
        return json.load(f)


def test_inbox_includes_matched_skills(client, profile_akim, monkeypatch):
    """Sprint 7: Verify matched_skills appear from profile↔offer intersection."""
    import os
    monkeypatch.setenv("ELEVIA_INBOX_USE_VIE_FIXTURES", "1")

    resp = client.post("/inbox", json={
        "profile_id": "akim-test",
        "profile": profile_akim,
        "min_score": 50,
        "limit": 5,
    })
    assert resp.status_code == 200
    data = resp.json()

    # Should have at least 1 match with VIE fixtures
    assert len(data["items"]) >= 1, "Expected at least 1 matched VIE offer"

    # At least one item should score above fallback (15)
    assert any(item.get("score", 0) > 15 for item in data["items"]), "Expected score > 15 with Akim profile"

    # At least one item should have matched_skills
    items_with_skills = [i for i in data["items"] if i.get("matched_skills")]
    assert len(items_with_skills) >= 1, "Expected at least 1 item with matched_skills"

    # Verify matched_skills are from real intersection
    for item in items_with_skills:
        matched = item["matched_skills"]
        assert isinstance(matched, list)
        assert len(matched) <= 3, "matched_skills should be capped at 3"
        # Skills should be strings
        for skill in matched:
            assert isinstance(skill, str)
            assert len(skill) > 0


# ============================================================================
# 7. Profile fixture lookup behavior
# ============================================================================


def test_inbox_profile_lookup_ok(monkeypatch):
    """Profile fixture should be found when enabled and id matches."""
    import os
    monkeypatch.setenv("ELEVIA_INBOX_PROFILE_FIXTURES", "1")
    monkeypatch.setenv("ELEVIA_PROFILE_FIXTURE_DEFAULT", "")
    from api.routes import inbox as inbox_routes

    payload = {"skills": ["sql"]}
    profile, status = inbox_routes._load_profile_fixture("akim_guentas_matching", payload)
    assert status == "FOUND"
    assert isinstance(profile.get("skills"), list)
    assert len(profile["skills"]) >= 10


def test_inbox_profile_not_found(monkeypatch):
    """Unknown profile_id should not silently map when default is disabled."""
    import os
    monkeypatch.setenv("ELEVIA_INBOX_PROFILE_FIXTURES", "1")
    monkeypatch.setenv("ELEVIA_PROFILE_FIXTURE_DEFAULT", "")
    from api.routes import inbox as inbox_routes

    payload = {"skills": ["sql", "python", "api", "json"]}
    profile, status = inbox_routes._load_profile_fixture("unknown_profile_id", payload)
    assert status == "NOT_FOUND"
    assert profile == payload


def test_inbox_profile_default_fallback(monkeypatch):
    """Low-skill payload should fallback to default fixture when enabled."""
    import os
    monkeypatch.setenv("ELEVIA_INBOX_PROFILE_FIXTURES", "1")
    monkeypatch.setenv("ELEVIA_PROFILE_FIXTURE_DEFAULT", "akim_guentas_matching")
    monkeypatch.setenv("ELEVIA_PROFILE_FIXTURE_MIN_SKILLS", "3")
    from api.routes import inbox as inbox_routes

    payload = {"skills": ["sql"]}
    profile, status = inbox_routes._load_profile_fixture("unknown_profile_id", payload)
    assert status == "DEFAULT"
    assert isinstance(profile.get("skills"), list)
    assert len(profile["skills"]) >= 10


def test_warm_inbox_runtime_builds_caches(monkeypatch):
    catalog = [
        {
            "id": "offer-1",
            "title": "Data Analyst",
            "description": "Analyse data with SQL and Python",
            "skills": ["sql", "python"],
            "skills_uri": ["u:sql", "u:python"],
            "skills_display": [{"uri": "u:sql", "label": "SQL"}, {"uri": "u:python", "label": "Python"}],
            "offer_cluster": "DATA_IT",
        }
    ]
    monkeypatch.setattr(inbox_routes, "_load_catalog_offers", lambda: catalog)
    monkeypatch.setattr(inbox_routes, "_cluster_idf_cache", None)
    monkeypatch.setattr(inbox_routes, "_engine_cache", None)
    monkeypatch.setattr(inbox_routes, "_engine_cache_catalog_id", None)

    stats = inbox_routes.warm_inbox_runtime()

    assert stats["catalog_count"] == 1
    assert inbox_routes._engine_cache is not None


# ============================================================================
# 6. Upsert: second decision updates status
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


def test_inbox_includes_rome_link(monkeypatch, client, profile_demo, tmp_path):
    db_path = tmp_path / "offers.db"
    seed_conn = sqlite3.connect(db_path)
    seed_conn.row_factory = sqlite3.Row
    seed_conn.execute("""
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
    seed_conn.execute("""
        CREATE TABLE offer_rome_link (
            offer_id TEXT PRIMARY KEY,
            rome_code TEXT,
            rome_label TEXT,
            linked_at TEXT NOT NULL
        )
    """)
    seed_conn.execute("""
        CREATE TABLE dim_rome_competence (
            competence_code TEXT PRIMARY KEY,
            competence_label TEXT NOT NULL,
            esco_uri TEXT
        )
    """)
    seed_conn.execute("""
        CREATE TABLE bridge_rome_metier_competence (
            rome_code TEXT NOT NULL,
            competence_code TEXT NOT NULL
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
    ft_offer_no_link = {
        "id": "FT-TEST-002",
        "source": "france_travail",
        "title": "Assistant RH",
        "description": "Gestion administrative RH.",
        "company": "PeopleLab",
        "city": "Lyon",
        "country": "FR",
        "publication_date": "2025-01-03",
        "contract_duration": 12,
        "start_date": "2025-04-15",
    }

    seed_conn.execute(
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
    seed_conn.execute(
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
    seed_conn.execute(
        """
        INSERT INTO fact_offers
        (id, source, title, description, company, city, country, publication_date, contract_duration, start_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ft_offer_no_link["id"],
            ft_offer_no_link["source"],
            ft_offer_no_link["title"],
            ft_offer_no_link["description"],
            ft_offer_no_link["company"],
            ft_offer_no_link["city"],
            ft_offer_no_link["country"],
            ft_offer_no_link["publication_date"],
            ft_offer_no_link["contract_duration"],
            ft_offer_no_link["start_date"],
        ),
    )
    seed_conn.execute(
        "INSERT INTO offer_rome_link (offer_id, rome_code, rome_label, linked_at) VALUES (?, ?, ?, ?)",
        ("FT-TEST-001", "M1607", "Conseiller en emploi", "2025-01-15T10:00:00Z"),
    )
    seed_conn.executemany(
        "INSERT INTO dim_rome_competence (competence_code, competence_label, esco_uri) VALUES (?, ?, ?)",
        [
            ("C001", "Analyse de données", "esco:skill/C001"),
            ("C002", "Reporting financier", "esco:skill/C002"),
            ("C003", "Modélisation", "esco:skill/C003"),
            ("C004", "Visualisation", "esco:skill/C004"),
        ],
    )
    seed_conn.executemany(
        "INSERT INTO bridge_rome_metier_competence (rome_code, competence_code) VALUES (?, ?)",
        [
            ("M1607", "C004"),
            ("M1607", "C002"),
            ("M1607", "C001"),
            ("M1607", "C003"),
        ],
    )
    seed_conn.commit()

    before_rows = [
        tuple(row)
        for row in seed_conn.execute(
            "SELECT id, source, title, description, company, city, country, publication_date, contract_duration, start_date FROM fact_offers"
        ).fetchall()
    ]

    def _catalog_stub():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, source, title, description, company, city, country, publication_date, contract_duration, start_date FROM fact_offers"
        ).fetchall()
        conn.close()
        offers = [dict(r) for r in rows]
        # BF offers require is_vie=True (set via payload_json in production)
        for offer in offers:
            if offer.get("source") == "business_france":
                offer["is_vie"] = True
        return offers

    monkeypatch.setattr(inbox_routes, "_load_catalog_offers", _catalog_stub)
    monkeypatch.setattr(inbox_routes, "_load_decided_ids", lambda _: set())
    monkeypatch.setattr(
        inbox_routes,
        "get_connection",
        lambda: sqlite3.connect(db_path, check_same_thread=False),
    )

    resp = client.post("/inbox?domain_mode=all", json={
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
    assert "FT-TEST-002" in items_by_id

    ft_item = items_by_id["FT-TEST-001"]
    bf_item = items_by_id["BF-TEST-001"]
    ft_no_link_item = items_by_id["FT-TEST-002"]

    assert ft_item["rome"] == {"rome_code": "M1607", "rome_label": "Conseiller en emploi"}
    assert bf_item["rome"] is None
    assert ft_no_link_item["rome"] is None

    assert ft_item["rome_competences"] == [
        {"competence_code": "C001", "competence_label": "Analyse de données", "esco_uri": "esco:skill/C001"},
        {"competence_code": "C002", "competence_label": "Reporting financier", "esco_uri": "esco:skill/C002"},
        {"competence_code": "C003", "competence_label": "Modélisation", "esco_uri": "esco:skill/C003"},
    ]
    assert bf_item["rome_competences"] == []
    assert ft_no_link_item["rome_competences"] == []

    after_conn = sqlite3.connect(db_path)
    after_rows = [
        tuple(row)
        for row in after_conn.execute(
            "SELECT id, source, title, description, company, city, country, publication_date, contract_duration, start_date FROM fact_offers"
        ).fetchall()
    ]
    after_conn.close()
    assert before_rows == after_rows
    seed_conn.close()
