"""
Unit tests for deterministic offer cluster detection.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from offer.offer_cluster import detect_offer_cluster


def test_offer_cluster_cases():
    cases = [
        ("Data analyst", "", ["sql", "python"], "DATA_IT"),
        ("Responsable marketing", "", ["marketing", "communication"], "MARKETING_SALES"),
        ("Contrôle de gestion", "", ["comptabilité", "audit"], "FINANCE_LEGAL"),
        ("Acheteur supply chain", "", ["logistique", "achats"], "SUPPLY_OPS"),
        ("Ingénieur mécanique", "", ["maintenance", "r&d"], "ENGINEERING_INDUSTRY"),
        ("Assistant RH", "", ["ressources humaines", "recrutement"], "ADMIN_HR"),
        ("Stage polyvalent", "", [], "OTHER"),
    ]

    for title, description, skills, expected in cases:
        cluster, confidence, scores = detect_offer_cluster(title, description, skills)
        assert cluster == expected
        assert 0.0 <= confidence <= 1.0
        assert isinstance(scores, dict)
        assert expected in scores
