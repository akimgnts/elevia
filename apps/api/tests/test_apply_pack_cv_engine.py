import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from documents.apply_pack_cv_engine import build_targeted_cv, parse_offer, score_experiences


OFFER = {
    "id": "offer-fin-1",
    "title": "Contrôleur de gestion junior",
    "company": "Acme Finance",
    "description": "Reporting mensuel, analyse des écarts budgétaires, suivi des KPI et consolidation sous Excel et Power BI. Anglais requis.",
    "skills": ["reporting", "analyse budgétaire", "Excel", "Power BI", "anglais"],
}

PROFILE = {
    "name": "Akim Guentas",
    "skills": ["Excel", "Power BI", "analyse budgétaire", "reporting", "SQL"],
    "education": ["MSc Analytics for Business — EM Normandie"],
    "experiences": [
        {
            "title": "Analyste reporting",
            "company": "Groupe Alpha",
            "dates": "2024-2025",
            "bullets": [
                "Suivi du reporting mensuel sur 12 centres de coûts avec Excel et Power BI",
                "Analyse des écarts budgétaires afin de fiabiliser les prévisions",
            ],
        },
        {
            "title": "Assistant marketing",
            "company": "Studio Beta",
            "dates": "2022-2023",
            "bullets": [
                "Rédaction de newsletters et suivi des campagnes",
            ],
        },
    ],
}


def test_parse_offer_extracts_core_signals():
    parsed = parse_offer(OFFER)
    assert parsed.job_title == "Contrôleur de gestion junior"
    assert "Excel" in parsed.tools
    assert "Power Bi" in parsed.tools or "Power BI" in parsed.tools
    assert "Anglais professionnel" in parsed.languages
    assert parsed.sector == "finance"
    assert parsed.core_skills



def test_experience_ranking_keeps_relevant_experience_first():
    parsed = parse_offer(OFFER)
    scored = score_experiences(PROFILE, parsed)
    assert scored[0]["experience"].role == "Analyste reporting"
    assert scored[0]["decision"] == "keep"
    assert scored[-1]["decision"] in {"compress", "drop"}



def test_build_targeted_cv_returns_structured_cv_and_debug():
    payload = build_targeted_cv(PROFILE, OFFER)
    assert payload["cv"]["title"] == "Contrôleur de gestion junior"
    assert 1 <= len(payload["cv"]["experiences"]) <= 5
    assert payload["cv"]["layout"] == "single_column"
    assert payload["debug"]["experience_scores"]
    assert payload["debug"]["selected_verbs"]



def test_rewritten_bullets_use_non_generic_infinitive_verbs():
    payload = build_targeted_cv(PROFILE, OFFER)
    bullets = [bullet for exp in payload["cv"]["experiences"] for bullet in exp["bullets"]]
    assert bullets
    assert any(bullet.startswith("Analyser") or bullet.startswith("Examiner") or bullet.startswith("Évaluer") or bullet.startswith("Mesurer") for bullet in bullets)
    assert all(not bullet.startswith("Faire") for bullet in bullets)



def test_skills_are_ordered_with_offer_matches_first():
    payload = build_targeted_cv(PROFILE, OFFER)
    skills = payload["cv"]["skills"]
    assert skills[:3]
    assert any(skill.lower().startswith("excel") for skill in skills[:3])
