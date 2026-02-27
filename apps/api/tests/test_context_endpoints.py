"""
test_context_endpoints.py — Schema + determinism tests for context layer.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient

from api.main import app
from api.schemas.context import ContextFit, OfferContext, ProfileContext


def _sample_offer_description() -> str:
    return (
        "Mission : construire des tableaux de bord de reporting pour la direction.\n"
        "- Produire des KPI hebdomadaires\n"
        "- Automatiser les rapports\n"
        "Outils : SQL, Power BI.\n"
        "Anglais courant requis."
    )


def _sample_profile_payload() -> dict:
    return {
        "candidate_info": {"years_of_experience": 5},
        "detected_capabilities": [
            {
                "name": "programming_scripting",
                "level": "expert",
                "score": 85,
                "proofs": ["5 ans de Python et SQL"],
                "tools_detected": ["Python", "SQL"],
            }
        ],
        "languages": [{"code": "fr", "level": "C2"}],
    }


def test_context_offer_schema():
    client = TestClient(app)
    resp = client.post(
        "/context/offer",
        json={"offer_id": "offer-ctx-1", "description": _sample_offer_description()},
    )
    assert resp.status_code == 200
    data = resp.json()
    OfferContext.model_validate(data)
    assert data["offer_id"] == "offer-ctx-1"
    assert "SQL" in data["tools_stack_signals"]
    assert data["role_type"] in {
        "BI_REPORTING",
        "DATA_ANALYSIS",
        "DATA_ENGINEERING",
        "PRODUCT_ANALYTICS",
        "OPS_ANALYTICS",
        "MIXED",
        "UNKNOWN",
    }
    for span in data.get("evidence_spans", []):
        assert len(span["span"].split()) <= 20


def test_context_profile_schema():
    client = TestClient(app)
    resp = client.post(
        "/context/profile",
        json={
            "profile_id": "profile-ctx-1",
            "cv_text_cleaned": "Profil data avec 5 ans d'expérience en SQL et Python.",
            "profile": _sample_profile_payload(),
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    ProfileContext.model_validate(data)
    assert data["profile_id"] == "profile-ctx-1"
    assert data["dominant_strengths"]
    for span in data.get("evidence_spans", []):
        assert len(span["span"].split()) <= 20


def test_context_fit_schema():
    client = TestClient(app)
    offer_resp = client.post(
        "/context/offer",
        json={"offer_id": "offer-ctx-2", "description": _sample_offer_description()},
    )
    profile_resp = client.post(
        "/context/profile",
        json={
            "profile_id": "profile-ctx-2",
            "cv_text_cleaned": "Profil data orienté reporting avec Power BI et SQL.",
            "profile": _sample_profile_payload(),
        },
    )
    assert offer_resp.status_code == 200
    assert profile_resp.status_code == 200

    resp = client.post(
        "/context/fit",
        json={
            "offer_context": offer_resp.json(),
            "profile_context": profile_resp.json(),
            "matched_skills": ["sql", "power bi"],
            "missing_skills": ["tableau"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    ContextFit.model_validate(data)
    assert data["offer_id"] == "offer-ctx-2"
    assert data["profile_id"] == "profile-ctx-2"

