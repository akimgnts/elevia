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
        assert cluster == expected, f"{title!r}: expected {expected!r}, got {cluster!r}"
        assert 0.0 <= confidence <= 1.0
        assert isinstance(scores, dict)
        assert expected in scores


def test_offer_cluster_tiebreak_deterministic():
    """Same inputs → same cluster (tie-break stable, no set iteration)."""
    r1 = detect_offer_cluster("Poste généraliste", "", [])
    r2 = detect_offer_cluster("Poste généraliste", "", [])
    assert r1[0] == r2[0]
    assert r1[0] == "OTHER"


def test_offer_cluster_confidence_range():
    """Confidence is always in [0, 1]."""
    for title, skills in [
        ("Data Analyst", ["python", "sql"]),
        ("Inconnu", []),
        ("Ingénieur", ["mécanique"]),
    ]:
        _, confidence, _ = detect_offer_cluster(title, "", skills)
        assert 0.0 <= confidence <= 1.0
