import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.offer.offer_parse_pipeline import build_offer_canonical_representation
from compass.offer.offer_intelligence import build_offer_intelligence


def _finance_offer() -> dict:
    return {
        "id": "offer-finance-parity",
        "title": "VIE - Finance Controller",
        "description": """
        Missions principales :
        - Produire des analyses et reportings réguliers
        - Suivre les budgets et les écarts
        Profil recherché :
        - Compétences : comptabilité, audit, Excel, modélisation financière
        """,
        "skills": ["comptabilité", "audit", "Excel", "modélisation financière", "reporting"],
        "skills_display": [{"label": "comptabilité"}, {"label": "audit"}, {"label": "Excel"}],
    }


def test_offer_parse_pipeline_returns_canonical_representation():
    result = build_offer_canonical_representation(_finance_offer())

    assert result["structured_units"]
    assert result["mapping_inputs"]
    assert result["canonical_skills"]
    assert result["canonical_domains"]
    assert isinstance(result["unresolved"], list)


def test_offer_parse_pipeline_is_deterministic():
    offer = _finance_offer()
    first = build_offer_canonical_representation(offer)
    second = build_offer_canonical_representation(offer)

    assert first["mapping_inputs"] == second["mapping_inputs"]
    assert first["canonical_skills"] == second["canonical_skills"]
    assert first["canonical_domains"] == second["canonical_domains"]


def test_offer_parse_pipeline_keeps_existing_finance_inference_stable():
    canonical_offer = build_offer_canonical_representation(_finance_offer())
    intelligence = build_offer_intelligence(offer=_finance_offer(), canonical_offer=canonical_offer)

    assert intelligence["dominant_role_block"] == "finance_ops"
