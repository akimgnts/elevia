"""
test_offer_skills.py
====================
Skill-aware matching V1 - Offer skills storage and guardrails.
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Add src/ and scripts/ to path
API_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(API_ROOT / "src"))
sys.path.insert(0, str(API_ROOT / "scripts"))

from api.main import app
from api.routes import matching as matching_routes
from api.utils import db as db_utils
from api.utils.offer_skills import ensure_offer_skills_table, get_offer_skills_by_offer_ids
from matching.matching_v1 import MatchingEngine, PARTIAL_MAX_SCORE
from matching.extractors import extract_profile, normalize_skill_label
from backfill_offer_skills import backfill_offer_skills


def _make_offer(offer_id: str, skills=None):
    return {
        "id": offer_id,
        "is_vie": True,
        "country": "france",
        "title": "Data Analyst",
        "company": "TestCorp",
        "skills": skills if skills is not None else [],
        "languages": ["français"],
        "education": "bac+3",
    }


def _make_profile(skills=None):
    return {
        "id": "profile_1",
        "skills": skills if skills is not None else ["python", "sql"],
        "languages": ["français"],
        "education": "bac+3",
    }


def test_offer_skills_table_created():
    conn = sqlite3.connect(":memory:")
    ensure_offer_skills_table(conn)
    tables = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert "fact_offer_skills" in tables
    columns = {row[1] for row in conn.execute("PRAGMA table_info(fact_offer_skills)").fetchall()}
    assert "skill_uri" in columns
    conn.close()


def test_offer_skills_table_migration_adds_skill_uri():
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE fact_offer_skills (offer_id TEXT NOT NULL, skill TEXT NOT NULL, source TEXT NOT NULL, "
        "confidence REAL, created_at TEXT NOT NULL, PRIMARY KEY (offer_id, skill))"
    )
    ensure_offer_skills_table(conn)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(fact_offer_skills)").fetchall()}
    assert "skill_uri" in columns
    conn.close()


def test_normalize_skill_label():
    assert normalize_skill_label("  C++ ") == "c++"
    assert normalize_skill_label("Data-Analysis!") == "data analysis"


def test_get_offer_skills_by_offer_ids():
    conn = sqlite3.connect(":memory:")
    ensure_offer_skills_table(conn)
    conn.execute(
        """
        INSERT INTO fact_offer_skills (offer_id, skill, skill_uri, source, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("FT-1", "python", "http://data.europa.eu/esco/skill/py", "france_travail", None, "2026-01-30T00:00:00Z"),
    )
    conn.execute(
        """
        INSERT INTO fact_offer_skills (offer_id, skill, skill_uri, source, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("FT-1", "sql", None, "rome", None, "2026-01-30T00:00:00Z"),
    )
    conn.commit()

    mapping = get_offer_skills_by_offer_ids(conn, ["FT-1", "FT-2"])
    assert mapping["FT-1"]["skills"] == ["python", "sql"]
    assert mapping["FT-1"]["skills_uri"] == ["http://data.europa.eu/esco/skill/py"]
    assert "FT-2" not in mapping
    conn.close()


def test_scoring_guardrail_empty_offer_skills():
    profile = extract_profile(_make_profile())
    offers = [_make_offer("FT-1", skills=[])]
    engine = MatchingEngine(offers)

    result = engine.score_offer(profile, offers[0])
    assert result.score_is_partial is True
    assert result.score <= PARTIAL_MAX_SCORE
    assert any("Compétences indisponibles" in r for r in result.reasons)


def test_scoring_with_offer_skills():
    profile = extract_profile(_make_profile())
    offers = [_make_offer("FT-2", skills=["python", "sql"])]
    engine = MatchingEngine(offers)

    result = engine.score_offer(profile, offers[0])
    assert result.score_is_partial is False
    assert result.score > 0


def test_backfill_idempotent(tmp_path):
    db_path = tmp_path / "offers.db"
    conn = sqlite3.connect(str(db_path))

    conn.execute(
        """
        CREATE TABLE fact_offers (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            title TEXT,
            description TEXT,
            payload_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE offer_rome_link (
            offer_id TEXT PRIMARY KEY,
            rome_code TEXT,
            rome_label TEXT,
            linked_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE dim_rome_competence (
            competence_code TEXT PRIMARY KEY,
            competence_label TEXT NOT NULL,
            esco_uri TEXT,
            last_updated TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE bridge_rome_metier_competence (
            rome_code TEXT NOT NULL,
            competence_code TEXT NOT NULL,
            PRIMARY KEY (rome_code, competence_code)
        )
        """
    )
    ensure_offer_skills_table(conn)

    payload = {
        "intitule": "Data Analyst",
        "description": "Analyse de données avec Python et SQL",
        "competences": [{"libelle": "Python"}],
    }
    payload_json = json.dumps(payload, ensure_ascii=False)
    conn.execute(
        "INSERT INTO fact_offers VALUES (?, ?, ?, ?, ?)",
        ("FT-100", "france_travail", "Data Analyst", "desc", payload_json),
    )
    conn.execute(
        "INSERT INTO offer_rome_link VALUES (?, ?, ?, ?)",
        ("FT-100", "M1234", "Analyste", "2026-01-30T00:00:00Z"),
    )
    conn.execute(
        "INSERT INTO dim_rome_competence VALUES (?, ?, ?, ?)",
        ("C001", "SQL", None, "2026-01-30T00:00:00Z"),
    )
    conn.execute(
        "INSERT INTO bridge_rome_metier_competence VALUES (?, ?)",
        ("M1234", "C001"),
    )
    conn.commit()

    before = conn.execute("SELECT payload_json FROM fact_offers WHERE id='FT-100'").fetchone()[0]
    stats1 = backfill_offer_skills(conn)
    count1 = conn.execute("SELECT COUNT(*) FROM fact_offer_skills").fetchone()[0]
    stats2 = backfill_offer_skills(conn)
    count2 = conn.execute("SELECT COUNT(*) FROM fact_offer_skills").fetchone()[0]
    after = conn.execute("SELECT payload_json FROM fact_offers WHERE id='FT-100'").fetchone()[0]

    assert stats1["offers_scanned"] == 1
    assert stats2["offers_scanned"] == 1
    assert count1 > 0
    assert count1 == count2
    assert before == after

    conn.close()


def test_matching_route_attaches_offer_skills(monkeypatch, tmp_path):
    db_path = tmp_path / "offers.db"
    monkeypatch.setattr(db_utils, "DB_PATH", db_path)
    monkeypatch.setattr(matching_routes, "get_connection", db_utils.get_connection)
    db_utils._initialized = False

    conn = db_utils.get_connection()
    ensure_offer_skills_table(conn)
    conn.execute(
        """
        INSERT INTO fact_offer_skills (offer_id, skill, skill_uri, source, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("FT-200", "python", None, "france_travail", None, "2026-01-30T00:00:00Z"),
    )
    conn.commit()
    conn.close()

    client = TestClient(app)
    payload = {
        "profile": _make_profile(skills=["python"]),
        "offers": [
            {
                "id": "FT-200",
                "is_vie": True,
                "country": "france",
                "title": "Data Analyst",
                "company": "TestCorp",
                "languages": ["français"],
                "education": "bac+3",
            }
        ],
    }
    resp = client.post("/v1/match", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"][0]["score_is_partial"] is False
