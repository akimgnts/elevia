"""
test_rome_enrichment.py - Tests for read-only ROME enrichment.
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from enrich_offers_with_rome import (
    enrich_offers,
    extract_rome_code,
    ensure_link_table,
)


SCHEMA_SQL = """
CREATE TABLE fact_offers (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    payload_json TEXT
);

CREATE TABLE dim_rome_metier (
    rome_code    TEXT PRIMARY KEY,
    rome_label   TEXT NOT NULL,
    last_updated TEXT NOT NULL
);
"""


def _conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON;")
    c.executescript(SCHEMA_SQL)
    c.commit()
    return c


def test_extract_rome_code_explicit_path():
    payload = {"romeCode": "G1602"}
    assert extract_rome_code(payload) == "G1602"


def test_extract_rome_code_nested():
    payload = {"metierRome": {"code": "M1234"}}
    assert extract_rome_code(payload) == "M1234"


def test_enrichment_links_valid_rome():
    conn = _conn()
    conn.execute(
        "INSERT INTO dim_rome_metier VALUES (?, ?, ?)",
        ("G1602", "Personnel de cuisine", "2026-01-01T00:00:00"),
    )
    payload = {"romeCode": "G1602"}
    conn.execute(
        "INSERT INTO fact_offers VALUES (?, ?, ?)",
        ("FT-1", "france_travail", json.dumps(payload)),
    )
    conn.commit()

    ensure_link_table(conn)
    stats = enrich_offers(conn)

    row = conn.execute(
        "SELECT rome_code, rome_label FROM offer_rome_link WHERE offer_id = 'FT-1'"
    ).fetchone()
    assert row["rome_code"] == "G1602"
    assert row["rome_label"] == "Personnel de cuisine"
    assert stats["linked"] == 1

    conn.close()


def test_enrichment_invalid_or_missing_rome_is_null():
    conn = _conn()
    conn.execute(
        "INSERT INTO dim_rome_metier VALUES (?, ?, ?)",
        ("A1234", "Test Metier", "2026-01-01T00:00:00"),
    )
    payload = {"romeCode": "ZZ99"}  # invalid format
    conn.execute(
        "INSERT INTO fact_offers VALUES (?, ?, ?)",
        ("FT-2", "france_travail", json.dumps(payload)),
    )
    conn.execute(
        "INSERT INTO fact_offers VALUES (?, ?, ?)",
        ("FT-3", "france_travail", json.dumps({"other": "value"})),
    )
    conn.commit()

    ensure_link_table(conn)
    enrich_offers(conn)

    row1 = conn.execute(
        "SELECT rome_code, rome_label FROM offer_rome_link WHERE offer_id = 'FT-2'"
    ).fetchone()
    row2 = conn.execute(
        "SELECT rome_code, rome_label FROM offer_rome_link WHERE offer_id = 'FT-3'"
    ).fetchone()
    assert row1["rome_code"] is None
    assert row1["rome_label"] is None
    assert row2["rome_code"] is None
    assert row2["rome_label"] is None

    conn.close()


def test_idempotent_no_duplicates():
    conn = _conn()
    conn.execute(
        "INSERT INTO dim_rome_metier VALUES (?, ?, ?)",
        ("A1234", "Test Metier", "2026-01-01T00:00:00"),
    )
    payload = {"codeRome": "A1234"}
    conn.execute(
        "INSERT INTO fact_offers VALUES (?, ?, ?)",
        ("FT-4", "france_travail", json.dumps(payload)),
    )
    conn.commit()

    ensure_link_table(conn)
    enrich_offers(conn)
    enrich_offers(conn)

    rows = conn.execute("SELECT * FROM offer_rome_link").fetchall()
    assert len(rows) == 1
    assert rows[0]["rome_code"] == "A1234"
    assert rows[0]["rome_label"] == "Test Metier"

    conn.close()


def test_no_cross_source_contamination():
    conn = _conn()
    conn.execute(
        "INSERT INTO dim_rome_metier VALUES (?, ?, ?)",
        ("B5678", "BF Metier", "2026-01-01T00:00:00"),
    )
    payload = {"romeCode": "B5678"}
    conn.execute(
        "INSERT INTO fact_offers VALUES (?, ?, ?)",
        ("BF-1", "business_france", json.dumps(payload)),
    )
    conn.commit()

    ensure_link_table(conn)
    enrich_offers(conn)

    row = conn.execute(
        "SELECT * FROM offer_rome_link WHERE offer_id = 'BF-1'"
    ).fetchone()
    assert row is None

    conn.close()


def test_fact_offers_not_modified():
    conn = _conn()
    conn.execute(
        "INSERT INTO dim_rome_metier VALUES (?, ?, ?)",
        ("C1111", "Metier C", "2026-01-01T00:00:00"),
    )
    payload = {"romeCode": "C1111", "nested": {"x": 1}}
    conn.execute(
        "INSERT INTO fact_offers VALUES (?, ?, ?)",
        ("FT-5", "france_travail", json.dumps(payload)),
    )
    conn.commit()

    before = conn.execute(
        "SELECT id, source, payload_json FROM fact_offers WHERE id = 'FT-5'"
    ).fetchone()

    ensure_link_table(conn)
    enrich_offers(conn)

    after = conn.execute(
        "SELECT id, source, payload_json FROM fact_offers WHERE id = 'FT-5'"
    ).fetchone()

    assert before["id"] == after["id"]
    assert before["source"] == after["source"]
    assert before["payload_json"] == after["payload_json"]

    conn.close()
