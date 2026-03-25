import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient

from api.main import app
from api.routes import inbox as inbox_routes
from api.schemas.inbox import OfferIntelligence
from compass.offer.offer_intelligence import (
    build_offer_intelligence,
    classify_role_match,
    evaluate_role_domain_gate,
    is_role_domain_compatible,
)


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


def test_inbox_filters_cross_metier_offers_before_scoring(monkeypatch):
    supply_offer = {
        "title": "Coordinateur Supply Chain (H/F)",
        "description": """
        Missions principales :
        - Coordination transport, suivi fournisseurs, gestion des stocks
        Profil recherché :
        - Compétences : logistique, supply chain, approvisionnement, SAP
        """,
        "skills": ["logistique", "supply chain", "approvisionnement", "SAP"],
        "skills_display": [{"label": "logistique"}, {"label": "supply chain"}, {"label": "approvisionnement"}],
        "id": "offer-supply-1",
        "source": "business_france",
        "company": "SupplyCo",
        "country": "France",
        "city": "Lille",
        "publication_date": "2026-03-20",
    }
    hr_offer = {
        "title": "HR Project Manager (H/F)",
        "description": """
        Missions principales :
        - Gestion administrative RH, onboarding, suivi recrutement
        Profil recherché :
        - Compétences : recrutement, administration du personnel, anglais
        """,
        "skills": ["recrutement", "administration du personnel", "anglais"],
        "skills_display": [{"label": "recrutement"}, {"label": "administration du personnel"}],
        "id": "offer-hr-1",
        "source": "business_france",
        "company": "HRCo",
        "country": "France",
        "city": "Paris",
        "publication_date": "2026-03-20",
    }
    client = TestClient(app)
    monkeypatch.setattr(inbox_routes, "load_catalog_offers", lambda: [supply_offer, hr_offer])
    monkeypatch.setattr(inbox_routes, "load_catalog_offers_filtered", lambda **kwargs: [supply_offer, hr_offer])
    monkeypatch.setattr(inbox_routes, "count_catalog_offers_filtered", lambda **kwargs: 2)

    resp = client.post(
        "/inbox",
        json={
            "profile_id": "supply-profile",
            "profile": {
                "skills": ["logistique", "transport", "supply chain"],
                "profile_intelligence": {
                    "dominant_role_block": "supply_chain_ops",
                    "secondary_role_blocks": ["project_ops"],
                    "dominant_domains": ["supply_chain", "operations"],
                    "top_profile_signals": ["logistique", "transport operations", "supply chain"],
                    "profile_summary": "Profil supply chain operationnelle.",
                },
            },
            "min_score": 0,
            "limit": 5,
        },
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [item["offer_id"] for item in items] == ["offer-supply-1"]


def test_offer_role_domain_compatibility_rejects_cross_metier_noise():
    profile_intelligence = {
        "dominant_role_block": "supply_chain_ops",
        "secondary_role_blocks": ["project_ops"],
        "dominant_domains": ["supply_chain", "operations"],
    }
    offer_intelligence = {
        "dominant_role_block": "hr_ops",
        "secondary_role_blocks": ["project_ops"],
        "dominant_domains": ["hr", "project"],
    }

    assert classify_role_match(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
    ) == "acceptable"
    assert is_role_domain_compatible(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
    ) is False


def test_offer_role_domain_compatibility_keeps_strong_metier_match():
    profile_intelligence = {
        "dominant_role_block": "finance_ops",
        "secondary_role_blocks": ["business_analysis"],
        "dominant_domains": ["finance"],
    }
    offer_intelligence = {
        "dominant_role_block": "finance_ops",
        "secondary_role_blocks": [],
        "dominant_domains": ["finance", "business"],
    }

    assert classify_role_match(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
    ) == "strong"
    assert is_role_domain_compatible(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
    ) is True


def test_offer_gate_allows_bridge_role_with_shared_domain_and_required_signal_overlap():
    profile_intelligence = {
        "dominant_role_block": "supply_chain_ops",
        "secondary_role_blocks": ["project_ops"],
        "dominant_domains": ["supply_chain", "operations"],
        "top_profile_signals": ["supply chain", "logistique", "procurement analytics"],
    }
    offer_intelligence = {
        "dominant_role_block": "data_analytics",
        "secondary_role_blocks": [],
        "dominant_domains": ["data", "supply_chain"],
        "top_offer_signals": ["procurement analytics", "supply chain dashboard"],
        "required_skills": ["supply chain", "sql"],
    }

    decision = evaluate_role_domain_gate(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
    )
    assert decision["role_match"] == "invalid"
    assert decision["compatible"] is True
    assert decision["effective_role_match"] == "weak"
    assert decision["allow_reason"] == "weak_role_with_bridge_domain"


def test_offer_gate_keeps_data_engineering_bridge_rejected_without_shared_business_domain():
    profile_intelligence = {
        "dominant_role_block": "data_analytics",
        "secondary_role_blocks": ["business_analysis"],
        "dominant_domains": ["data"],
        "top_profile_signals": ["sql", "power bi", "dashboard"],
    }
    offer_intelligence = {
        "dominant_role_block": "software_it",
        "secondary_role_blocks": [],
        "dominant_domains": ["software", "it", "data"],
        "top_offer_signals": ["chemical engineering", "industrial process"],
        "required_skills": ["engineering", "industrial process"],
    }

    decision = evaluate_role_domain_gate(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
    )
    assert decision["compatible"] is False
    assert decision["rejection_reason"] == "weak_role_without_enough_domain_or_signal_support"


def test_offer_gate_allows_acceptable_marketing_business_dev_hybrid_from_secondary_role_domain_support():
    profile_intelligence = {
        "dominant_role_block": "marketing_communication",
        "secondary_role_blocks": ["sales_business_dev"],
        "dominant_domains": ["marketing"],
        "top_profile_signals": ["emailing", "campaign analysis", "content creation"],
    }
    offer_intelligence = {
        "dominant_role_block": "sales_business_dev",
        "secondary_role_blocks": ["marketing_communication"],
        "dominant_domains": ["sales", "data"],
        "top_offer_signals": ["business development", "campaign coordination"],
        "required_skills": ["communication", "business development"],
    }

    decision = evaluate_role_domain_gate(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
    )
    assert decision["role_match"] == "acceptable"
    assert decision["compatible"] is True
    assert decision["allow_reason"] == "acceptable_role_with_secondary_role_domain_support"


def test_offer_gate_rejects_weak_data_only_overlap_even_with_signal_overlap():
    profile_intelligence = {
        "dominant_role_block": "data_analytics",
        "secondary_role_blocks": ["business_analysis"],
        "dominant_domains": ["data"],
        "top_profile_signals": ["data analysis", "dashboarding", "sql"],
    }
    offer_intelligence = {
        "dominant_role_block": "software_it",
        "secondary_role_blocks": [],
        "dominant_domains": ["software", "it", "data"],
        "top_offer_signals": ["data analysis", "chemical engineering"],
        "required_skills": ["data analysis", "industrial process"],
    }

    decision = evaluate_role_domain_gate(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
    )
    assert decision["role_match"] == "weak"
    assert decision["compatible"] is False
    assert decision["rejection_reason"] == "weak_role_without_enough_domain_or_signal_support"


def test_offer_gate_allows_narrow_data_software_bridge_with_explicit_data_support():
    profile_intelligence = {
        "dominant_role_block": "data_analytics",
        "secondary_role_blocks": ["business_analysis"],
        "dominant_domains": ["data"],
        "top_profile_signals": ["data analysis", "sql", "dashboarding", "power bi"],
    }
    offer_intelligence = {
        "dominant_role_block": "software_it",
        "secondary_role_blocks": [],
        "dominant_domains": ["software", "it", "data"],
        "top_offer_signals": ["Business Intelligence", "Data Analysis", "Machine Learning"],
        "required_skills": ["Machine Learning", "Business Intelligence"],
        "debug": {
            "title_probe": {"raw_title": "VIE - Informatique - Plastic Omnium Danemark"},
            "domain_scores": [
                {"domain": "software", "score": 5.7},
                {"domain": "it", "score": 5.1},
                {"domain": "data", "score": 3.6},
            ],
        },
    }

    decision = evaluate_role_domain_gate(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
    )
    assert decision["role_match"] == "weak"
    assert decision["compatible"] is True
    assert decision["allow_reason"] == "data_software_bridge_with_explicit_data_support"


def test_offer_gate_keeps_generic_engineering_noise_rejected_for_data_profile():
    profile_intelligence = {
        "dominant_role_block": "data_analytics",
        "secondary_role_blocks": ["business_analysis"],
        "dominant_domains": ["data"],
        "top_profile_signals": ["data analysis", "sql", "dashboarding", "power bi"],
    }
    offer_intelligence = {
        "dominant_role_block": "software_it",
        "secondary_role_blocks": [],
        "dominant_domains": ["software", "it", "data"],
        "top_offer_signals": [
            "Data Analysis",
            "analyse de données",
            "schéma de conception d’interface utilisateur",
        ],
        "required_skills": ["Data Analysis", "schéma de conception d’interface utilisateur"],
        "debug": {
            "title_probe": {"raw_title": "Chemical Engineering (H/F)"},
            "domain_scores": [
                {"domain": "software", "score": 4.0},
                {"domain": "it", "score": 3.6},
                {"domain": "data", "score": 1.85},
            ],
        },
    }

    decision = evaluate_role_domain_gate(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
    )
    assert decision["role_match"] == "weak"
    assert decision["compatible"] is False
    assert decision["rejection_reason"] == "weak_role_without_enough_domain_or_signal_support"
