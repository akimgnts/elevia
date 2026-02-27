"""
QA — POST /inbox explain=True contract tests.

Covers:
- test_inbox_explain_returns_200
- test_inbox_explain_schema_contract     (explain block present + valid shape)
- test_inbox_explain_default_no_block    (explain=False → explain is null)
- test_inbox_explain_breakdown_values    (scores are floats, weights are ints)
- test_inbox_explain_lists_bounded       (display ≤ 6, full ≤ 30)
- test_inbox_explain_deterministic       (same inputs → same explain data)

Fast (<1s), no LLM, no external deps.
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
        "profile_id": "explain-test",
        "profile": profile,
        "min_score": min_score,
        "limit": limit,
        "explain": explain,
    })


# ── Basic contract ─────────────────────────────────────────────────────────────

def test_inbox_explain_returns_200(client, profile_demo):
    resp = _post_inbox(client, profile_demo, explain=True)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


def test_inbox_explain_schema_contract(client, profile_demo):
    """With explain=True, each item must have a valid explain block or null."""
    resp = _post_inbox(client, profile_demo, explain=True)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    items_with_explain = [i for i in data["items"] if i.get("explain") is not None]
    # If there are any items, at least some should have explain (when score > 0)
    for item in items_with_explain:
        ex = item["explain"]
        assert "matched_display" in ex
        assert "missing_display" in ex
        assert "matched_full" in ex
        assert "missing_full" in ex
        assert "breakdown" in ex
        bd = ex["breakdown"]
        assert "skills_score" in bd
        assert "skills_weight" in bd
        assert "language_score" in bd
        assert "language_weight" in bd
        assert "language_match" in bd
        assert "education_score" in bd
        assert "education_weight" in bd
        assert "education_match" in bd
        assert "country_score" in bd
        assert "country_weight" in bd
        assert "country_match" in bd
        assert "total" in bd


def test_inbox_explain_default_no_block(client, profile_demo):
    """With explain=False (default), explain field should be null."""
    resp = _post_inbox(client, profile_demo, explain=False)
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item.get("explain") is None, (
            f"explain should be null when explain=False, got: {item.get('explain')}"
        )


def test_inbox_explain_breakdown_values(client, profile_demo):
    """breakdown scores are floats, weights are ints matching expected values."""
    resp = _post_inbox(client, profile_demo, explain=True)
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        ex = item.get("explain")
        if ex is None:
            continue
        bd = ex["breakdown"]
        # Weights must be standard matching constants
        assert bd["skills_weight"] == 70
        assert bd["language_weight"] == 15
        assert bd["education_weight"] == 10
        assert bd["country_weight"] == 5
        # Scores must be non-negative floats
        assert isinstance(bd["skills_score"], (int, float)) and bd["skills_score"] >= 0
        assert isinstance(bd["language_score"], (int, float)) and bd["language_score"] >= 0
        assert isinstance(bd["education_score"], (int, float)) and bd["education_score"] >= 0
        assert isinstance(bd["country_score"], (int, float)) and bd["country_score"] >= 0
        assert isinstance(bd["total"], (int, float))
        # Boolean fields
        assert isinstance(bd["language_match"], bool)
        assert isinstance(bd["education_match"], bool)
        assert isinstance(bd["country_match"], bool)


def test_inbox_explain_lists_bounded(client, profile_demo):
    """matched_display/missing_display ≤ 6; matched_full/missing_full ≤ 30."""
    resp = _post_inbox(client, profile_demo, explain=True)
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        ex = item.get("explain")
        if ex is None:
            continue
        assert len(ex["matched_display"]) <= 6, (
            f"matched_display has {len(ex['matched_display'])} items (max 6)"
        )
        assert len(ex["missing_display"]) <= 6, (
            f"missing_display has {len(ex['missing_display'])} items (max 6)"
        )
        assert len(ex["matched_full"]) <= 30, (
            f"matched_full has {len(ex['matched_full'])} items (max 30)"
        )
        assert len(ex["missing_full"]) <= 30, (
            f"missing_full has {len(ex['missing_full'])} items (max 30)"
        )


def test_inbox_explain_skill_items_shape(client, profile_demo):
    """Each skill explain item has label (str) and weighted (bool)."""
    resp = _post_inbox(client, profile_demo, explain=True)
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        ex = item.get("explain")
        if ex is None:
            continue
        for skill in ex["matched_display"] + ex["missing_display"]:
            assert "label" in skill
            assert "weighted" in skill
            assert isinstance(skill["label"], str)
            assert isinstance(skill["weighted"], bool)


def test_inbox_explain_deterministic(client, profile_demo):
    """Same inputs → identical explain data (deterministic)."""
    r1 = _post_inbox(client, profile_demo, explain=True)
    r2 = _post_inbox(client, profile_demo, explain=True)
    assert r1.status_code == 200
    assert r2.status_code == 200
    items1 = {i["offer_id"]: i.get("explain") for i in r1.json()["items"]}
    items2 = {i["offer_id"]: i.get("explain") for i in r2.json()["items"]}
    assert items1 == items2, "explain data must be deterministic"


def test_inbox_explain_empty_profile(client):
    """Minimal profile with no skills → 200, all explain blocks are null or have empty lists."""
    resp = _post_inbox(client, {"id": "empty", "skills": []}, explain=True)
    assert resp.status_code == 200
    data = resp.json()
    # Should not crash; items may be empty or have explain=null (no skills matched)
    for item in data["items"]:
        ex = item.get("explain")
        if ex is not None:
            assert isinstance(ex["matched_display"], list)
            assert isinstance(ex["missing_display"], list)
