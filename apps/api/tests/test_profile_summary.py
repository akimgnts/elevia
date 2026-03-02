from fastapi.testclient import TestClient

from api.main import app
from api.utils import profile_summary_store


def test_profile_summary_no_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_summary_store, "DB_PATH", tmp_path / "context.db")
    with TestClient(app) as c:
        resp = c.get("/profile/summary?profile_id=missing-profile")
        assert resp.status_code == 404
        data = resp.json()
        assert data["detail"]["status"] == "NO_PROFILE"


def test_profile_summary_from_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(profile_summary_store, "DB_PATH", tmp_path / "context.db")
    payload = {
        "cv_quality_level": "MED",
        "cv_quality_reasons": [],
        "top_skills": [{"uri": None, "label": "python"}],
        "tools": ["python"],
        "certifications": [],
        "education": [],
        "experiences": [],
        "cluster_hints": [],
        "last_updated": "2026-03-01T00:00:00Z",
    }
    profile_summary_store.store_profile_summary("profile-test-1", payload)

    with TestClient(app) as c:
        resp = c.get("/profile/summary?profile_id=profile-test-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cv_quality_level"] == "MED"
        assert data["top_skills"][0]["label"] == "python"

        resp2 = c.get("/profile/summary?profile_id=profile-test-1")
        assert resp2.status_code == 200
        assert resp2.json() == data
