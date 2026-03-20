"""
test_inbox_near_matches.py — compact near-match count in inbox list.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app
from api.routes import inbox as inbox_routes


@pytest.fixture
def client():
    return TestClient(app)


def _catalog_with_skill(label: str):
    return [
        {
            "id": "OFFER-1",
            "title": "Offer",
            "description": "Role",
            "skills": [label],
            "skills_display": [label],
            "source": "test",
            "is_vie": True,
        }
    ]


def test_inbox_near_match_count_present(client, monkeypatch):
    monkeypatch.setattr(inbox_routes, "_load_catalog_offers", lambda: _catalog_with_skill("deep learning"))
    monkeypatch.setattr(inbox_routes, "_load_decided_ids", lambda _: set())

    profile = {"skills": ["machine learning"]}
    resp = client.post("/inbox?domain_mode=all", json={
        "profile_id": "near-test",
        "profile": profile,
        "min_score": 0,
        "limit": 10,
        "explain": True,
    })
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert "near_match_count" in item
    assert item["near_match_count"] > 0


def test_inbox_near_match_count_absent_when_zero(client, monkeypatch):
    monkeypatch.setattr(inbox_routes, "_load_catalog_offers", lambda: _catalog_with_skill("accounting"))
    monkeypatch.setattr(inbox_routes, "_load_decided_ids", lambda _: set())

    profile = {"skills": ["machine learning"]}
    resp = client.post("/inbox?domain_mode=all", json={
        "profile_id": "near-test",
        "profile": profile,
        "min_score": 0,
        "limit": 10,
        "explain": True,
    })
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert "near_match_count" not in item or item["near_match_count"] in (0, None)
