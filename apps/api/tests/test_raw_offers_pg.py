import sys
from pathlib import Path

API_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(API_ROOT / "src"))

from api.utils import raw_offers_pg


class _FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    def __init__(self):
        self.executed = []
        self.commit_calls = 0
        self.closed = False

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.commit_calls += 1

    def close(self):
        self.closed = True


def test_build_external_id_france_travail_uses_native_id():
    payload = {"id": 12345, "intitule": "Data Analyst"}
    assert raw_offers_pg.build_external_id("france_travail", payload) == "12345"


def test_build_external_id_business_france_prefers_native_keys():
    payload = {"id": 238429, "reference": "VIE238429", "missionTitle": "Analyst"}
    assert raw_offers_pg.build_external_id("business_france", payload) == "238429"


def test_build_external_id_falls_back_to_stable_hash():
    payload = {"title": "Fallback only", "company": "Test"}
    first = raw_offers_pg.build_external_id("business_france", payload)
    second = raw_offers_pg.build_external_id("business_france", payload)
    assert first == second
    assert len(first) == 40


def test_persist_raw_offers_with_connection_upserts_rows():
    conn = _FakeConn()

    result = raw_offers_pg.persist_raw_offers_with_connection(
        conn,
        "france_travail",
        [{"id": "FT-1", "title": "Offer 1"}],
        "2026-04-16T00:00:00+00:00",
    )

    assert result.attempted == 1
    assert result.persisted == 1
    assert conn.commit_calls == 1
    assert any("CREATE TABLE IF NOT EXISTS raw_offers" in sql for sql, _ in conn.executed)
    insert_calls = [entry for entry in conn.executed if "INSERT INTO raw_offers" in entry[0]]
    assert len(insert_calls) == 1
    _, params = insert_calls[0]
    assert params[0] == "france_travail"
    assert params[1] == "FT-1"


def test_persist_raw_offers_returns_clear_error_without_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = raw_offers_pg.persist_raw_offers(
        "france_travail",
        [{"id": "100"}],
        "2026-04-16T00:00:00+00:00",
    )
    assert result.persisted == 0
    assert result.error == "DATABASE_URL is not set"
