"""Shadow-mode integration tests: ELEVIA_FIT_SCORE_V2_SHADOW gate must not change ranking."""
from __future__ import annotations

import json
import os
import sys
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app  # noqa: E402
from api.utils.db import DB_PATH, get_connection  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def profile_demo():
    fixtures_path = Path(__file__).parent.parent / "fixtures" / "profile_demo.json"
    with open(fixtures_path) as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def _clean_decisions():
    if DB_PATH.exists():
        conn = get_connection()
        conn.execute("DELETE FROM offer_decisions")
        conn.commit()
        conn.close()
    yield


def _post_inbox(client, profile_demo, *, flag_value: str):
    prev = os.environ.get("ELEVIA_FIT_SCORE_V2_SHADOW")
    os.environ["ELEVIA_FIT_SCORE_V2_SHADOW"] = flag_value
    try:
        resp = client.post(
            "/inbox",
            json={
                "profile_id": "shadow-test",
                "profile": profile_demo,
                "min_score": 0,
                "limit": 20,
            },
        )
    finally:
        if prev is None:
            os.environ.pop("ELEVIA_FIT_SCORE_V2_SHADOW", None)
        else:
            os.environ["ELEVIA_FIT_SCORE_V2_SHADOW"] = prev
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_flag_off_no_fit_score_v2_fields(client, profile_demo):
    data = _post_inbox(client, profile_demo, flag_value="0")
    items = data.get("items", [])
    if not items:
        pytest.skip("no items returned by demo profile in this environment")
    for item in items:
        # Flag OFF: shadow helper does nothing — fit_score / preference_score / eligibility_status
        # remain at their defaults (None or unset by upstream).
        assert item.get("preference_score") is None
        assert item.get("eligibility_status") is None


def test_flag_on_populates_fit_score(client, profile_demo):
    data = _post_inbox(client, profile_demo, flag_value="1")
    items = data.get("items", [])
    if not items:
        pytest.skip("no items returned by demo profile in this environment")
    populated = [i for i in items if i.get("fit_score") is not None]
    # At least some eligible offers should produce fit_score (cannot guarantee 100%
    # because seed offers may legitimately fail eligibility).
    assert populated, "expected at least one item with shadow fit_score populated"


def test_flag_on_populates_eligibility_status(client, profile_demo):
    data = _post_inbox(client, profile_demo, flag_value="1")
    items = data.get("items", [])
    if not items:
        pytest.skip("no items returned by demo profile in this environment")
    with_status = [i for i in items if i.get("eligibility_status") is not None]
    assert with_status, "expected at least one item with eligibility_status populated"
    sample = with_status[0]["eligibility_status"]
    assert "ok" in sample
    assert "reasons" in sample


def test_flag_on_does_not_change_v1_score(client, profile_demo):
    """Critical invariant: item.score (V1) must be identical with flag ON vs OFF."""
    off = _post_inbox(client, profile_demo, flag_value="0")
    on = _post_inbox(client, profile_demo, flag_value="1")
    if not off.get("items") or not on.get("items"):
        pytest.skip("no items returned in this environment")
    by_id_off = {i["offer_id"]: i["score"] for i in off["items"]}
    by_id_on = {i["offer_id"]: i["score"] for i in on["items"]}
    common = set(by_id_off) & set(by_id_on)
    assert common, "no overlap between flag ON/OFF responses"
    for oid in common:
        assert by_id_off[oid] == by_id_on[oid], (
            f"V1 score changed for offer {oid}: off={by_id_off[oid]} on={by_id_on[oid]}"
        )


def test_flag_on_does_not_change_ordering(client, profile_demo):
    off = _post_inbox(client, profile_demo, flag_value="0")
    on = _post_inbox(client, profile_demo, flag_value="1")
    if not off.get("items") or not on.get("items"):
        pytest.skip("no items returned in this environment")
    order_off = [i["offer_id"] for i in off["items"]]
    order_on = [i["offer_id"] for i in on["items"]]
    assert order_off == order_on, "shadow flag must not change item ordering"


def test_shadow_failure_does_not_break_inbox(client, profile_demo, monkeypatch):
    """If the shadow helper raises, the response must still be 200."""
    from api.routes import inbox as inbox_routes

    def _broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(inbox_routes, "_apply_fit_score_v2_shadow", _broken)
    os.environ["ELEVIA_FIT_SCORE_V2_SHADOW"] = "1"
    try:
        resp = client.post(
            "/inbox",
            json={
                "profile_id": "shadow-fail-test",
                "profile": profile_demo,
                "min_score": 0,
                "limit": 5,
            },
        )
    finally:
        os.environ.pop("ELEVIA_FIT_SCORE_V2_SHADOW", None)
    assert resp.status_code == 200
