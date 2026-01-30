"""
test_rome_offer_link.py - Tests for offer ↔ ROME link enrichment.

Uses an in-memory SQLite DB with minimal fact_offers + dim_rome_metier data.
No network calls.
"""

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

# ---------------------------------------------------------------------------
# Schema for test DB (fact_offers + dim_rome_metier + offer_rome_link)
# ---------------------------------------------------------------------------

FACT_OFFERS_SQL = """
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
    start_date TEXT,
    payload_json TEXT NOT NULL,
    last_updated TEXT NOT NULL
);
"""

DIM_ROME_SQL = """
CREATE TABLE dim_rome_metier (
    rome_code    TEXT PRIMARY KEY,
    rome_label   TEXT NOT NULL,
    last_updated TEXT NOT NULL
);
"""

LINK_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS offer_rome_link (
    offer_id   TEXT PRIMARY KEY,
    rome_code  TEXT,
    rome_label TEXT,
    linked_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_offer_rome_link_rome_code ON offer_rome_link(rome_code);
"""


def _make_ft_offer(offer_id: str, rome_code: str | None = None, rome_libelle: str | None = None) -> tuple:
    """Build a fact_offers row tuple for a France Travail offer."""
    payload = {"id": offer_id.replace("FT-", ""), "intitule": "Test"}
    if rome_code:
        payload["romeCode"] = rome_code
    if rome_libelle:
        payload["romeLibelle"] = rome_libelle
    return (
        offer_id, "france_travail", "Test", "Desc", None, None, "France",
        None, None, None, json.dumps(payload, ensure_ascii=False), "2025-01-01",
    )


def _make_bf_offer(offer_id: str) -> tuple:
    return (
        offer_id, "business_france", "BF Test", "Desc", None, None, "Germany",
        None, None, None, json.dumps({"id": offer_id}), "2025-01-01",
    )


@pytest.fixture
def conn():
    """In-memory SQLite with fact_offers + dim_rome_metier + offer_rome_link."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(FACT_OFFERS_SQL)
    c.executescript(DIM_ROME_SQL)
    c.executescript(LINK_SCHEMA_SQL)

    # Seed dim_rome_metier
    c.execute("INSERT INTO dim_rome_metier VALUES ('M1607', 'Secrétaire', '2025-01-01')")
    c.execute("INSERT INTO dim_rome_metier VALUES ('G1803', 'Service en restauration', '2025-01-01')")

    # Seed fact_offers
    c.execute("INSERT INTO fact_offers VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              _make_ft_offer("FT-001", "M1607", "Secrétaire"))
    c.execute("INSERT INTO fact_offers VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              _make_ft_offer("FT-002", "G1803", "Serveur"))
    c.execute("INSERT INTO fact_offers VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              _make_ft_offer("FT-003"))  # No rome code
    c.execute("INSERT INTO fact_offers VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              _make_ft_offer("FT-004", "XXXXX"))  # Invalid rome code
    c.execute("INSERT INTO fact_offers VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              _make_bf_offer("BF-001"))  # Business France — should be ignored

    c.commit()
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Import enrichment logic
# ---------------------------------------------------------------------------

from enrich_offers_with_rome import extract_rome_code, ensure_schema, ROME_CODE_RE


def _run_enrichment(conn):
    """Simulate the enrichment loop from the script."""
    import json as _json
    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat()

    metiers = {}
    for r in conn.execute("SELECT rome_code, rome_label FROM dim_rome_metier").fetchall():
        metiers[r["rome_code"]] = r["rome_label"]

    rows = conn.execute(
        "SELECT id, payload_json FROM fact_offers WHERE source = 'france_travail'"
    ).fetchall()

    for row in rows:
        offer_id = row["id"]
        try:
            payload = _json.loads(row["payload_json"])
        except (_json.JSONDecodeError, TypeError):
            conn.execute(
                """INSERT INTO offer_rome_link (offer_id, rome_code, rome_label, linked_at)
                   VALUES (?, NULL, NULL, ?)
                   ON CONFLICT(offer_id) DO UPDATE SET
                       rome_code=excluded.rome_code, rome_label=excluded.rome_label, linked_at=excluded.linked_at""",
                (offer_id, now_iso),
            )
            continue

        code = extract_rome_code(payload)

        if code and code in metiers:
            conn.execute(
                """INSERT INTO offer_rome_link (offer_id, rome_code, rome_label, linked_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(offer_id) DO UPDATE SET
                       rome_code=excluded.rome_code, rome_label=excluded.rome_label, linked_at=excluded.linked_at""",
                (offer_id, code, metiers[code], now_iso),
            )
        elif code:
            fallback = (payload.get("romeLibelle") or "").strip() or None
            conn.execute(
                """INSERT INTO offer_rome_link (offer_id, rome_code, rome_label, linked_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(offer_id) DO UPDATE SET
                       rome_code=excluded.rome_code, rome_label=excluded.rome_label, linked_at=excluded.linked_at""",
                (offer_id, code, fallback, now_iso),
            )
        else:
            conn.execute(
                """INSERT INTO offer_rome_link (offer_id, rome_code, rome_label, linked_at)
                   VALUES (?, NULL, NULL, ?)
                   ON CONFLICT(offer_id) DO UPDATE SET
                       rome_code=excluded.rome_code, rome_label=excluded.rome_label, linked_at=excluded.linked_at""",
                (offer_id, now_iso),
            )
    conn.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_table_creation(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "offer_rome_link" in tables


def test_link_valid_rome_code(conn):
    _run_enrichment(conn)
    row = conn.execute("SELECT * FROM offer_rome_link WHERE offer_id='FT-001'").fetchone()
    assert row["rome_code"] == "M1607"
    assert row["rome_label"] == "Secrétaire"
    assert row["linked_at"] is not None


def test_link_second_valid_code(conn):
    _run_enrichment(conn)
    row = conn.execute("SELECT * FROM offer_rome_link WHERE offer_id='FT-002'").fetchone()
    assert row["rome_code"] == "G1803"
    assert row["rome_label"] == "Service en restauration"


def test_null_when_no_rome_code(conn):
    _run_enrichment(conn)
    row = conn.execute("SELECT * FROM offer_rome_link WHERE offer_id='FT-003'").fetchone()
    assert row["rome_code"] is None
    assert row["rome_label"] is None


def test_invalid_code_yields_null(conn):
    """'XXXXX' doesn't match ^[A-Z]\\d{4}$, so should be NULL."""
    _run_enrichment(conn)
    row = conn.execute("SELECT * FROM offer_rome_link WHERE offer_id='FT-004'").fetchone()
    assert row["rome_code"] is None


def test_ignores_bf_offers(conn):
    _run_enrichment(conn)
    row = conn.execute("SELECT * FROM offer_rome_link WHERE offer_id='BF-001'").fetchone()
    assert row is None


def test_idempotent(conn):
    _run_enrichment(conn)
    _run_enrichment(conn)
    count = conn.execute("SELECT COUNT(*) FROM offer_rome_link").fetchone()[0]
    # Should have exactly 4 FT offers (not duplicated)
    assert count == 4


def test_fact_offers_unchanged(conn):
    """fact_offers must not be modified by enrichment."""
    before = conn.execute("SELECT COUNT(*) FROM fact_offers").fetchone()[0]
    payloads_before = {
        r["id"]: r["payload_json"]
        for r in conn.execute("SELECT id, payload_json FROM fact_offers").fetchall()
    }
    _run_enrichment(conn)
    after = conn.execute("SELECT COUNT(*) FROM fact_offers").fetchone()[0]
    payloads_after = {
        r["id"]: r["payload_json"]
        for r in conn.execute("SELECT id, payload_json FROM fact_offers").fetchall()
    }
    assert before == after
    assert payloads_before == payloads_after


def test_extract_rome_code_from_payload():
    assert extract_rome_code({"romeCode": "M1607"}) == "M1607"
    assert extract_rome_code({"codeRome": "G1803"}) == "G1803"
    assert extract_rome_code({"romeCode": "INVALID"}) is None
    assert extract_rome_code({}) is None
    assert extract_rome_code({"romeCode": ""}) is None
    assert extract_rome_code({"romeCode": "m1607"}) is None  # lowercase


def test_rome_link_util(conn):
    """Test the read utility function."""
    from api.utils.rome_link import get_offer_rome_link

    # Before enrichment
    assert get_offer_rome_link(conn, "FT-001") is None

    _run_enrichment(conn)

    link = get_offer_rome_link(conn, "FT-001")
    assert link is not None
    assert link["rome_code"] == "M1607"

    # Non-existent offer
    assert get_offer_rome_link(conn, "NOPE") is None
