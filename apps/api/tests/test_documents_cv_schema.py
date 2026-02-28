"""
test_documents_cv_schema.py — Pydantic v2 schema validation tests.

Tests:
  - Valid CvDocumentPayload parses correctly
  - ExperienceBlock autonomy enum validated
  - AtsNotes ats_score_estimate range (0-100)
  - CvRequest requires offer_id
  - Missing required fields raise ValidationError
  - Extra unknown fields: behaviour
  - CvDocumentResponse envelopes correctly
  - model_dump produces clean JSON-serializable dict
"""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from documents.schemas import (
    AtsNotes,
    AutonomyEnum,
    CvDocumentPayload,
    CvDocumentResponse,
    CvMeta,
    CvRequest,
    ExperienceBlock,
    PROMPT_VERSION,
)


# ── Minimal valid fixtures ────────────────────────────────────────────────────

def _valid_meta(**overrides):
    return {
        "offer_id": "BF-123",
        "profile_fingerprint": "abcd1234",
        "prompt_version": PROMPT_VERSION,
        "cache_hit": False,
        "fallback_used": False,
        **overrides,
    }


def _valid_ats_notes(**overrides):
    return {
        "matched_keywords": ["python", "sql"],
        "missing_keywords": ["docker"],
        "ats_score_estimate": 67,
        **overrides,
    }


def _valid_exp_block(**overrides):
    return {
        "title": "Data Analyst",
        "company": "Acme Corp",
        "bullets": ["Analysed KPIs", "Built dashboards", "Presented to stakeholders"],
        "tools": ["python", "sql"],
        "autonomy": "COPILOT",
        "impact": None,
        **overrides,
    }


def _valid_payload(**overrides):
    return {
        "summary": "Ligne 1.\nLigne 2.\nLigne 3.",
        "keywords_injected": ["python", "sql"],
        "experience_blocks": [_valid_exp_block()],
        "ats_notes": _valid_ats_notes(),
        "meta": _valid_meta(),
        **overrides,
    }


# ── CvDocumentPayload ─────────────────────────────────────────────────────────

def test_valid_payload_parses():
    """A valid payload dict constructs a CvDocumentPayload without error."""
    p = CvDocumentPayload.model_validate(_valid_payload())
    assert p.summary.startswith("Ligne 1")
    assert p.ats_notes.ats_score_estimate == 67
    assert len(p.experience_blocks) == 1


def test_payload_missing_summary_raises():
    """summary is required — missing → ValidationError."""
    data = _valid_payload()
    del data["summary"]
    with pytest.raises(ValidationError):
        CvDocumentPayload.model_validate(data)


def test_payload_missing_ats_notes_raises():
    """ats_notes is required."""
    data = _valid_payload()
    del data["ats_notes"]
    with pytest.raises(ValidationError):
        CvDocumentPayload.model_validate(data)


def test_payload_missing_meta_raises():
    """meta is required."""
    data = _valid_payload()
    del data["meta"]
    with pytest.raises(ValidationError):
        CvDocumentPayload.model_validate(data)


def test_payload_empty_experience_blocks():
    """experience_blocks can be empty list."""
    p = CvDocumentPayload.model_validate(_valid_payload(experience_blocks=[]))
    assert p.experience_blocks == []


def test_payload_max_experience_blocks():
    """experience_blocks max 3 (Pydantic constraint)."""
    blocks = [_valid_exp_block() for _ in range(4)]
    with pytest.raises(ValidationError):
        CvDocumentPayload.model_validate(_valid_payload(experience_blocks=blocks))


def test_payload_max_keywords_injected():
    """keywords_injected max 12."""
    kws = [f"kw{i}" for i in range(13)]
    with pytest.raises(ValidationError):
        CvDocumentPayload.model_validate(_valid_payload(keywords_injected=kws))


def test_payload_model_dump_json_serializable():
    """model_dump() result is JSON-serializable (no datetime objects etc)."""
    import json
    p = CvDocumentPayload.model_validate(_valid_payload())
    d = p.model_dump()
    serialized = json.dumps(d)  # should not raise
    assert '"summary"' in serialized


# ── ExperienceBlock ───────────────────────────────────────────────────────────

def test_autonomy_valid_values():
    """All valid autonomy enum values are accepted."""
    for val in ("CONTRIB", "COPILOT", "LEAD"):
        b = ExperienceBlock.model_validate({**_valid_exp_block(), "autonomy": val})
        assert b.autonomy == AutonomyEnum(val)


def test_autonomy_invalid_raises():
    """Invalid autonomy value → ValidationError."""
    with pytest.raises(ValidationError):
        ExperienceBlock.model_validate({**_valid_exp_block(), "autonomy": "EXPERT"})


def test_experience_block_min_bullets():
    """bullets minimum 1."""
    with pytest.raises(ValidationError):
        ExperienceBlock.model_validate({**_valid_exp_block(), "bullets": []})


def test_experience_block_max_bullets():
    """bullets maximum 5."""
    with pytest.raises(ValidationError):
        ExperienceBlock.model_validate({**_valid_exp_block(),
                                        "bullets": ["b"] * 6})


def test_experience_block_max_tools():
    """tools max 8."""
    with pytest.raises(ValidationError):
        ExperienceBlock.model_validate({**_valid_exp_block(),
                                        "tools": ["t"] * 9})


# ── AtsNotes ─────────────────────────────────────────────────────────────────

def test_ats_score_range_valid():
    """ats_score_estimate accepts 0 and 100."""
    AtsNotes.model_validate({**_valid_ats_notes(), "ats_score_estimate": 0})
    AtsNotes.model_validate({**_valid_ats_notes(), "ats_score_estimate": 100})


def test_ats_score_below_0_raises():
    with pytest.raises(ValidationError):
        AtsNotes.model_validate({**_valid_ats_notes(), "ats_score_estimate": -1})


def test_ats_score_above_100_raises():
    with pytest.raises(ValidationError):
        AtsNotes.model_validate({**_valid_ats_notes(), "ats_score_estimate": 101})


# ── CvRequest ─────────────────────────────────────────────────────────────────

def test_cv_request_minimal():
    """offer_id is sufficient; profile and profile_id can be omitted."""
    r = CvRequest.model_validate({"offer_id": "BF-99"})
    assert r.offer_id == "BF-99"
    assert r.lang == "fr"
    assert r.style == "ats_compact"


def test_cv_request_missing_offer_id_raises():
    with pytest.raises(ValidationError):
        CvRequest.model_validate({"profile": {"skills": ["python"]}})


def test_cv_request_lang_enum():
    """Only 'fr' and 'en' are valid lang values."""
    CvRequest.model_validate({"offer_id": "X", "lang": "fr"})
    CvRequest.model_validate({"offer_id": "X", "lang": "en"})
    with pytest.raises(ValidationError):
        CvRequest.model_validate({"offer_id": "X", "lang": "de"})


def test_cv_request_style_enum():
    """Only 'ats_compact' is valid style."""
    with pytest.raises(ValidationError):
        CvRequest.model_validate({"offer_id": "X", "style": "creative"})


# ── CvDocumentResponse ────────────────────────────────────────────────────────

def test_cv_response_wraps_payload():
    """CvDocumentResponse wraps payload + duration_ms correctly."""
    payload = CvDocumentPayload.model_validate(_valid_payload())
    resp = CvDocumentResponse(ok=True, document=payload, duration_ms=42)
    assert resp.ok is True
    assert resp.duration_ms == 42
    assert resp.document.summary.startswith("Ligne")
