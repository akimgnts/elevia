import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.offer.offer_intelligence import build_offer_intelligence


def _offer(title: str, description: str, skills: list[str]) -> dict:
    return {
        "id": "offer-test",
        "title": title,
        "description": description,
        "skills": skills,
        "skills_display": [{"label": skill} for skill in skills],
        "offer_cluster": None,
    }


def test_finance_offer_maps_to_finance_ops():
    offer = _offer(
        "VIE - Finance - LVMH Allemagne",
        """
        Missions principales :
        - Produire des analyses et reportings réguliers
        - Suivre les budgets et les écarts
        Profil recherché :
        - Compétences : comptabilité, audit, Excel, modélisation financière
        - Maîtrise de l'anglais professionnel requis
        """,
        ["comptabilité", "audit", "Excel", "modélisation financière", "reporting"],
    )
    result = build_offer_intelligence(offer=offer)
    assert result["dominant_role_block"] == "finance_ops"


def test_sales_offer_maps_to_sales_business_dev():
    offer = _offer(
        "VIE - Commerce - AXA Japon",
        """
        Missions principales :
        - Développer le portefeuille clients et qualifier les prospects
        - Suivre l'activité commerciale dans le CRM
        Profil recherché :
        - Compétences : développement commercial, prospection, négociation, CRM
        """,
        ["développement commercial", "prospection", "négociation", "CRM"],
    )
    result = build_offer_intelligence(offer=offer)
    assert result["dominant_role_block"] == "sales_business_dev"


def test_supply_offer_maps_to_supply_chain_ops():
    offer = _offer(
        "VIE - Supply Chain - Bouygues Royaume-Uni",
        """
        Missions principales :
        - Suivre les livraisons et les stocks
        - Coordonner les fournisseurs et les approvisionnements
        Profil recherché :
        - Compétences : supply chain, logistique, gestion des stocks
        """,
        ["supply chain", "logistique", "gestion des stocks", "fournisseurs"],
    )
    result = build_offer_intelligence(offer=offer)
    assert result["dominant_role_block"] == "supply_chain_ops"


def test_communication_offer_maps_to_marketing_communication():
    offer = _offer(
        "VIE - Communication - Hermès Mexique",
        """
        Missions principales :
        - Préparer les contenus et newsletters internes
        - Coordonner les relations presse et l'événementiel
        Profil recherché :
        - Compétences : communication interne, relations presse, événementiel
        """,
        ["communication interne", "relations presse", "événementiel", "newsletter"],
    )
    result = build_offer_intelligence(offer=offer)
    assert result["dominant_role_block"] == "marketing_communication"
