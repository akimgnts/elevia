from api.utils import profiles_db


def test_profiles_db_sqlite_fallback_roundtrip(tmp_path, monkeypatch):
    db_path = tmp_path / "offers.db"
    monkeypatch.setattr(profiles_db, "_SQLITE_DB_PATH", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    payload = {"id": "p1", "skills": ["python", "sql"], "career_profile": {"base_title": "Data Analyst"}}

    assert profiles_db.save_profile("p1", payload, user_id=None) is True
    stored = profiles_db.get_profile("p1")

    assert stored is not None
    assert stored["id"] == "p1"
    assert stored["skills"] == ["python", "sql"]
