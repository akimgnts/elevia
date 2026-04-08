import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app
from api.routes import applications as applications_routes
from api.utils import auth_db, db as db_utils
from api.utils.auth_security import hash_password


@pytest.fixture
def client(tmp_path, monkeypatch):
    auth_path = tmp_path / "auth.db"
    offers_path = tmp_path / "offers.db"

    monkeypatch.setattr(auth_db, "DB_PATH", auth_path)
    monkeypatch.setattr(db_utils, "DB_PATH", offers_path)
    monkeypatch.setattr(applications_routes, "get_connection", db_utils.get_connection)
    db_utils._initialized = False

    return TestClient(app)


def test_login_requires_seeded_admin(client):
    resp = client.post("/auth/login", json={"email": "admin@elevia.fr", "password": "secret123"})
    assert resp.status_code == 503


def test_protected_route_bypasses_when_auth_not_bootstrapped(client):
    resp = client.get("/applications")
    assert resp.status_code == 401
    assert resp.json()["detail"]["message"] == "Auth not initialized"


def test_login_me_logout_flow_and_route_protection(client):
    auth_db.upsert_user(
        email="admin@elevia.fr",
        password_hash=hash_password("secret123"),
        role="admin",
    )

    unauthorized = client.get("/applications")
    assert unauthorized.status_code == 401

    login_resp = client.post(
        "/auth/login",
        json={"email": "admin@elevia.fr", "password": "secret123"},
    )
    assert login_resp.status_code == 200
    assert "elevia_session" in login_resp.cookies

    me_resp = client.get("/auth/me")
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["authenticated"] is True
    assert me_data["auth_enabled"] is True
    assert me_data["user"]["email"] == "admin@elevia.fr"

    protected = client.get("/applications")
    assert protected.status_code == 200
    assert protected.json() == {"items": []}

    save_profile = client.put("/auth/profile", json={"profile": {"skills": ["sql", "power bi"]}})
    assert save_profile.status_code == 200

    get_profile = client.get("/auth/profile")
    assert get_profile.status_code == 200
    assert get_profile.json()["profile"] == {"skills": ["sql", "power bi"]}

    logout_resp = client.post("/auth/logout")
    assert logout_resp.status_code == 204

    revoked = client.get("/applications")
    assert revoked.status_code == 401
