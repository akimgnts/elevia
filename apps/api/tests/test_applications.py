"""
test_applications.py - Contract + integration tests for Applications Tracker V2.

Status values migrated: shortlisted→saved, dismissed→archived
New tests: user isolation, status history, prepare route, old-status rejection.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.utils import db as db_utils
from api.utils import auth_db
from api.utils.auth_security import hash_password
from api.routes import applications as applications_routes


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "offers.db"
    auth_path = tmp_path / "auth.db"
    monkeypatch.setattr(db_utils, "DB_PATH", db_path)
    monkeypatch.setattr(auth_db, "DB_PATH", auth_path)
    monkeypatch.setattr(applications_routes, "get_connection", db_utils.get_connection)
    db_utils._initialized = False
    yield


@pytest.fixture
def authenticated_client(client):
    auth_db.upsert_user(
        email="admin@elevia.fr",
        password_hash=hash_password("secret123"),
        role="admin",
    )
    login_resp = client.post(
        "/auth/login",
        json={"email": "admin@elevia.fr", "password": "secret123"},
    )
    assert login_resp.status_code == 200
    return client


# ---------------------------------------------------------------------------
# Existing CRUD tests (status values migrated to new enum)
# ---------------------------------------------------------------------------

def test_create_application(authenticated_client, monkeypatch):
    monkeypatch.setattr(applications_routes, "_utc_now", lambda: "2026-01-30T10:00:00Z")
    resp = authenticated_client.post("/applications", json={
        "offer_id": "offer-1",
        "status": "saved",
        "note": "First pass",
        "next_follow_up_date": "2026-02-01",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["offer_id"] == "offer-1"
    assert data["status"] == "saved"
    assert data["note"] == "First pass"
    assert data["next_follow_up_date"] == "2026-02-01"
    assert data["created_at"] == "2026-01-30T10:00:00Z"
    assert data["updated_at"] == "2026-01-30T10:00:00Z"


def test_upsert_updates_fields_and_updated_at(authenticated_client, monkeypatch):
    times = ["2026-01-30T10:00:00Z", "2026-01-30T11:00:00Z"]
    monkeypatch.setattr(applications_routes, "_utc_now", lambda: times.pop(0))

    resp1 = authenticated_client.post("/applications", json={
        "offer_id": "offer-2",
        "status": "applied",
        "note": "Initial",
        "next_follow_up_date": "2026-02-02",
    })
    assert resp1.status_code == 201

    resp2 = authenticated_client.post("/applications", json={
        "offer_id": "offer-2",
        "status": "archived",
        "note": "Updated",
        "next_follow_up_date": "2026-02-05",
    })
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["status"] == "archived"
    assert data["note"] == "Updated"
    assert data["next_follow_up_date"] == "2026-02-05"
    assert data["updated_at"] == "2026-01-30T11:00:00Z"


def test_list_sorted_by_updated_at_desc(authenticated_client, monkeypatch):
    times = [
        "2026-01-30T09:00:00Z",
        "2026-01-30T10:00:00Z",
        "2026-01-30T11:00:00Z",
    ]
    monkeypatch.setattr(applications_routes, "_utc_now", lambda: times.pop(0))

    authenticated_client.post("/applications", json={"offer_id": "offer-3", "status": "saved"})
    authenticated_client.post("/applications", json={"offer_id": "offer-4", "status": "applied"})
    authenticated_client.patch("/applications/offer-3", json={"note": "bumped"})

    resp = authenticated_client.get("/applications")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["offer_id"] == "offer-3"
    assert items[1]["offer_id"] == "offer-4"


def test_get_missing_returns_404(authenticated_client):
    resp = authenticated_client.get("/applications/missing")
    assert resp.status_code == 404


def test_patch_partial_update(authenticated_client, monkeypatch):
    monkeypatch.setattr(applications_routes, "_utc_now", lambda: "2026-01-30T12:00:00Z")
    authenticated_client.post("/applications", json={"offer_id": "offer-5", "status": "saved"})

    monkeypatch.setattr(applications_routes, "_utc_now", lambda: "2026-01-30T12:30:00Z")
    resp = authenticated_client.patch("/applications/offer-5", json={
        "note": "Updated note",
        "next_follow_up_date": "2026-02-10",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["note"] == "Updated note"
    assert data["next_follow_up_date"] == "2026-02-10"
    assert data["updated_at"] == "2026-01-30T12:30:00Z"


def test_delete_application(authenticated_client):
    authenticated_client.post("/applications", json={"offer_id": "offer-6", "status": "applied"})
    resp = authenticated_client.delete("/applications/offer-6")
    assert resp.status_code == 204
    assert authenticated_client.get("/applications/offer-6").status_code == 404


def test_invalid_status_returns_422(authenticated_client):
    resp = authenticated_client.post("/applications", json={
        "offer_id": "offer-7",
        "status": "invalid",
    })
    assert resp.status_code == 422


def test_invalid_date_returns_400(authenticated_client):
    resp = authenticated_client.post("/applications", json={
        "offer_id": "offer-8",
        "status": "saved",
        "next_follow_up_date": "2026/02/01",
    })
    assert resp.status_code == 400


def test_anonymous_application_flow_and_offer_metadata(client):
    conn = db_utils.get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_offers (
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
        )
        """
    )
    conn.execute(
        """
        INSERT INTO fact_offers (
            id, source, title, description, company, city, country,
            publication_date, contract_duration, start_date, payload_json, last_updated
        ) VALUES (?, 'business_france', ?, 'desc', ?, ?, ?, NULL, NULL, NULL, '{}', ?)
        """,
        (
            "offer-meta-1",
            "Charge de clientele",
            "ACME",
            "Paris",
            "France",
            "2026-01-30T10:00:00Z",
        ),
    )
    conn.commit()
    conn.close()

    create_resp = client.post("/applications", json={"offer_id": "offer-meta-1", "status": "saved"})
    assert create_resp.status_code == 201
    data = create_resp.json()
    assert data["offer_title"] == "Charge de clientele"
    assert data["offer_company"] == "ACME"
    assert data["offer_city"] == "Paris"
    assert data["offer_country"] == "France"

    list_resp = client.get("/applications")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["offer_id"] == "offer-meta-1"


# ---------------------------------------------------------------------------
# New V2 tests
# ---------------------------------------------------------------------------

def test_new_status_values_valid(authenticated_client):
    """All 8 new status values must be accepted by the API."""
    for i, status in enumerate(
        ["saved", "cv_ready", "applied", "follow_up", "interview", "rejected", "won", "archived"]
    ):
        resp = authenticated_client.post("/applications", json={
            "offer_id": f"offer-status-{i}",
            "status": status,
        })
        assert resp.status_code in (200, 201), f"status={status} returned {resp.status_code}"
        assert resp.json()["status"] == status


def test_old_status_values_rejected(authenticated_client):
    """Old status values shortlisted/dismissed must now be rejected (422)."""
    for old_status in ["shortlisted", "dismissed"]:
        resp = authenticated_client.post("/applications", json={
            "offer_id": f"offer-old-{old_status}",
            "status": old_status,
        })
        assert resp.status_code == 422, f"Expected 422 for old status '{old_status}', got {resp.status_code}"


def test_user_isolation(client, monkeypatch):
    """User A's applications must not be visible to user B."""
    monkeypatch.setattr(db_utils, "DB_PATH", db_utils.DB_PATH)  # already set by autouse fixture

    # Create user A
    auth_db.upsert_user(
        email="alice@elevia.fr",
        password_hash=hash_password("pw_alice_123"),
        role="admin",
    )
    # Create user B
    auth_db.upsert_user(
        email="bob@elevia.fr",
        password_hash=hash_password("pw_bob_456"),
        role="admin",
    )

    # User A logs in and creates an application
    login_a = client.post("/auth/login", json={"email": "alice@elevia.fr", "password": "pw_alice_123"})
    assert login_a.status_code == 200
    client_a = client  # cookies set on the shared TestClient

    client_a.post("/applications", json={"offer_id": "offer-alice-only", "status": "saved"})

    # User B logs in (overwrites cookie in the shared client)
    # Use a fresh TestClient so we don't share the session cookie
    client_b = TestClient(app)
    monkeypatch.setattr(db_utils, "DB_PATH", db_utils.DB_PATH)
    login_b = client_b.post("/auth/login", json={"email": "bob@elevia.fr", "password": "pw_bob_456"})
    assert login_b.status_code == 200

    # User B should see an empty list
    list_b = client_b.get("/applications")
    assert list_b.status_code == 200
    assert list_b.json()["items"] == []

    # User B should get 404 on user A's specific offer
    get_b = client_b.get("/applications/offer-alice-only")
    assert get_b.status_code == 404


def test_status_history_on_upsert(authenticated_client):
    """POST (upsert) with a different status must write a history row."""
    authenticated_client.post("/applications", json={"offer_id": "offer-hist-1", "status": "saved"})
    authenticated_client.post("/applications", json={"offer_id": "offer-hist-1", "status": "applied"})

    resp = authenticated_client.get("/applications/offer-hist-1/history")
    assert resp.status_code == 200
    items = resp.json()["items"]
    # First upsert: None → saved; second upsert: saved → applied
    assert len(items) == 2
    assert items[0]["from_status"] is None
    assert items[0]["to_status"] == "saved"
    assert items[1]["from_status"] == "saved"
    assert items[1]["to_status"] == "applied"


def test_status_history_on_patch(authenticated_client):
    """PATCH with a new status must write a history row."""
    authenticated_client.post("/applications", json={"offer_id": "offer-hist-2", "status": "saved"})
    authenticated_client.patch("/applications/offer-hist-2", json={"status": "cv_ready"})
    authenticated_client.patch("/applications/offer-hist-2", json={"status": "applied"})

    resp = authenticated_client.get("/applications/offer-hist-2/history")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 3  # None→saved, saved→cv_ready, cv_ready→applied
    statuses = [(i["from_status"], i["to_status"]) for i in items]
    assert statuses == [
        (None, "saved"),
        ("saved", "cv_ready"),
        ("cv_ready", "applied"),
    ]


def test_history_no_duplicate_on_same_status_patch(authenticated_client):
    """PATCH with the same status must NOT write an extra history row."""
    authenticated_client.post("/applications", json={"offer_id": "offer-hist-3", "status": "saved"})
    authenticated_client.patch("/applications/offer-hist-3", json={"status": "saved"})

    resp = authenticated_client.get("/applications/offer-hist-3/history")
    items = resp.json()["items"]
    assert len(items) == 1  # only the initial creation


def test_history_404_for_missing_application(authenticated_client):
    resp = authenticated_client.get("/applications/does-not-exist/history")
    assert resp.status_code == 404


def test_prepare_creates_run_and_transitions_status(authenticated_client, monkeypatch):
    """
    POST /applications/{offer_id}/prepare must:
    - create an apply_pack_runs row
    - transition status saved → cv_ready
    - attach cv_cache_key to the application
    """
    # Create the application in saved state
    authenticated_client.post("/applications", json={"offer_id": "offer-prep-1", "status": "saved"})

    # Mock generate_cv so we don't need a real offer in the DB
    mock_cv_payload = MagicMock()
    monkeypatch.setattr(applications_routes, "auth_db", auth_db)

    # Patch the lazy imports inside the prepare route by replacing the module-level imports
    import documents.cv_generator as cv_gen_mod
    import documents.cache as cache_mod
    import documents.schemas as schemas_mod

    monkeypatch.setattr(cv_gen_mod, "generate_cv", lambda req: mock_cv_payload)
    monkeypatch.setattr(cv_gen_mod, "_profile_fingerprint", lambda profile: "test-fingerprint")
    monkeypatch.setattr(cache_mod, "make_cache_key", lambda fp, oid, pv: "test-cache-key")

    # Provide a profile so auth_db.get_profile is not needed
    resp = authenticated_client.post(
        "/applications/offer-prep-1/prepare",
        json={"profile": {"name": "Test User", "skills": ["Python"]}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["status"] == "cv_ready"
    assert data["cv_cache_key"] == "test-cache-key"
    assert data["run_id"]  # non-empty

    # Verify application status updated
    app_resp = authenticated_client.get("/applications/offer-prep-1")
    assert app_resp.json()["status"] == "cv_ready"
    assert app_resp.json()["current_cv_cache_key"] == "test-cache-key"

    # Verify apply_pack_runs row exists
    conn = db_utils.get_connection()
    run = conn.execute(
        "SELECT * FROM apply_pack_runs WHERE offer_id = ?", ("offer-prep-1",)
    ).fetchone()
    conn.close()
    assert run is not None
    assert run["cv_cache_key"] == "test-cache-key"


def test_prepare_404_for_unknown_offer(authenticated_client, monkeypatch):
    """prepare must return 404 when generate_cv raises ValueError (offer not in DB)."""
    authenticated_client.post("/applications", json={"offer_id": "offer-unknown", "status": "saved"})

    import documents.cv_generator as cv_gen_mod

    def _raise_not_found(req):
        raise ValueError("Offer not found")

    monkeypatch.setattr(cv_gen_mod, "generate_cv", _raise_not_found)
    monkeypatch.setattr(cv_gen_mod, "_profile_fingerprint", lambda p: "fp")

    resp = authenticated_client.post(
        "/applications/offer-unknown/prepare",
        json={"profile": {"name": "Test", "skills": []}},
    )
    assert resp.status_code == 404


def test_prepare_no_profile_returns_400(authenticated_client):
    """prepare with no profile in body and no stored profile must return 400."""
    # Don't create an auth profile — the test user has none
    authenticated_client.post("/applications", json={"offer_id": "offer-noprofile", "status": "saved"})

    resp = authenticated_client.post("/applications/offer-noprofile/prepare", json={})
    assert resp.status_code == 400


def test_prepare_preserves_status_if_not_saved(authenticated_client, monkeypatch):
    """If application is already past 'saved', prepare must not downgrade the status."""
    authenticated_client.post("/applications", json={"offer_id": "offer-prep-2", "status": "applied"})

    import documents.cv_generator as cv_gen_mod
    import documents.cache as cache_mod

    monkeypatch.setattr(cv_gen_mod, "generate_cv", lambda req: MagicMock())
    monkeypatch.setattr(cv_gen_mod, "_profile_fingerprint", lambda p: "fp2")
    monkeypatch.setattr(cache_mod, "make_cache_key", lambda fp, oid, pv: "key2")

    resp = authenticated_client.post(
        "/applications/offer-prep-2/prepare",
        json={"profile": {"name": "User", "skills": []}},
    )
    assert resp.status_code == 200
    # Status should stay 'applied', not drop to 'cv_ready'
    assert resp.json()["status"] == "applied"


# ---------------------------------------------------------------------------
# Compat layer: POST /offers/{offer_id}/decision → application_tracker
# ---------------------------------------------------------------------------

def test_decision_compat_shortlisted_creates_saved(authenticated_client):
    """SHORTLISTED decision by authenticated user creates an application_tracker row with status=saved."""
    resp = authenticated_client.post(
        "/offers/offer-compat-1/decision",
        json={"profile_id": "any-profile", "status": "SHORTLISTED"},
    )
    assert resp.status_code == 200

    conn = db_utils.get_connection()
    row = conn.execute(
        "SELECT status, source FROM application_tracker WHERE offer_id = ?",
        ("offer-compat-1",),
    ).fetchone()
    conn.close()

    assert row is not None, "application_tracker row must be created for authenticated SHORTLISTED decision"
    assert row["status"] == "saved"
    assert row["source"] == "assisted"


def test_decision_compat_dismissed_creates_archived(authenticated_client):
    """DISMISSED decision by authenticated user creates an application_tracker row with status=archived."""
    resp = authenticated_client.post(
        "/offers/offer-compat-2/decision",
        json={"profile_id": "any-profile", "status": "DISMISSED"},
    )
    assert resp.status_code == 200

    conn = db_utils.get_connection()
    row = conn.execute(
        "SELECT status, source FROM application_tracker WHERE offer_id = ?",
        ("offer-compat-2",),
    ).fetchone()
    conn.close()

    assert row is not None, "application_tracker row must be created for authenticated DISMISSED decision"
    assert row["status"] == "archived"
    assert row["source"] == "assisted"


def test_decision_compat_unauthenticated_creates_anonymous_tracker_row(client):
    """Unauthenticated decision must still create an anonymous tracker row."""
    resp = client.post(
        "/offers/offer-compat-3/decision",
        json={"profile_id": "anon-profile", "status": "SHORTLISTED"},
    )
    assert resp.status_code == 200

    conn = db_utils.get_connection()
    row = conn.execute(
        "SELECT * FROM application_tracker WHERE offer_id = ?",
        ("offer-compat-3",),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["user_id"] == "__anonymous__"
    assert row["status"] == "saved"


# ---------------------------------------------------------------------------
# Prepare route: letter_cache_key traceability
# ---------------------------------------------------------------------------

def test_prepare_generates_letter_cache_key(authenticated_client, monkeypatch):
    """
    POST /applications/{offer_id}/prepare must:
    - generate a letter and store letter_cache_key in the response
    - write letter_cache_key to apply_pack_runs
    - write current_letter_cache_key to application_tracker
    """
    authenticated_client.post("/applications", json={"offer_id": "offer-letter-1", "status": "saved"})

    import documents.cv_generator as cv_gen_mod
    import documents.cover_letter_generator as letter_gen_mod
    import documents.cache as cache_mod

    mock_letter = MagicMock()

    monkeypatch.setattr(cv_gen_mod, "generate_cv", lambda req: MagicMock())
    monkeypatch.setattr(cv_gen_mod, "_profile_fingerprint", lambda p: "letter-fp")
    monkeypatch.setattr(cv_gen_mod, "_load_offer", lambda oid: {"title": "Data Analyst", "company": "Acme"})
    monkeypatch.setattr(
        letter_gen_mod,
        "generate_cover_letter",
        lambda **kw: (mock_letter, "preview"),
    )
    monkeypatch.setattr(cache_mod, "make_cache_key", lambda fp, oid, pv: "cv-key")
    monkeypatch.setattr(cache_mod, "make_letter_cache_key", lambda fp, oid, tv: "letter-key")
    monkeypatch.setattr(cache_mod, "cache_set", lambda **kw: True)

    resp = authenticated_client.post(
        "/applications/offer-letter-1/prepare",
        json={"profile": {"name": "Test", "skills": ["Python"]}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["cv_cache_key"] == "cv-key"
    assert data["letter_cache_key"] == "letter-key"
    assert data["status"] == "cv_ready"

    # Verify application_tracker.current_letter_cache_key
    app_resp = authenticated_client.get("/applications/offer-letter-1")
    assert app_resp.status_code == 200
    assert app_resp.json()["current_letter_cache_key"] == "letter-key"

    # Verify apply_pack_runs row
    conn = db_utils.get_connection()
    run = conn.execute(
        "SELECT cv_cache_key, letter_cache_key FROM apply_pack_runs WHERE offer_id = ?",
        ("offer-letter-1",),
    ).fetchone()
    conn.close()
    assert run is not None
    assert run["cv_cache_key"] == "cv-key"
    assert run["letter_cache_key"] == "letter-key"


# ---------------------------------------------------------------------------
# strategy_hint field (v2.1 — preparatory AI slot, not LLM-generated yet)
# ---------------------------------------------------------------------------

def test_strategy_hint_patch_and_roundtrip(authenticated_client):
    """strategy_hint can be set via PATCH and is returned in GET."""
    authenticated_client.post("/applications", json={"offer_id": "offer-hint-1", "status": "saved"})

    # Initially null
    resp = authenticated_client.get("/applications/offer-hint-1")
    assert resp.json()["strategy_hint"] is None

    # PATCH strategy_hint only
    patch_resp = authenticated_client.patch(
        "/applications/offer-hint-1",
        json={"strategy_hint": "Insister sur experience data pipeline en production"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["strategy_hint"] == "Insister sur experience data pipeline en production"

    # GET roundtrip
    get_resp = authenticated_client.get("/applications/offer-hint-1")
    assert get_resp.json()["strategy_hint"] == "Insister sur experience data pipeline en production"

    # Verify it appears in the list too
    list_resp = authenticated_client.get("/applications")
    match = next((i for i in list_resp.json()["items"] if i["offer_id"] == "offer-hint-1"), None)
    assert match is not None
    assert match["strategy_hint"] == "Insister sur experience data pipeline en production"


# ---------------------------------------------------------------------------
# PATCH model_fields_set behaviour: clearing nullable fields
# ---------------------------------------------------------------------------

def test_patch_clears_follow_up_date(authenticated_client):
    """Sending next_follow_up_date: null via PATCH must clear the date (not keep old value)."""
    authenticated_client.post("/applications", json={
        "offer_id": "offer-clear-date",
        "status": "saved",
        "next_follow_up_date": "2026-12-01",
    })

    # Verify date is set
    resp = authenticated_client.get("/applications/offer-clear-date")
    assert resp.json()["next_follow_up_date"] == "2026-12-01"

    # Clear the date by sending explicit null
    patch_resp = authenticated_client.patch(
        "/applications/offer-clear-date",
        json={"next_follow_up_date": None},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["next_follow_up_date"] is None

    # GET confirms it's cleared
    get_resp = authenticated_client.get("/applications/offer-clear-date")
    assert get_resp.json()["next_follow_up_date"] is None


def test_patch_clears_note(authenticated_client):
    """Sending note: null via PATCH must clear the note."""
    authenticated_client.post("/applications", json={
        "offer_id": "offer-clear-note",
        "status": "saved",
        "note": "A note to clear",
    })
    patch_resp = authenticated_client.patch(
        "/applications/offer-clear-note",
        json={"note": None},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["note"] is None


def test_patch_omitted_fields_not_overwritten(authenticated_client):
    """Fields absent from PATCH body must not be overwritten."""
    authenticated_client.post("/applications", json={
        "offer_id": "offer-omit",
        "status": "saved",
        "note": "Keep me",
        "next_follow_up_date": "2026-11-01",
    })

    # PATCH only status — note and date must be preserved
    patch_resp = authenticated_client.patch(
        "/applications/offer-omit",
        json={"status": "applied"},
    )
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["status"] == "applied"
    assert data["note"] == "Keep me"
    assert data["next_follow_up_date"] == "2026-11-01"


def test_patch_empty_body_returns_400(authenticated_client):
    """PATCH with empty JSON body must return 400."""
    authenticated_client.post("/applications", json={"offer_id": "offer-empty-patch", "status": "saved"})
    resp = authenticated_client.patch("/applications/offer-empty-patch", json={})
    assert resp.status_code == 400
