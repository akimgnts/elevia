"""
Tests for offer skill URI storage in backfill.
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(API_ROOT / "src"))
sys.path.insert(0, str(API_ROOT / "scripts"))

from api.utils.offer_skills import ensure_offer_skills_table
from backfill_offer_skills import backfill_offer_skills


def test_backfill_writes_skill_uri(monkeypatch, tmp_path):
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
        ("FT-300", "france_travail", "Data Analyst", "desc", payload_json),
    )
    conn.commit()

    # Stub ESCO mapper used in backfill_offer_skills
    def _stub_map_skill(label, enable_fuzzy=False):
        if str(label).lower() == "python":
            return {"esco_id": "http://data.europa.eu/esco/skill/python"}
        return None

    monkeypatch.setattr("backfill_offer_skills.map_skill", _stub_map_skill)

    stats = backfill_offer_skills(conn)
    assert stats["offers_scanned"] == 1

    row = conn.execute(
        "SELECT skill, skill_uri FROM fact_offer_skills WHERE offer_id='FT-300' AND skill='python'"
    ).fetchone()
    assert row is not None
    assert row[1] == "http://data.europa.eu/esco/skill/python"
    conn.close()


def test_backfill_updates_existing_row_uri(monkeypatch, tmp_path):
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
        ("FT-301", "france_travail", "Data Analyst", "desc", payload_json),
    )
    conn.execute(
        """
        INSERT INTO fact_offer_skills (offer_id, skill, skill_uri, source, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("FT-301", "python", None, "france_travail", None, "2026-01-30T00:00:00Z"),
    )
    conn.commit()

    def _stub_map_skill(label, enable_fuzzy=False):
        if str(label).lower() == "python":
            return {"esco_id": "http://data.europa.eu/esco/skill/python"}
        return None

    monkeypatch.setattr("backfill_offer_skills.map_skill", _stub_map_skill)

    backfill_offer_skills(conn)

    row = conn.execute(
        "SELECT skill_uri FROM fact_offer_skills WHERE offer_id='FT-301' AND skill='python'"
    ).fetchone()
    assert row is not None
    assert row[0] == "http://data.europa.eu/esco/skill/python"
    conn.close()
