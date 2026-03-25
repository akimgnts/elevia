import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.offer.offer_parse_pipeline import build_offer_canonical_representation


def test_offer_canonical_mapping_collapses_fr_en_aliases():
    offer = {
        "title": "Data Analyst",
        "description": """
        Missions principales :
        - Build reporting and perform data analysis on commercial datasets
        Profil recherché :
        - Compétences : analyse de données, data analysis, Power BI
        """,
        "skills": ["analyse de données", "data analysis", "Power BI"],
        "skills_display": [{"label": "analyse de données"}, {"label": "data analysis"}, {"label": "Power BI"}],
    }

    result = build_offer_canonical_representation(offer)
    data_analysis = [item for item in result["canonical_skills"] if item.get("canonical_id") == "skill:data_analysis"]

    assert len(data_analysis) == 1
    assert "Data Analysis" in result["mapping_inputs"]


def test_offer_canonical_mapping_normalizes_aliases_before_mapping():
    offer = {
        "title": "Business Intelligence Analyst",
        "description": """
        Missions principales :
        - Construire des tableaux de bord et de la visualisation des données
        Profil recherché :
        - Compétences : powerbi, data visualization
        """,
        "skills": ["powerbi", "data visualization"],
        "skills_display": [{"label": "powerbi"}, {"label": "data visualization"}],
    }

    result = build_offer_canonical_representation(offer)
    mapped_ids = {item.get("canonical_id") for item in result["canonical_skills"]}

    assert "skill:power_bi" in mapped_ids
    assert "Power BI" in result["mapping_inputs"]


def test_offer_canonical_mapping_tracks_unresolved_without_crashing():
    offer = {
        "title": "Operations Coordinator",
        "description": "Missions : piloter les flux. Profil : connaissance de xenotool interne.",
        "skills": ["xenotool interne"],
        "skills_display": [{"label": "xenotool interne"}],
    }

    result = build_offer_canonical_representation(offer)

    assert isinstance(result["unresolved"], list)
    assert any(item.get("raw") for item in result["unresolved"])
