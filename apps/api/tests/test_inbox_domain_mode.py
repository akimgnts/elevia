"""
Integration tests for inbox domain_mode gating.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def profile_demo():
    fixtures_path = Path(__file__).parent.parent / "fixtures" / "profile_demo.json"
    with open(fixtures_path) as f:
        return json.load(f)


def test_inbox_domain_mode_gating(client, profile_demo):
    resp = client.post(
        "/inbox",
        params={"domain_mode": "in_domain"},
        json={
            "profile_id": "test-user",
            "profile": profile_demo,
            "min_score": 0,
            "limit": 20,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    meta = data.get("meta") or {}
    items = data.get("items") or []

    if not items:
        pytest.skip("No offers returned for in_domain")

    profile_cluster = meta.get("profile_cluster")
    assert profile_cluster is not None
    assert meta.get("gating_mode") == "IN_DOMAIN"
    for item in items:
        assert item.get("offer_cluster") == profile_cluster

    resp_all = client.post(
        "/inbox",
        params={"domain_mode": "all"},
        json={
            "profile_id": "test-user",
            "profile": profile_demo,
            "min_score": 0,
            "limit": 20,
        },
    )
    assert resp_all.status_code == 200
    data_all = resp_all.json()
    assert data_all.get("meta", {}).get("gating_mode") == "OUT_OF_DOMAIN"
    assert len(data_all.get("items", [])) >= len(items)
