"""
test_cv_for_offer.py — Integration + unit tests for POST /documents/cv/for-offer.

Tests:
  - Missing offer_id → 422
  - Unknown offer_id → 404
  - Happy path (fallback, LLM disabled) → 200 + ForOfferResponse schema
  - context_used=True when matched_skills provided
  - Matched skills appear first in keywords_injected (ordering contract)
  - Determinism: same request → same preview_text (hash stable)
  - preview_text non-empty with expected sections
  - SEC: no API key in response
  - enrich_payload unit test (no DB needed)
  - render_preview_markdown unit test (no DB needed)
"""

import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── Unit tests (no DB, no app) ────────────────────────────────────────────────

def test_enrich_payload_matched_first():
    """Matched skills appear before unmatched in keywords_injected."""
    from documents.cv_generator import enrich_payload
    from documents.schemas import CvDocumentPayload, AtsNotes, CvMeta, PROMPT_VERSION

    payload = CvDocumentPayload(
        summary="Test summary.",
        keywords_injected=["excel", "python", "sql", "machine learning"],
        experience_blocks=[],
        ats_notes=AtsNotes(matched_keywords=["python"], missing_keywords=[], ats_score_estimate=50),
        meta=CvMeta(offer_id="X", profile_fingerprint="fp", prompt_version=PROMPT_VERSION),
    )

    enriched = enrich_payload(payload, matched_core_skills=["python", "sql"])
    kws = enriched.keywords_injected

    # python and sql must appear before excel and machine learning
    matched_norm = {"python", "sql"}
    matched_positions = [i for i, k in enumerate(kws) if k.lower() in matched_norm]
    rest_positions = [i for i, k in enumerate(kws) if k.lower() not in matched_norm]

    assert matched_positions, "No matched skills in output"
    assert max(matched_positions) < min(rest_positions), "Matched must come before unmatched"


def test_enrich_payload_no_matched_noop():
    """Empty matched_core_skills → payload unchanged."""
    from documents.cv_generator import enrich_payload
    from documents.schemas import CvDocumentPayload, AtsNotes, CvMeta, PROMPT_VERSION

    payload = CvDocumentPayload(
        summary="Test.",
        keywords_injected=["excel", "python"],
        experience_blocks=[],
        ats_notes=AtsNotes(matched_keywords=[], missing_keywords=[], ats_score_estimate=0),
        meta=CvMeta(offer_id="X", profile_fingerprint="fp", prompt_version=PROMPT_VERSION),
    )
    enriched = enrich_payload(payload, matched_core_skills=[])
    assert enriched.keywords_injected == ["excel", "python"]


def test_enrich_payload_deterministic():
    """Same inputs → same output (no set iteration)."""
    from documents.cv_generator import enrich_payload
    from documents.schemas import CvDocumentPayload, AtsNotes, CvMeta, PROMPT_VERSION

    payload = CvDocumentPayload(
        summary="Test.",
        keywords_injected=["pandas", "python", "sql", "excel", "machine learning"],
        experience_blocks=[],
        ats_notes=AtsNotes(matched_keywords=[], missing_keywords=[], ats_score_estimate=0),
        meta=CvMeta(offer_id="X", profile_fingerprint="fp", prompt_version=PROMPT_VERSION),
    )
    matched = ["python", "sql", "pandas"]
    r1 = enrich_payload(payload, matched).keywords_injected
    r2 = enrich_payload(payload, matched).keywords_injected
    assert r1 == r2


def test_render_preview_markdown_sections():
    """preview_text contains expected sections."""
    from documents.preview_renderer import render_preview_markdown
    from documents.schemas import CvDocumentPayload, AtsNotes, CvMeta, PROMPT_VERSION

    payload = CvDocumentPayload(
        summary="Profil data analyst orienté résultats.",
        keywords_injected=["python", "sql"],
        experience_blocks=[],
        ats_notes=AtsNotes(
            matched_keywords=["python"],
            missing_keywords=["docker"],
            ats_score_estimate=60,
        ),
        cv={
            "title": "Data Analyst VIE",
            "experiences": [
                {
                    "role": "Data Analyst",
                    "company": "Acme",
                    "dates": "2024-2025",
                    "bullets": ["Analyser les données commerciales."],
                    "decision": "keep",
                }
            ],
            "skills": ["python", "sql"],
            "education": ["Master data"],
            "layout": "single_column",
        },
        meta=CvMeta(offer_id="BF-1", profile_fingerprint="fp", prompt_version=PROMPT_VERSION),
    )
    preview = render_preview_markdown(
        payload,
        offer_title="Data Analyst VIE",
        offer_company="Acme",
        offer_country="DE",
    )
    assert "## Expériences" in preview
    assert "## Formation" in preview
    assert "## Compétences" in preview
    assert "Data Analyst VIE" in preview


def test_render_preview_markdown_deterministic():
    """Same payload → same markdown."""
    from documents.preview_renderer import render_preview_markdown
    from documents.schemas import CvDocumentPayload, AtsNotes, CvMeta, PROMPT_VERSION

    payload = CvDocumentPayload(
        summary="Résumé stable.",
        keywords_injected=["python", "sql"],
        experience_blocks=[],
        ats_notes=AtsNotes(matched_keywords=["python"], missing_keywords=[], ats_score_estimate=70),
        meta=CvMeta(offer_id="BF-1", profile_fingerprint="fp00", prompt_version=PROMPT_VERSION),
    )
    r1 = render_preview_markdown(payload, "Title", "Company", "FR")
    r2 = render_preview_markdown(payload, "Title", "Company", "FR")
    assert r1 == r2
    assert hashlib.sha256(r1.encode()).hexdigest() == hashlib.sha256(r2.encode()).hexdigest()


def test_build_matched_skills_from_context():
    """When matched_skills provided, returns them sorted and normalized."""
    from documents.context_builder import build_matched_skills

    matched, missing = build_matched_skills(
        offer={},
        profile={},
        matched_skills=["Python", "SQL", "Excel"],
        missing_skills=["Machine Learning"],
    )
    assert matched == ["excel", "python", "sql"]  # sorted, lowercased
    assert missing == ["machine learning"]


def test_build_matched_skills_fallback():
    """Without context, computes from ATS keywords vs profile skills."""
    from documents.context_builder import build_matched_skills

    matched, missing = build_matched_skills(
        offer={"title": "Data Analyst", "description": "Requires Python and SQL skills."},
        profile={"skills": ["Python", "PowerBI"]},
    )
    # python should be matched (profile has Python, offer mentions python)
    assert isinstance(matched, list)
    assert isinstance(missing, list)
    assert all(m == m.lower() for m in matched)  # all lowercased


# ── App fixture (LLM disabled) ────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    with patch.dict("os.environ", {"OPENAI_API_KEY": "", "LLM_API_KEY": "", "OPENAI_KEY": ""}, clear=False):
        from api.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


def _for_offer_payload(offer_id="BF-237241", matched_skills=None, missing_skills=None):
    ctx = None
    if matched_skills is not None:
        ctx = {"matched_skills": matched_skills, "missing_skills": missing_skills or []}
    body = {
        "offer_id": offer_id,
        "profile": {"skills": ["python", "sql", "analyse de données"], "education": "bac+5"},
        "lang": "fr",
    }
    if ctx:
        body["context"] = ctx
    return body


# ── Endpoint tests ─────────────────────────────────────────────────────────────

def test_for_offer_missing_offer_id_422(client):
    resp = client.post("/documents/cv/for-offer", json={"profile": {"skills": ["python"]}})
    assert resp.status_code == 422


def test_for_offer_unknown_offer_404(client):
    resp = client.post("/documents/cv/for-offer", json=_for_offer_payload("NONEXISTENT_ZZZ_999"))
    assert resp.status_code == 404


def test_for_offer_happy_path(client):
    """Happy path: 200 + ForOfferResponse schema."""
    resp = client.post("/documents/cv/for-offer", json=_for_offer_payload())
    if resp.status_code == 404:
        pytest.skip("BF-237241 not in DB — run ingestion first")

    assert resp.status_code == 200
    data = resp.json()

    assert data["ok"] is True
    assert "document" in data
    assert "preview_text" in data
    assert isinstance(data["preview_text"], str)
    assert len(data["preview_text"]) > 20
    assert isinstance(data["context_used"], bool)
    assert isinstance(data["duration_ms"], int)

    doc = data["document"]
    assert "summary" in doc
    assert "keywords_injected" in doc
    assert "ats_notes" in doc
    assert "meta" in doc


def test_for_offer_context_used_flag(client):
    """context_used=True only when matched_skills provided."""
    r_no_ctx = client.post("/documents/cv/for-offer", json=_for_offer_payload())
    if r_no_ctx.status_code == 404:
        pytest.skip("BF-237241 not in DB")

    r_with_ctx = client.post(
        "/documents/cv/for-offer",
        json=_for_offer_payload(matched_skills=["python", "sql"]),
    )
    assert r_no_ctx.json()["context_used"] is False
    assert r_with_ctx.json()["context_used"] is True


def test_for_offer_matched_skills_ordered_first(client):
    """Matched skills appear before unmatched in keywords_injected."""
    resp = client.post(
        "/documents/cv/for-offer",
        json=_for_offer_payload(matched_skills=["python", "sql"]),
    )
    if resp.status_code == 404:
        pytest.skip("BF-237241 not in DB")
    assert resp.status_code == 200

    kws = resp.json()["document"]["keywords_injected"]
    if len(kws) < 2:
        pytest.skip("Not enough keywords to test ordering")

    matched_norm = {"python", "sql"}
    matched_pos = [i for i, k in enumerate(kws) if k.lower() in matched_norm]
    rest_pos = [i for i, k in enumerate(kws) if k.lower() not in matched_norm]

    if matched_pos and rest_pos:
        assert max(matched_pos) < min(rest_pos), "Matched keywords must precede unmatched"


def test_for_offer_determinism(client):
    """Same request → same preview_text on repeated calls (hash stable)."""
    body = _for_offer_payload(matched_skills=["python"])
    r1 = client.post("/documents/cv/for-offer", json=body)
    if r1.status_code != 200:
        pytest.skip("Offer not available")
    r2 = client.post("/documents/cv/for-offer", json=body)
    assert r2.status_code == 200
    assert r1.json()["preview_text"] == r2.json()["preview_text"]


def test_for_offer_preview_has_ats_section(client):
    """preview_text contains the ATS-friendly CV sections."""
    resp = client.post("/documents/cv/for-offer", json=_for_offer_payload())
    if resp.status_code != 200:
        pytest.skip("Offer not available")
    assert "## Expériences" in resp.json()["preview_text"]
    assert "## Compétences" in resp.json()["preview_text"]


def test_for_offer_no_secret_in_response(client):
    """SEC: no API key pattern in response body."""
    resp = client.post("/documents/cv/for-offer", json=_for_offer_payload())
    raw = resp.text
    assert "sk-" not in raw
    assert "OPENAI_API_KEY" not in raw
    assert "LLM_API_KEY" not in raw
