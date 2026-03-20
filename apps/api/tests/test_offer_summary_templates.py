import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.offer.offer_intelligence import build_offer_intelligence


def test_offer_summary_is_short_and_stable():
    offer = {
        "title": "VIE - Supply Chain - Bouygues Royaume-Uni",
        "description": """
        Missions principales :
        - Suivre les livraisons et les stocks
        - Coordonner les fournisseurs
        Profil recherché :
        - Compétences : supply chain, logistique, gestion des stocks
        """,
        "skills": ["supply chain", "logistique", "gestion des stocks"],
        "skills_display": [{"label": "supply chain"}, {"label": "logistique"}, {"label": "gestion des stocks"}],
    }
    first = build_offer_intelligence(offer=offer)
    second = build_offer_intelligence(offer=offer)
    assert first["offer_summary"] == second["offer_summary"]
    assert first["offer_summary"].startswith("Poste orienté")
    assert len(first["offer_summary"]) < 140
