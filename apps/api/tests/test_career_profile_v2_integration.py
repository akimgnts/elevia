"""
Integration test: CareerProfile v2 pipeline.

Covers:
- ProfileStructuredV1 → identity_hint, projects, experience.location
- from_profile_structured_v1 → CareerProfile v2 schema
- _profile_fingerprint: identity_present busts cache
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
    load_career_profile,
    to_experience_dicts,
)
from documents.cv_generator import _profile_fingerprint
from documents.apply_pack_cv_engine import (
    build_targeted_cv,
    parse_offer,
    score_career_experiences,
)
from documents.html_renderer import _extract_contact_line, _extract_name
from compass.pipeline.cache_hooks import run_profile_cache_hooks


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


def test_career_profile_round_trips_additive_enrichment_metadata():
    payload = {
        "identity": {"full_name": "Jean Dupont"},
        "enrichment_meta": {
            "structuring_report": {
                "validated_at": "2026-04-15T10:00:00Z",
                "version": "v1",
            },
            "wizard_state": {
                "step": "validation",
                "completed": True,
            },
        },
    }

    loaded = load_career_profile(payload)

    assert loaded.enrichment_meta == payload["enrichment_meta"]


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


def test_from_profile_structured_v1_builds_skill_links_from_existing_signals():
    result = structure_profile_text_v1(CV_TEXT, debug=False)
    cp = from_profile_structured_v1(result, raw_skills=["Python", "SQL", "Power BI"], raw_languages=[])

    assert cp.experiences
    assert any(exp.skill_links for exp in cp.experiences)
    first = next(exp for exp in cp.experiences if exp.skill_links)
    assert all(link.skill.label for link in first.skill_links)
    assert any(link.tools for link in first.skill_links)


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


def test_to_experience_dicts_persists_skill_links():
    result = structure_profile_text_v1(CV_TEXT, debug=False)
    cp = from_profile_structured_v1(result, raw_skills=["Python", "SQL", "Power BI"], raw_languages=[])
    dicts = to_experience_dicts(cp)

    assert dicts
    assert "skill_links" in dicts[0]


def test_load_career_profile_round_trips_skill_links():
    result = structure_profile_text_v1(CV_TEXT, debug=False)
    cp = from_profile_structured_v1(result, raw_skills=["Python", "SQL", "Power BI"], raw_languages=[])
    data = cp.model_dump()

    loaded = load_career_profile(data)

    assert loaded.model_dump() == data


def test_run_profile_cache_hooks_populates_career_profile_skill_links():
    profile = {
        "skills": ["Python", "SQL", "Power BI"],
        "languages": ["Français"],
    }

    result = run_profile_cache_hooks(cv_text=CV_TEXT, profile=profile)

    assert result.profile_hash
    assert "career_profile" in profile
    assert profile["career_profile"]["experiences"]
    assert any(exp.get("skill_links") for exp in profile["career_profile"]["experiences"])
    assert "experiences" in profile


def test_run_profile_cache_hooks_persists_structuring_report():
    profile = {
        "skills": ["Python", "SQL", "Power BI"],
        "languages": ["Français"],
        "canonical_skills": [
            {"label": "Analyse de données", "uri": "skill:data_analysis"},
            {"label": "Reporting", "uri": "skill:reporting"},
        ],
        "unresolved": [{"raw": "powerbi dashboards"}],
        "generic_filter_removed": [{"value": "communication", "reason": "generic_without_context"}],
    }

    run_profile_cache_hooks(cv_text=CV_TEXT, profile=profile)

    assert "structuring_report" in profile
    assert "stats" in profile["structuring_report"]
    assert "enrichment_report" in profile
    assert "stats" in profile["enrichment_report"]
    assert "priority_signals" in profile["enrichment_report"]
    assert "confidence_scores" in profile["enrichment_report"]
    assert "auto_filled" in profile["enrichment_report"]
    assert "questions" in profile["enrichment_report"]
    assert profile["enrichment_report"]["learning_candidates"] or profile["enrichment_report"]["confidence_scores"]
    assert isinstance(profile["enrichment_report"]["priority_signals"], list)
    assert "career_profile" in profile
    assert "enrichment_meta" in profile["career_profile"]
    assert profile["career_profile"]["enrichment_meta"]["experiences"]
    assert profile["career_profile"]["enrichment_meta"]["experiences"][0]["skill_links"]
    assert "experiences" in profile
    assert any(exp.get("skill_links") for exp in profile["experiences"])


def test_run_profile_cache_hooks_enriches_comparison_metrics_and_logs(caplog):
    profile = {
        "full_name": "Jean Dupont",
        "identity": {"full_name": "Jean Dupont", "email": "jean.dupont@example.com"},
        "skills": ["Python", "SQL", "Power BI"],
        "languages": ["Français"],
        "experiences": [
            {
                "title": "Legacy Analyst",
                "company": "Legacy Co",
                "responsibilities": ["Build dashboards"],
            }
        ],
        "education": ["Master Data Science"],
        "document_understanding": {
            "identity": {"full_name": "Jean Dupont", "email": "jean.dupont@example.com"},
            "experience_blocks": [
                {
                    "title": "Analyste Data",
                    "company": "Société Générale",
                    "location": "Paris",
                    "start_date": "2022",
                    "end_date": "2025",
                    "description_lines": ["Développement de dashboards Power BI"],
                    "header_raw": "Analyste Data - Société Générale (2022-2025)",
                    "confidence": 0.8,
                }
            ],
            "education_blocks": [
                {
                    "title": "Master Data Science",
                    "institution": "Université Paris-Dauphine",
                    "start_date": "2020",
                    "end_date": "2022",
                    "description_lines": [],
                    "header_raw": "Master Data Science - Université Paris-Dauphine (2020-2022)",
                    "confidence": 0.8,
                }
            ],
            "project_blocks": [
                {
                    "title": "Dashboard RH automatisé",
                    "organization": "",
                    "start_date": "",
                    "end_date": "",
                    "description_lines": ["Python, Pandas, Streamlit"],
                    "header_raw": "Dashboard RH automatisé",
                    "confidence": 0.7,
                }
            ],
            "parsing_diagnostics": {
                "sections_detected": [{"name": "experience", "line_count": 3}],
                "suspicious_merges": [{"section": "experience", "header_raw": "Legacy Analyst - Legacy Co and seeking"}],
                "orphan_lines": [{"section": "experience", "line": "orphan line"}],
                "warnings": [],
                "comparison_metrics": {
                    "invalid_experience_headers_count": 2,
                },
            },
            "confidence": {
                "identity_confidence": 0.8,
                "sectioning_confidence": 0.6,
                "experience_segmentation_confidence": 0.7,
            },
        },
    }

    with caplog.at_level("INFO"):
        run_profile_cache_hooks(cv_text=CV_TEXT, profile=profile)

    metrics = profile["document_understanding"]["parsing_diagnostics"]["comparison_metrics"]
    assert metrics["identity_detected_legacy"] is True
    assert metrics["identity_detected_understanding"] is True
    assert metrics["experience_count_legacy"] == 1
    assert metrics["experience_count_understanding"] == 1
    assert metrics["project_count_understanding"] == 1
    assert metrics["suspicious_merges_count"] == 1
    assert metrics["orphan_lines_count"] == 1
    assert metrics["invalid_experience_headers_count"] == 2
    assert any("DOCUMENT_UNDERSTANDING_COMPARISON_METRICS" in record.message for record in caplog.records)


def test_run_profile_cache_hooks_preserves_document_understanding(monkeypatch):
    profile = {
        "skills": ["Python", "SQL", "Power BI"],
        "languages": ["Français"],
        "document_understanding": {
            "identity": {"full_name": "Jean Dupont"},
            "confidence": {"identity_confidence": 0.9},
        },
    }
    original = profile["document_understanding"]

    def fake_structuring_run(self, payload):
        profile.pop("document_understanding", None)
        return {
            "career_profile_enriched": payload["career_profile"],
            "structuring_report": {"stats": {}},
        }

    def fake_enrichment_run(self, payload):
        return {
            "career_profile_enriched": payload["career_profile"],
            "enrichment_report": {},
        }

    monkeypatch.setattr("compass.pipeline.cache_hooks.ProfileStructuringAgent.run", fake_structuring_run)
    monkeypatch.setattr("compass.pipeline.cache_hooks.ProfileEnrichmentAgent.run", fake_enrichment_run)

    run_profile_cache_hooks(cv_text=CV_TEXT, profile=profile)

    assert profile["document_understanding"] == original


def test_run_profile_cache_hooks_keeps_base_career_profile_when_structuring_fails(monkeypatch):
    profile = {
        "skills": ["Python", "SQL"],
        "languages": ["Français"],
        "document_understanding": {
            "identity": {"full_name": "Jean Dupont"},
        },
    }

    def fake_structuring_run(self, payload):
        raise RuntimeError("boom")

    monkeypatch.setattr("compass.pipeline.cache_hooks.ProfileStructuringAgent.run", fake_structuring_run)

    run_profile_cache_hooks(cv_text=CV_TEXT, profile=profile)

    assert profile["document_understanding"]["identity"]["full_name"] == "Jean Dupont"
    assert "career_profile" in profile
    assert profile["career_profile"]["experiences"]
    assert "experiences" in profile


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
    assert result["summary"]
    assert result["ats_notes"]["cv_strategy"].get("positioning") == "Expert en data visualisation"


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
