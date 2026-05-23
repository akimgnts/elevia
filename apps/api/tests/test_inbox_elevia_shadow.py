from __future__ import annotations

import json
import os
import sys
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


def _post_inbox(client, profile_demo, *, debug_value: str, query: str = ""):
    prev = os.environ.get("ELEVIA_DEBUG_MATCHING")
    os.environ["ELEVIA_DEBUG_MATCHING"] = debug_value
    try:
        url = "/inbox"
        if query:
            url = f"{url}?{query}"
        resp = client.post(
            url,
            json={
                "profile_id": "elevia-shadow-test",
                "profile": profile_demo,
                "min_score": 0,
                "limit": 10,
            },
        )
    finally:
        if prev is None:
            os.environ.pop("ELEVIA_DEBUG_MATCHING", None)
        else:
            os.environ["ELEVIA_DEBUG_MATCHING"] = prev
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_debug_off_keeps_payload_unchanged_for_elevia_shadow_fields(client, profile_demo):
    data = _post_inbox(client, profile_demo, debug_value="0")
    items = data.get("items", [])
    if not items:
        pytest.skip("no items returned by demo profile in this environment")

    assert "profile_elevia_cluster" not in (data.get("meta") or {})
    for item in items:
        assert "offer_elevia_clusters" not in item
        assert "cluster_alignment" not in item
        assert "cluster_confidence" not in item
        assert "cluster_evidence" not in item


def test_debug_on_adds_elevia_shadow_fields_without_touching_score_or_order(client, profile_demo, monkeypatch):
    from api.routes import inbox as inbox_routes

    calls: list[dict] = []

    def _fake_infer(input_data):
        calls.append(input_data)
        if len(calls) == 1:
            return {
                "primary_cluster": "FINANCE_CONTROL",
                "candidate_clusters": [{"cluster": "FINANCE_CONTROL", "score": 9.0, "eligible": True}],
                "confidence": 0.82,
                "evidence": {"primary_cluster": "FINANCE_CONTROL"},
            }
        return {
            "primary_cluster": "BI_ANALYTICS",
            "candidate_clusters": [{"cluster": "BI_ANALYTICS", "score": 8.0, "eligible": True}],
            "confidence": 0.71,
            "evidence": {"primary_cluster": "BI_ANALYTICS"},
        }

    monkeypatch.setattr(inbox_routes, "infer_elevia_metier", _fake_infer)

    off = _post_inbox(client, profile_demo, debug_value="0")
    on = _post_inbox(client, profile_demo, debug_value="1")

    if not off.get("items") or not on.get("items"):
        pytest.skip("no items returned by demo profile in this environment")

    assert [item["offer_id"] for item in off["items"]] == [item["offer_id"] for item in on["items"]]
    assert [item["score"] for item in off["items"]] == [item["score"] for item in on["items"]]

    assert on["meta"]["profile_elevia_cluster"]["primary_cluster"] == "FINANCE_CONTROL"
    assert len(calls) == 1 + len(on["items"])

    sample = on["items"][0]
    assert sample["offer_elevia_clusters"]["primary_cluster"] == "BI_ANALYTICS"
    assert sample["cluster_alignment"]["status"] == "mismatch"
    assert sample["cluster_confidence"]["profile"] == 0.82
    assert sample["cluster_confidence"]["offer"] == 0.71
    assert sample["cluster_evidence"]["profile"]["primary_cluster"] == "FINANCE_CONTROL"


def test_filtered_inbox_pagination_is_identical_with_shadow_mode(client, profile_demo, monkeypatch):
    from api.routes import inbox as inbox_routes

    def _fake_infer(_input_data):
        return {
            "primary_cluster": "ENGINEERING_BUILD_RUN",
            "candidate_clusters": [{"cluster": "ENGINEERING_BUILD_RUN", "score": 7.0, "eligible": True}],
            "confidence": 0.66,
            "evidence": {"primary_cluster": "ENGINEERING_BUILD_RUN"},
        }

    monkeypatch.setattr(inbox_routes, "infer_elevia_metier", _fake_infer)

    query = "domain_mode=all&page=1&page_size=5"
    off = _post_inbox(client, profile_demo, debug_value="0", query=query)
    on = _post_inbox(client, profile_demo, debug_value="1", query=query)

    if not off.get("items") or not on.get("items"):
        pytest.skip("no items returned by demo profile in this environment")

    assert off["page"] == on["page"] == 1
    assert off["page_size"] == on["page_size"] == 5
    assert off["total_estimate"] == on["total_estimate"]
    assert [item["offer_id"] for item in off["items"]] == [item["offer_id"] for item in on["items"]]
    assert [item["score"] for item in off["items"]] == [item["score"] for item in on["items"]]
    assert on["items"][0]["cluster_alignment"]["status"] == "match"
