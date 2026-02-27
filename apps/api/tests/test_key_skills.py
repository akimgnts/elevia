"""
QA — POST /profile/key-skills endpoint tests.

Covers:
- test_key_skills_returns_200
- test_key_skills_schema_contract
- test_key_skills_deterministic_ordering
- test_key_skills_handles_empty_validated
- test_key_skills_graceful_fallback_no_idf   (IDF table empty → still 200)
- test_key_skills_max_12_key_skills
- test_key_skills_reason_values
- test_key_skills_rome_code_accepted

Fast (<1s), no LLM, no external deps.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

TECH_SKILLS = [
    {"uri": "http://data.europa.eu/esco/skill/1", "label": "Python"},
    {"uri": "http://data.europa.eu/esco/skill/2", "label": "SQL"},
    {"uri": "http://data.europa.eu/esco/skill/3", "label": "Docker"},
    {"uri": "http://data.europa.eu/esco/skill/4", "label": "Git"},
    {"uri": "http://data.europa.eu/esco/skill/5", "label": "Pandas"},
    {"uri": "http://data.europa.eu/esco/skill/6", "label": "Machine learning"},
    {"uri": "http://data.europa.eu/esco/skill/7", "label": "ETL"},
    {"uri": "http://data.europa.eu/esco/skill/8", "label": "Statistics"},
    {"uri": "http://data.europa.eu/esco/skill/9", "label": "Data analysis"},
    {"uri": "http://data.europa.eu/esco/skill/10", "label": "Excel"},
    {"uri": "http://data.europa.eu/esco/skill/11", "label": "Power BI"},
    {"uri": "http://data.europa.eu/esco/skill/12", "label": "Tableau"},
    {"uri": "http://data.europa.eu/esco/skill/13", "label": "Airflow"},
    {"uri": "http://data.europa.eu/esco/skill/14", "label": "dbt"},
    {"uri": "http://data.europa.eu/esco/skill/15", "label": "Spark"},
]


@pytest.fixture(scope="module")
def client():
    import os
    os.environ.setdefault("ELEVIA_DEV_TOOLS", "1")
    from api.main import app
    return TestClient(app)


def _post(client, validated_items=None, rome_code=None):
    payload = {"validated_items": TECH_SKILLS if validated_items is None else validated_items}
    if rome_code:
        payload["rome_code"] = rome_code
    return client.post("/profile/key-skills", json=payload)


# ── Basic contract ─────────────────────────────────────────────────────────────

def test_key_skills_returns_200(client):
    resp = _post(client)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


def test_key_skills_schema_contract(client):
    resp = _post(client)
    assert resp.status_code == 200
    body = resp.json()
    assert "key_skills" in body
    assert "all_skills_ranked" in body
    assert isinstance(body["key_skills"], list)
    assert isinstance(body["all_skills_ranked"], list)
    # Each item must have label, reason, weighted
    for item in body["key_skills"]:
        assert "label" in item
        assert "reason" in item
        assert "weighted" in item
        assert isinstance(item["weighted"], bool)


def test_key_skills_reason_values(client):
    resp = _post(client)
    assert resp.status_code == 200
    body = resp.json()
    valid_reasons = {"weighted", "idf", "standard"}
    for item in body["key_skills"] + body["all_skills_ranked"]:
        assert item["reason"] in valid_reasons, (
            f"Invalid reason: {item['reason']!r}"
        )


# ── Determinism ────────────────────────────────────────────────────────────────

def test_key_skills_deterministic_ordering(client):
    """Same inputs twice → identical output."""
    r1 = _post(client)
    r2 = _post(client)
    assert r1.status_code == 200
    assert r2.status_code == 200
    b1 = r1.json()
    b2 = r2.json()
    # key_skills order must be identical
    assert [i["label"] for i in b1["key_skills"]] == [i["label"] for i in b2["key_skills"]]
    # all_skills_ranked order must be identical
    assert [i["label"] for i in b1["all_skills_ranked"]] == [
        i["label"] for i in b2["all_skills_ranked"]
    ]


# ── Edge cases ─────────────────────────────────────────────────────────────────

def test_key_skills_handles_empty_validated(client):
    """Empty validated_items must return 200 with empty lists."""
    resp = _post(client, validated_items=[])
    assert resp.status_code == 200
    body = resp.json()
    assert body["key_skills"] == []
    assert body["all_skills_ranked"] == []


def test_key_skills_graceful_fallback_no_idf(client):
    """
    Even if IDF lookup returns nothing (e.g. empty DB),
    the endpoint must still return 200 with all skills as 'standard'.
    We can't force empty DB in this test, but we verify the endpoint
    never 500s and always returns valid reasons.
    """
    resp = _post(client, validated_items=[
        {"uri": "http://data.europa.eu/esco/skill/x1", "label": "UnknownSkillXYZ123"},
        {"uri": "http://data.europa.eu/esco/skill/x2", "label": "AnotherRareSkillABC456"},
    ])
    assert resp.status_code == 200
    body = resp.json()
    valid_reasons = {"weighted", "idf", "standard"}
    for item in body["key_skills"] + body["all_skills_ranked"]:
        assert item["reason"] in valid_reasons


# ── Limits ─────────────────────────────────────────────────────────────────────

def test_key_skills_max_12_key_skills(client):
    """key_skills must contain at most 12 items."""
    resp = _post(client)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["key_skills"]) <= 12, (
        f"key_skills has {len(body['key_skills'])} items (max 12)"
    )


def test_key_skills_all_skills_ranked_max_40(client):
    """all_skills_ranked must contain at most 40 items."""
    # Build 50 items
    many = [
        {"uri": f"http://data.europa.eu/esco/skill/{i}", "label": f"Skill {i:02d}"}
        for i in range(50)
    ]
    resp = _post(client, validated_items=many)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["all_skills_ranked"]) <= 40, (
        f"all_skills_ranked has {len(body['all_skills_ranked'])} items (max 40)"
    )


def test_key_skills_all_skills_contains_all_validated(client):
    """all_skills_ranked must include all validated items (when <= 40)."""
    resp = _post(client)
    assert resp.status_code == 200
    body = resp.json()
    ranked_labels = {item["label"] for item in body["all_skills_ranked"]}
    input_labels = {s["label"] for s in TECH_SKILLS}
    # All 15 input skills should appear (15 <= 40)
    assert input_labels == ranked_labels


# ── ROME code ──────────────────────────────────────────────────────────────────

def test_key_skills_rome_code_accepted(client):
    """rome_code field is accepted and endpoint still returns 200."""
    resp = _post(client, rome_code="M1403")
    assert resp.status_code == 200
    body = resp.json()
    assert "key_skills" in body


def test_key_skills_rome_code_none_accepted(client):
    """Null/missing rome_code is handled gracefully."""
    payload = {"validated_items": TECH_SKILLS, "rome_code": None}
    resp = client.post("/profile/key-skills", json=payload)
    assert resp.status_code == 200
