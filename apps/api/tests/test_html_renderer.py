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
    assert "<aside class=\"sidebar\">" in html
    assert "<main class=\"main-content\">" in html
    assert "section-title\">Expérience" in html


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
