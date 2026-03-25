import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.canonical.canonical_mapper import map_to_canonical
from compass.explainability.semantic_explanation_builder import build_semantic_explainability
from compass.offer.offer_intelligence import build_offer_intelligence
from compass.offer.offer_parse_pipeline import build_offer_canonical_representation
from compass.scoring.scoring_v2 import build_scoring_v2


def test_offer_profile_linking_fr_en_variants_share_canonical_id_and_reduce_gap():
    profile_mapping = map_to_canonical(["analyse de données"])
    assert profile_mapping.mappings
    profile_skill = profile_mapping.mappings[0]

    offer = {
        "title": "Data Analyst",
        "description": """
        Missions principales :
        - Perform data analysis and prepare dashboards
        Profil recherché :
        - Compétences : data analysis
        """,
        "skills": ["data analysis"],
        "skills_display": [{"label": "data analysis"}],
    }
    canonical_offer = build_offer_canonical_representation(offer)
    offer_skill_ids = {item.get("canonical_id") for item in canonical_offer["canonical_skills"]}

    assert profile_skill.canonical_id == "skill:data_analysis"
    assert profile_skill.canonical_id in offer_skill_ids

    profile_intelligence = {
        "dominant_role_block": "data_analytics",
        "secondary_role_blocks": [],
        "dominant_domains": ["data"],
        "top_profile_signals": [profile_skill.label],
        "profile_summary": "Profil orienté analyse de données.",
    }
    offer_intelligence = build_offer_intelligence(offer=offer, canonical_offer=canonical_offer)
    semantic = build_semantic_explainability(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
        explanation=None,
    )
    scoring = build_scoring_v2(
        profile_intelligence=profile_intelligence,
        offer_intelligence=offer_intelligence,
        semantic_explainability=semantic,
        matching_score=0.82,
    )

    assert semantic is not None
    assert scoring is not None
    assert semantic["signal_alignment"]["matched_signals"]
    assert "Data Analysis" not in semantic["signal_alignment"]["missing_core_signals"]
    assert scoring["components"]["gap_penalty"] <= 0.1
    assert scoring["score"] >= 0.75
