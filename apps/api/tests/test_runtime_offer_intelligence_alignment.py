from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app


def _offer() -> dict:
    return {
        "id": "bf-align-1",
        "source": "business_france",
        "title": "Financial Controller",
        "description": """
        Missions principales :
        - Contrôle de gestion, budget, reporting, audit
        Profil recherché :
        - Compétences : comptabilité, audit, Excel, modélisation financière
        """,
        "skills": ["comptabilité", "audit", "Excel", "modélisation financière", "reporting"],
        "skills_display": [
            {"label": "comptabilité"},
            {"label": "audit"},
            {"label": "Excel"},
            {"label": "modélisation financière"},
        ],
        "skills_uri": [
            "http://data.europa.eu/esco/skill/accounting",
            "http://data.europa.eu/esco/skill/internal-control",
        ],
        "job_family": "Finance",
        "primary_function": "Controlling",
        "purity_score": 0.8,
        "hybrid_score": 0.1,
        "needs_review": False,
        "country": "Germany",
        "city": "Frankfurt",
        "publication_date": "2026-03-20",
    }


def _profile() -> dict:
    return {
        "id": "profile-finance-1",
        "skills": ["audit", "excel", "reporting"],
        "matching_skills": ["audit", "excel", "reporting"],
        "skills_uri": [
            "http://data.europa.eu/esco/skill/accounting",
            "http://data.europa.eu/esco/skill/internal-control",
        ],
        "profile_intelligence": {
            "dominant_role_block": "finance_ops",
            "dominant_domains": ["finance"],
            "top_profile_signals": ["audit", "reporting", "excel"],
            "profile_summary": "Profil orienté finance opérationnelle.",
        },
    }


def test_matching_route_exposes_persisted_offer_intelligence_fields():
    client = TestClient(app)
    response = client.post(
        "/v1/match",
        json={
            "profile": _profile(),
            "offers": [_offer()],
        },
    )

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["offer_intelligence"]["job_family"] == "Finance"
    assert result["offer_intelligence"]["primary_function"] == "Controlling"
    assert result["offer_intelligence"]["purity_score"] == 0.8
    assert result["offer_intelligence"]["hybrid_score"] == 0.1
    assert result["offer_intelligence"]["needs_review"] is False


def test_debug_match_exposes_persisted_offer_intelligence_fields(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("DEBUG", "1")
    client = TestClient(app)

    response = client.post(
        "/debug/match",
        json={
            "profile": _profile(),
            "offers": [_offer()],
            "limit": 1,
        },
    )

    assert response.status_code == 200
    trace = response.json()["traces"][0]
    assert trace["offer_intelligence"]["job_family"] == "Finance"
    assert trace["offer_intelligence"]["primary_function"] == "Controlling"
    assert trace["offer_intelligence"]["purity_score"] == 0.8
    assert trace["offer_intelligence"]["hybrid_score"] == 0.1
    assert trace["offer_intelligence"]["needs_review"] is False
