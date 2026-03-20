import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient

from api.main import app
from api.routes import inbox as inbox_routes
from api.schemas.inbox import OfferIntelligence
from compass.offer.offer_intelligence import build_offer_intelligence


def _offer() -> dict:
    return {
        "title": "VIE - Finance - LVMH Allemagne",
        "description": """
        Missions principales :
        - Produire des analyses et reportings réguliers
        Profil recherché :
        - Compétences : comptabilité, audit, Excel, modélisation financière
        """,
        "skills": ["comptabilité", "audit", "Excel", "modélisation financière", "reporting"],
        "skills_display": [{"label": "comptabilité"}, {"label": "audit"}, {"label": "Excel"}],
        "id": "offer-finance-1",
        "source": "business_france",
        "company": "LVMH",
        "country": "Allemagne",
        "city": "Frankfurt",
        "publication_date": "2026-03-20",
    }


def test_offer_intelligence_payload_is_schema_compatible():
    payload = OfferIntelligence(**build_offer_intelligence(offer=_offer()))
    assert payload.dominant_role_block
    assert payload.offer_summary


def test_offer_intelligence_is_exposed_in_inbox_route(monkeypatch):
    offer = _offer()
    client = TestClient(app)
    monkeypatch.setattr(inbox_routes, "load_catalog_offers", lambda: [offer])
    monkeypatch.setattr(inbox_routes, "load_catalog_offers_filtered", lambda **kwargs: [offer])
    monkeypatch.setattr(inbox_routes, "count_catalog_offers_filtered", lambda **kwargs: 1)

    resp = client.post(
        "/inbox",
        json={
            "profile_id": "offer-intel",
            "profile": {
                "skills": ["audit", "excel"],
                "profile_intelligence": {
                    "dominant_role_block": "finance_ops",
                    "dominant_domains": ["finance"],
                    "top_profile_signals": ["audit", "reporting", "excel"],
                    "profile_summary": "Profil orienté finance opérationnelle.",
                },
            },
            "min_score": 0,
            "limit": 1,
        },
    )
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["offer_intelligence"]["dominant_role_block"] == "finance_ops"
    assert item["offer_intelligence"]["offer_summary"].startswith("Poste orienté")
    assert item["semantic_explainability"]["role_alignment"]["alignment"] == "high"
    assert item["semantic_explainability"]["alignment_summary"].startswith("Ton profil et ce poste")


def test_offer_intelligence_is_deterministic():
    offer = {
        "title": "VIE - Finance - LVMH Allemagne",
        "description": """
        Missions principales :
        - Produire des analyses et reportings réguliers
        Profil recherché :
        - Compétences : comptabilité, audit, Excel, modélisation financière
        """,
        "skills": ["comptabilité", "audit", "Excel", "modélisation financière", "reporting"],
        "skills_display": [{"label": "comptabilité"}, {"label": "audit"}, {"label": "Excel"}],
    }
    first = build_offer_intelligence(offer=offer)
    second = build_offer_intelligence(offer=offer)
    assert first == second
