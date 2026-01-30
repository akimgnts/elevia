"""
test_rome_ingestion.py - Sanity checks for ROME referential schema and ingestion logic.

Tests run against a temporary in-memory SQLite DB (no network calls).
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest


# ---------------------------------------------------------------------------
# Inline schema (same as ingest_rome.py)
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS dim_rome_metier (
    rome_code    TEXT PRIMARY KEY,
    rome_label   TEXT NOT NULL,
    last_updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dim_rome_competence (
    competence_code  TEXT PRIMARY KEY,
    competence_label TEXT NOT NULL,
    esco_uri         TEXT,
    last_updated     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bridge_rome_metier_competence (
    rome_code       TEXT NOT NULL,
    competence_code TEXT NOT NULL,
    PRIMARY KEY (rome_code, competence_code),
    FOREIGN KEY (rome_code) REFERENCES dim_rome_metier(rome_code),
    FOREIGN KEY (competence_code) REFERENCES dim_rome_competence(competence_code)
);
CREATE INDEX IF NOT EXISTS idx_bridge_rome_code ON bridge_rome_metier_competence(rome_code);
CREATE INDEX IF NOT EXISTS idx_bridge_comp_code ON bridge_rome_metier_competence(competence_code);
"""


@pytest.fixture
def conn():
    """In-memory SQLite with ROME schema."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA_SQL)
    c.commit()
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


def test_tables_exist(conn):
    """All three ROME tables are created."""
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "dim_rome_metier" in tables
    assert "dim_rome_competence" in tables
    assert "bridge_rome_metier_competence" in tables


def test_metier_upsert(conn):
    """INSERT + ON CONFLICT UPDATE works for dim_rome_metier."""
    conn.execute(
        "INSERT INTO dim_rome_metier VALUES (?, ?, ?)",
        ("M1234", "Développeur", "2025-01-01T00:00:00"),
    )
    conn.execute(
        """INSERT INTO dim_rome_metier (rome_code, rome_label, last_updated)
           VALUES (?, ?, ?)
           ON CONFLICT(rome_code) DO UPDATE SET
               rome_label = excluded.rome_label,
               last_updated = excluded.last_updated""",
        ("M1234", "Développeur full-stack", "2025-02-01T00:00:00"),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM dim_rome_metier WHERE rome_code='M1234'").fetchone()
    assert row["rome_label"] == "Développeur full-stack"
    assert row["last_updated"] == "2025-02-01T00:00:00"


def test_competence_upsert(conn):
    """INSERT + ON CONFLICT UPDATE works for dim_rome_competence."""
    conn.execute(
        "INSERT INTO dim_rome_competence VALUES (?, ?, ?, ?)",
        ("C001", "Python", None, "2025-01-01T00:00:00"),
    )
    conn.execute(
        """INSERT INTO dim_rome_competence (competence_code, competence_label, esco_uri, last_updated)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(competence_code) DO UPDATE SET
               competence_label = excluded.competence_label,
               esco_uri = excluded.esco_uri,
               last_updated = excluded.last_updated""",
        ("C001", "Python programming", "http://esco.eu/python", "2025-02-01T00:00:00"),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM dim_rome_competence WHERE competence_code='C001'").fetchone()
    assert row["competence_label"] == "Python programming"
    assert row["esco_uri"] == "http://esco.eu/python"


def test_bridge_insert_ignore(conn):
    """Bridge table uses INSERT OR IGNORE for duplicates."""
    conn.execute("INSERT INTO dim_rome_metier VALUES ('M1', 'Dev', '2025-01-01')")
    conn.execute("INSERT INTO dim_rome_competence VALUES ('C1', 'Python', NULL, '2025-01-01')")
    conn.execute("INSERT INTO bridge_rome_metier_competence VALUES ('M1', 'C1')")
    # Second insert should be silently ignored
    conn.execute("INSERT OR IGNORE INTO bridge_rome_metier_competence VALUES ('M1', 'C1')")
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM bridge_rome_metier_competence").fetchone()[0]
    assert count == 1


def test_bridge_fk_columns(conn):
    """Bridge table has rome_code and competence_code columns."""
    conn.execute("INSERT INTO dim_rome_metier VALUES ('M1', 'Dev', '2025-01-01')")
    conn.execute("INSERT INTO dim_rome_competence VALUES ('C1', 'Python', NULL, '2025-01-01')")
    conn.execute("INSERT INTO bridge_rome_metier_competence VALUES ('M1', 'C1')")
    conn.commit()
    row = conn.execute("SELECT * FROM bridge_rome_metier_competence").fetchone()
    assert row["rome_code"] == "M1"
    assert row["competence_code"] == "C1"


def test_schema_does_not_create_fact_offers(conn):
    """ROME schema must NOT create or alter fact_offers."""
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "fact_offers" not in tables


def test_idempotent_schema(conn):
    """Running schema creation twice doesn't error."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "dim_rome_metier" in tables
