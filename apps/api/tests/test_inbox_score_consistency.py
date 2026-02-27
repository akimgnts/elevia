"""
QA — Inbox score consistency + description fields.
"""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(scope="module")
def client():
    import os
    os.environ.setdefault("ELEVIA_DEV_TOOLS", "1")
    from api.main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def profile_demo():
    fixtures_path = Path(__file__).parent.parent / "fixtures" / "profile_demo.json"
    with open(fixtures_path) as f:
        return json.load(f)


def _post_inbox(client, profile, explain: bool = True, min_score: int = 0, limit: int = 5):
    return client.post("/inbox", json={
        "profile_id": "score-consistency",
        "profile": profile,
        "min_score": min_score,
        "limit": limit,
        "explain": explain,
    })


def test_inbox_description_and_scores_present(client, profile_demo):
    resp = _post_inbox(client, profile_demo, explain=True)
    assert resp.status_code == 200
    data = resp.json()
    for item in data.get("items", []):
        assert "description" in item
        assert "description_snippet" in item
        assert "score_pct" in item
        assert "score_raw" in item
        if item["description"] is not None:
            assert isinstance(item["description"], str)
        if item["description_snippet"] is not None:
            assert isinstance(item["description_snippet"], str)
        assert isinstance(item["score_pct"], int)
        assert isinstance(item["score_raw"], (int, float))
        assert 0.0 <= float(item["score_raw"]) <= 1.0


def test_description_snippet_capped(client, profile_demo):
    resp = _post_inbox(client, profile_demo, explain=True)
    assert resp.status_code == 200
    data = resp.json()
    for item in data.get("items", []):
        snippet = item.get("description_snippet") or ""
        assert len(snippet) <= 320


def test_score_pct_matches_score(client, profile_demo):
    resp = _post_inbox(client, profile_demo, explain=True)
    assert resp.status_code == 200
    data = resp.json()
    for item in data.get("items", []):
        assert item["score_pct"] == item["score"]


def test_score_raw_matches_breakdown_total(client, profile_demo):
    resp = _post_inbox(client, profile_demo, explain=True)
    assert resp.status_code == 200
    data = resp.json()
    for item in data.get("items", []):
        explain = item.get("explain")
        if not explain:
            continue
        total = explain["breakdown"]["total"]
        score_raw = float(item["score_raw"]) * 100.0
        # total is rounded to 0.1, tolerate small rounding drift
        assert abs(score_raw - total) <= 1.0


def test_score_100_implies_no_missing_display(client, profile_demo):
    resp = _post_inbox(client, profile_demo, explain=True)
    assert resp.status_code == 200
    data = resp.json()
    for item in data.get("items", []):
        if item["score_pct"] == 100 and item.get("explain"):
            missing = item["explain"]["missing_display"]
            assert len(missing) == 0, "score_pct==100 but missing_display is not empty"
