import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.offer.offer_intelligence import build_offer_intelligence


def test_required_optional_split_is_bounded_and_meaningful():
    offer = {
        "title": "VIE - Marketing - Faurecia Émirats arabes unis",
        "description": """
        Missions principales :
        - Piloter les campagnes email et les contenus marketing
        Profil recherché :
        - Compétences : branding, SEO, réseaux sociaux, marketing digital, CRM
        - Power BI apprécié
        - Première expérience souhaitée
        """,
        "skills": ["branding", "SEO", "réseaux sociaux", "marketing digital", "CRM", "Power BI"],
        "skills_display": [{"label": skill} for skill in ["branding", "SEO", "réseaux sociaux", "marketing digital", "CRM", "Power BI"]],
    }
    result = build_offer_intelligence(offer=offer)
    assert result["required_skills"]
    assert len(result["required_skills"]) <= 5
    assert len(result["optional_skills"]) <= 4
    assert "Power BI" in result["optional_skills"]
    assert "marketing digital" in result["required_skills"] or "SEO" in result["required_skills"]
