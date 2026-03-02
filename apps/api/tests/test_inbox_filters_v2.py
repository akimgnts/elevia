import json
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import app
from api.routes import inbox as inbox_routes
from api.utils import inbox_catalog


def _seed_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE fact_offers (
            id TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            description TEXT,
            company TEXT,
            city TEXT,
            country TEXT,
            publication_date TEXT,
            contract_duration INTEGER,
            start_date TEXT,
            payload_json TEXT,
            last_updated TEXT
        )
        """
    )
    offers = [
        {
            "id": "A1",
            "source": "business_france",
            "title": "Data Analyst",
            "description": "Analyse data with Python.",
            "company": "Acme",
            "city": "Paris",
            "country": "France",
            "publication_date": "2026-02-10",
        },
        {
            "id": "A2",
            "source": "business_france",
            "title": "Data Engineer",
            "description": "Build pipelines in SQL.",
            "company": "Acme",
            "city": "Lyon",
            "country": "France",
            "publication_date": "2026-02-11",
        },
        {
            "id": "B1",
            "source": "business_france",
            "title": "BI Analyst",
            "description": "Reporting dashboards.",
            "company": "Beta",
            "city": "Paris",
            "country": "France",
            "publication_date": "2026-02-09",
        },
        {
            "id": "C1",
            "source": "business_france",
            "title": "Ops Analyst",
            "description": "Supply ops analytics.",
            "company": "Gamma",
            "city": "Berlin",
            "country": "Germany",
            "publication_date": "2026-02-12",
        },
        {
            "id": "D1",
            "source": "business_france",
            "title": "Data Specialist",
            "description": "Python SQL stack.",
            "company": "Acme",
            "city": "Paris",
            "country": "France",
            "publication_date": "2026-02-12T10:00:00Z",
        },
    ]
    payload = {"is_vie": True, "skills": ["python", "sql"]}
    for offer in offers:
        conn.execute(
            """
            INSERT INTO fact_offers
            (id, source, title, description, company, city, country, publication_date,
             contract_duration, start_date, payload_json, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
            """,
            (
                offer["id"],
                offer["source"],
                offer["title"],
                offer["description"],
                offer["company"],
                offer["city"],
                offer["country"],
                offer["publication_date"],
                json.dumps(payload),
                "2026-02-28",
            ),
        )
    conn.commit()
    conn.close()


def test_inbox_prefilter_sql_deterministic(tmp_path, monkeypatch):
    db_path = tmp_path / "offers.db"
    _seed_db(db_path)
    monkeypatch.setattr(inbox_catalog, "DB_PATH", db_path)
    monkeypatch.setattr(inbox_routes, "_load_decided_ids", lambda _: set())

    profile = {"id": "p1", "skills": ["python", "sql"]}
    params = "domain_mode=all&q_company=Acme&page=1&page_size=2&sort=published_desc"

    with TestClient(app) as client:
        r1 = client.post(f"/inbox?{params}", json={"profile_id": "p1", "profile": profile, "min_score": 0, "limit": 5})
        r2 = client.post(f"/inbox?{params}", json={"profile_id": "p1", "profile": profile, "min_score": 0, "limit": 5})
        assert r1.status_code == 200
        assert r2.status_code == 200
        items1 = [i["offer_id"] for i in r1.json()["items"]]
        items2 = [i["offer_id"] for i in r2.json()["items"]]
        assert items1 == items2
        assert items1 == ["D1", "A2"]


def test_inbox_pagination_stable_order(tmp_path, monkeypatch):
    db_path = tmp_path / "offers.db"
    _seed_db(db_path)
    monkeypatch.setattr(inbox_catalog, "DB_PATH", db_path)
    monkeypatch.setattr(inbox_catalog, "_load_vie_fixtures", lambda: [])
    monkeypatch.setattr(inbox_routes, "_load_decided_ids", lambda _: set())

    profile = {"id": "p1", "skills": ["python", "sql"]}
    params_page1 = "domain_mode=all&q_company=Acme&page=1&page_size=2&sort=published_desc"
    params_page2 = "domain_mode=all&q_company=Acme&page=2&page_size=2&sort=published_desc"

    with TestClient(app) as client:
        r1 = client.post(f"/inbox?{params_page1}", json={"profile_id": "p1", "profile": profile, "min_score": 0, "limit": 5})
        r2 = client.post(f"/inbox?{params_page2}", json={"profile_id": "p1", "profile": profile, "min_score": 0, "limit": 5})
        assert r1.status_code == 200
        assert r2.status_code == 200
        page1 = [i["offer_id"] for i in r1.json()["items"]]
        page2 = [i["offer_id"] for i in r2.json()["items"]]
        assert page1 == ["D1", "A2"]
        assert page2 == ["A1"]
        assert set(page1).isdisjoint(set(page2))


def test_inbox_compass_post_filters(tmp_path, monkeypatch):
    db_path = tmp_path / "offers.db"
    _seed_db(db_path)
    monkeypatch.setattr(inbox_catalog, "DB_PATH", db_path)
    monkeypatch.setattr(inbox_routes, "_load_decided_ids", lambda _: set())

    profile = {"id": "p1", "skills": ["python", "sql"]}
    params = "domain_mode=all&page=1&page_size=5&sort=published_desc&confidence=HIGH"

    with TestClient(app) as client:
        resp = client.post(f"/inbox?{params}", json={"profile_id": "p1", "profile": profile, "min_score": 0, "limit": 5})
        assert resp.status_code == 200
        items = resp.json()["items"]
        for item in items:
            assert item["explain_v1"]["confidence"] == "HIGH"


def test_score_invariance_inbox(tmp_path, monkeypatch):
    db_path = tmp_path / "offers.db"
    _seed_db(db_path)
    monkeypatch.setattr(inbox_catalog, "DB_PATH", db_path)
    monkeypatch.setattr(inbox_routes, "_load_decided_ids", lambda _: set())

    profile = {"id": "p1", "skills": ["python", "sql"]}

    with TestClient(app) as client:
        base = client.post("/inbox?domain_mode=all", json={"profile_id": "p1", "profile": profile, "min_score": 0, "limit": 10})
        filtered = client.post(
            "/inbox?domain_mode=all&q_company=Acme&page=1&page_size=10&sort=published_desc",
            json={"profile_id": "p1", "profile": profile, "min_score": 0, "limit": 10},
        )
        assert base.status_code == 200
        assert filtered.status_code == 200

        base_items = {item["offer_id"]: item["score"] for item in base.json()["items"]}
        filt_items = {item["offer_id"]: item["score"] for item in filtered.json()["items"]}
        shared = set(base_items).intersection(set(filt_items))
        assert shared
        for oid in shared:
            assert base_items[oid] == filt_items[oid]
