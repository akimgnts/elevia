"""
Unit tests for HTML CV renderer.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from documents.html_renderer import render_cv_html
from documents.schemas import AtsNotes, AutonomyEnum, CvDocumentPayload, CvMeta, ExperienceBlock


def _sample_payload(summary: str = "Profil data") -> CvDocumentPayload:
    return CvDocumentPayload(
        summary=summary,
        keywords_injected=["SQL", "Python"],
        experience_blocks=[
            ExperienceBlock(
                title="Data Analyst",
                company="ACME",
                bullets=["Analyse", "Reporting"],
                tools=["SQL", "Python"],
                autonomy=AutonomyEnum.COPILOT,
                impact=None,
            )
        ],
        ats_notes=AtsNotes(
            matched_keywords=["sql"],
            missing_keywords=["power bi"],
            ats_score_estimate=80,
        ),
        cv={
            "title": "Data Analyst",
            "experiences": [
                {
                    "role": "Data Analyst",
                    "company": "ACME",
                    "dates": "2024-2025",
                    "bullets": ["Analyser les données de vente."],
                    "decision": "keep",
                }
            ],
            "skills": ["SQL", "Python"],
            "education": ["Master Data — ACME School"],
            "layout": "single_column",
        },
        meta=CvMeta(
            offer_id="offer-1",
            profile_fingerprint="abc123",
            cache_hit=False,
            fallback_used=False,
        ),
    )


def test_html_contains_sections():
    payload = _sample_payload()
    html = render_cv_html(payload, profile={"name": "Test"}, offer={"title": "Offer"})
    assert "<h1>Data Analyst</h1>" in html
    assert "<h2>Expérience</h2>" in html
    assert "<h2>Formation</h2>" in html
    assert "<h2>Compétences</h2>" in html


def test_html_escapes_values():
    payload = _sample_payload(summary="Hello <script>alert(1)</script>")
    html = render_cv_html(payload, profile={"name": "<script>x</script>"}, offer=None)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_html_no_ats_terms():
    payload = _sample_payload()
    html = render_cv_html(payload, profile=None, offer=None)
    assert "ATS" not in html
    assert "ats_score_estimate" not in html
    assert "sidebar" not in html


def test_html_v2_uses_skill_links_for_experience_and_skills_sections():
    payload = _sample_payload()
    profile = {
        "career_profile": {
            "base_title": "Data Analyst",
            "experiences": [
                {
                    "title": "Data Analyst",
                    "company": "ACME",
                    "start_date": "2024",
                    "end_date": "2025",
                    "skill_links": [
                        {
                            "skill": {"label": "Analyse de donnees"},
                            "tools": [{"label": "Python"}, {"label": "SQL"}, {"label": "Power BI"}],
                            "context": "analyse de performance",
                            "autonomy_level": "autonomous",
                        }
                    ],
                    "responsibilities": ["Ancienne ligne"],
                    "tools": ["Excel"],
                    "skills": ["reporting"],
                }
            ],
        }
    }

    html = render_cv_html(payload, template_version="cv_v2", profile=profile, offer={"title": "Data Analyst"})

    assert "Analyse de donnees avec Python, SQL et Power BI dans un contexte de analyse de performance." in html
    assert "Pratique autonome de analyse de donnees, avec arbitrages sur le perimetre." in html
    assert "Analyse de donnees" in html
    assert "Python" in html
    assert "Power BI" in html
