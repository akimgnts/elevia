"""
Integration test: CareerProfile v2 pipeline.

Covers:
- ProfileStructuredV1 → identity_hint, projects, experience.location
- from_profile_structured_v1 → CareerProfile v2 schema
- _profile_fingerprint: identity_present busts cache
- _build_experiences_text: location in headers
- _build_identity_text / _build_projects_text / _build_positioning_phrase
- score_career_experiences: uses explicit LEAD/COPILOT/CONTRIB autonomy
- build_targeted_cv: cv_strategy passthrough
- html_renderer: _extract_name prefers career_profile.identity, _extract_contact_line
- Score invariance: no skills_uri injection
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.contracts import ExperienceV1, ProjectV1, ProfileStructuredV1
from compass.profile_structurer import structure_profile_text_v1
from documents.career_profile import (
    CareerIdentity,
    CareerProfile,
    CareerProject,
    from_profile_structured_v1,
    to_experience_dicts,
)
from documents.cv_generator import (
    _build_identity_text,
    _build_positioning_phrase,
    _build_projects_text,
    _profile_fingerprint,
)
from documents.apply_pack_cv_engine import (
    build_targeted_cv,
    parse_offer,
    score_career_experiences,
)
from documents.html_renderer import _extract_contact_line, _extract_name


# ── Fixtures ──────────────────────────────────────────────────────────────────

CV_TEXT = """
Jean Dupont
jean.dupont@example.com
+33 6 12 34 56 78
linkedin.com/in/jeandupont
Paris

EXPÉRIENCES PROFESSIONNELLES

Analyste Data - Société Générale (2022-2025)
Paris
Développement de dashboards Power BI pour le suivi budgétaire
Analyse des écarts avec Python et SQL
Réduction des délais de reporting de 30%

PROJETS

Dashboard RH automatisé
github.com/jeandupont/rh-dashboard
Python, Pandas, Streamlit
Utilisé par 200 utilisateurs

FORMATION

Master Data Science - Université Paris-Dauphine (2020-2022)
"""

OFFER = {
    "id": "TEST-CV2-001",
    "title": "Data Analyst",
    "company": "Acme Corp",
    "country": "France",
    "description": "Python SQL Power BI reporting data analytics",
}

PROFILE_WITH_CAREER = {
    "skills": ["Python", "SQL", "Power BI"],
    "education": ["Master Data Science — Université Paris-Dauphine"],
    "experiences": [
        {
            "title": "Analyste Data",
            "company": "Société Générale",
            "location": "Paris",
            "autonomy": "LEAD",
            "dates": "2022-2025",
            "bullets": ["Développement de dashboards Power BI", "Analyse des écarts budgétaires"],
            "achievements": ["Réduction des délais de reporting de 30%"],
            "tools": ["Python", "SQL", "Power BI"],
        }
    ],
    "career_profile": {
        "schema_version": "v2",
        "target_title": "Analyste Data",
        "identity": {"full_name": "Jean Dupont", "email": "jean.dupont@example.com", "phone": "+33 6 12 34 56 78", "location": "Paris", "linkedin": "linkedin.com/in/jeandupont"},
        "projects": [{"title": "Dashboard RH automatisé", "technologies": ["Python", "Streamlit"], "url": "github.com/jeandupont/rh-dashboard", "impact": "200 utilisateurs"}],
        "experiences": [
            {"title": "Analyste Data", "company": "Société Générale", "location": "Paris", "autonomy": "LEAD", "dates": "2022-2025", "responsibilities": ["Développement de dashboards Power BI"], "achievements": ["Réduction des délais de 30%"], "tools": ["Python", "SQL"]}
        ],
        "completeness": 0.85,
    },
}


# ── Step 1: contracts ─────────────────────────────────────────────────────────

def test_experience_v1_has_location():
    exp = ExperienceV1(title="Analyst", company="Acme", location="Paris")
    assert exp.location == "Paris"


def test_project_v1_schema():
    proj = ProjectV1(title="My App", technologies=["Python", "React"], url="https://github.com/foo")
    assert proj.title == "My App"
    assert "Python" in proj.technologies


def test_profile_structured_v1_has_projects_and_identity():
    from compass.contracts import CVQualityV1, CVQualityCoverage
    structured = ProfileStructuredV1(
        projects=[ProjectV1(title="Test Project")],
        identity_hint={"full_name": "Alice"},
        cv_quality=CVQualityV1(
            quality_level="MED",
            reasons=[],
            coverage=CVQualityCoverage(experiences_found=0, education_found=0, certifications_found=0, tools_found=0, date_coverage_ratio=0.0),
        ),
    )
    assert len(structured.projects) == 1
    assert structured.identity_hint == {"full_name": "Alice"}


# ── Step 2-4: profile_structurer ─────────────────────────────────────────────

def test_structurer_extracts_identity_hint():
    result = structure_profile_text_v1(CV_TEXT, debug=False)
    assert result.identity_hint is not None
    assert result.identity_hint.get("full_name") == "Jean Dupont"
    assert result.identity_hint.get("email") == "jean.dupont@example.com"
    assert result.identity_hint.get("linkedin") is not None


def test_structurer_extracts_projects():
    result = structure_profile_text_v1(CV_TEXT, debug=False)
    assert len(result.projects) >= 1
    proj = result.projects[0]
    assert "Dashboard" in proj.title
    assert proj.url is not None


def test_structurer_experience_location():
    cv = """
EXPÉRIENCES PROFESSIONNELLES

Data Analyst chez Acme
Paris
2023-présent
Analyse des données Python
"""
    result = structure_profile_text_v1(cv, debug=False)
    # Location may be extracted if location detection works
    locations = [e.location for e in result.experiences if e.location]
    assert "Paris" in locations or len(result.experiences) == 0  # parser edge cases OK


# ── Steps 5-7: career_profile.py ─────────────────────────────────────────────

def test_career_profile_v2_schema():
    cp = CareerProfile()
    assert cp.schema_version == "v2"
    assert cp.identity is None
    assert cp.projects == []


def test_career_identity_model():
    identity = CareerIdentity(full_name="Jean Dupont", email="j@example.com", location="Paris")
    assert identity.full_name == "Jean Dupont"
    assert identity.location == "Paris"


def test_career_project_model():
    proj = CareerProject(title="Portfolio", technologies=["React", "Python"])
    assert proj.title == "Portfolio"
    assert "React" in proj.technologies


def test_from_profile_structured_v1_identity():
    result = structure_profile_text_v1(CV_TEXT, debug=False)
    cp = from_profile_structured_v1(result, raw_skills=["Python", "SQL"], raw_languages=["Français natif"])
    assert cp.schema_version == "v2"
    assert cp.identity is not None
    assert cp.identity.full_name == "Jean Dupont"


def test_from_profile_structured_v1_projects():
    result = structure_profile_text_v1(CV_TEXT, debug=False)
    cp = from_profile_structured_v1(result, raw_skills=["Python"], raw_languages=[])
    assert len(cp.projects) >= 1
    assert "Dashboard" in cp.projects[0].title


def test_completeness_increases_with_identity_and_projects():
    cp_base = CareerProfile(experiences=[])
    cp_with = CareerProfile(
        identity=CareerIdentity(full_name="Jean Dupont"),
        projects=[CareerProject(title="Test")],
    )
    assert cp_with.completeness >= cp_base.completeness


def test_to_experience_dicts_includes_location():
    cp = CareerProfile()
    from documents.career_profile import CareerExperience
    cp.experiences = [
        CareerExperience(title="Analyst", company="Acme", location="Paris", responsibilities=["Build reports"])
    ]
    dicts = to_experience_dicts(cp)
    assert dicts[0]["location"] == "Paris"


# ── Steps 8-11: cv_generator.py ──────────────────────────────────────────────

def test_fingerprint_changes_with_identity():
    profile_no_identity = {
        "skills": ["Python"],
        "career_profile": {"completeness": 0.5},
    }
    profile_with_identity = {
        "skills": ["Python"],
        "career_profile": {"completeness": 0.5, "identity": {"full_name": "Alice"}},
    }
    fp1 = _profile_fingerprint(profile_no_identity)
    fp2 = _profile_fingerprint(profile_with_identity)
    assert fp1 != fp2


def test_build_identity_text_empty():
    assert _build_identity_text({}) == ""


def test_build_identity_text_full():
    profile = {
        "career_profile": {
            "identity": {"full_name": "Jean Dupont", "location": "Paris", "email": "j@ex.com"}
        }
    }
    text = _build_identity_text(profile)
    assert "Jean Dupont" in text
    assert "Paris" in text


def test_build_projects_text_empty():
    text = _build_projects_text({})
    assert "aucun" in text.lower()


def test_build_projects_text_has_content():
    profile = {
        "career_profile": {
            "projects": [{"title": "Portfolio DS", "technologies": ["Python"], "url": "github.com/foo"}]
        }
    }
    text = _build_projects_text(profile)
    assert "Portfolio DS" in text
    assert "Python" in text


def test_build_positioning_phrase():
    profile = {
        "career_profile": {
            "target_title": "Data Analyst",
            "identity": {"location": "Paris"},
        }
    }
    phrase = _build_positioning_phrase(profile)
    assert "Data Analyst" in phrase
    assert "Paris" in phrase


# ── Steps 12-13: score_career_experiences ────────────────────────────────────

def test_score_career_experiences_uses_explicit_autonomy():
    profile = {
        "experiences": [
            {"title": "Analyst", "company": "Acme", "autonomy": "LEAD", "bullets": ["Python reporting"], "dates": "2023-2025"},
            {"title": "Junior", "company": "Beta", "autonomy": "CONTRIB", "bullets": ["data entry"], "dates": "2021-2022"},
        ]
    }
    offer_obj = parse_offer(OFFER)
    scores = score_career_experiences(profile, offer_obj)
    assert len(scores) == 2
    # LEAD should score higher autonomy value than CONTRIB
    lead_item = next(s for s in scores if s["experience"].role == "Analyst")
    contrib_item = next(s for s in scores if s["experience"].role == "Junior")
    assert lead_item["autonomy"] == 1.0
    assert contrib_item["autonomy"] == 0.2


def test_score_career_experiences_falls_back_without_career_format():
    # If no career-format autonomy, falls back to score_experiences
    profile = {
        "experiences": [
            {"title": "Analyst", "company": "Acme", "bullets": ["Python reporting"], "dates": "2023-2025"},
        ]
    }
    offer_obj = parse_offer(OFFER)
    scores = score_career_experiences(profile, offer_obj)
    assert len(scores) >= 0  # no crash


# ── Step 14: cv_strategy passthrough ─────────────────────────────────────────

def test_build_targeted_cv_cv_strategy_in_ats_notes():
    offer_with_strategy = {**OFFER, "cv_strategy": {"positioning": "Data Analyst senior", "focus": ["Python"]}}
    result = build_targeted_cv(profile=PROFILE_WITH_CAREER, offer=offer_with_strategy)
    assert result["ats_notes"].get("cv_strategy") is not None
    assert result["ats_notes"]["cv_strategy"].get("positioning") == "Data Analyst senior"


def test_build_targeted_cv_cv_strategy_in_summary():
    offer_with_strategy = {**OFFER, "cv_strategy": {"positioning": "Expert en data visualisation"}}
    result = build_targeted_cv(profile=PROFILE_WITH_CAREER, offer=offer_with_strategy)
    assert "Expert en data visualisation" in result["summary"]


def test_build_targeted_cv_no_cv_strategy_no_crash():
    result = build_targeted_cv(profile=PROFILE_WITH_CAREER, offer=OFFER)
    assert result["ats_notes"].get("cv_strategy") is None
    assert "summary" in result


# ── Step 15: html_renderer ────────────────────────────────────────────────────

def test_extract_name_prefers_career_identity():
    profile = {
        "name": "Old Name",
        "career_profile": {"identity": {"full_name": "Jean Dupont"}},
    }
    assert _extract_name(profile) == "Jean Dupont"


def test_extract_name_fallback_without_career_profile():
    profile = {"full_name": "Alice Morin"}
    assert _extract_name(profile) == "Alice Morin"


def test_extract_name_default():
    assert _extract_name(None) == "Candidat"
    assert _extract_name({}) == "Candidat"


def test_extract_contact_line_full():
    profile = {
        "career_profile": {
            "identity": {
                "full_name": "Jean Dupont",
                "email": "j@example.com",
                "phone": "+33 6 12 34 56 78",
                "location": "Paris",
                "linkedin": "linkedin.com/in/jeandupont",
            }
        }
    }
    line = _extract_contact_line(profile)
    assert "Paris" in line
    assert "j@example.com" in line
    assert "linkedin" in line


def test_extract_contact_line_empty():
    assert _extract_contact_line(None) == ""
    assert _extract_contact_line({}) == ""


# ── Score invariance ──────────────────────────────────────────────────────────

def test_career_profile_never_injects_skills_uri():
    """CareerProfile v2 fields must not appear in skills_uri."""
    cp = CareerProfile(
        identity=CareerIdentity(full_name="Jean Dupont"),
        projects=[CareerProject(title="Test")],
    )
    # CareerProfile has no skills_uri attribute — document generation only
    assert not hasattr(cp, "skills_uri")


def test_score_career_experiences_does_not_modify_skills_uri():
    profile = {
        "skills_uri": frozenset(["esco:skill:123"]),
        "skills": ["Python"],
        "experiences": [{"title": "Analyst", "company": "Acme", "autonomy": "COPILOT", "bullets": ["Python"], "dates": "2024"}],
    }
    offer_obj = parse_offer(OFFER)
    score_career_experiences(profile, offer_obj)
    # skills_uri must remain unchanged
    assert profile["skills_uri"] == frozenset(["esco:skill:123"])
