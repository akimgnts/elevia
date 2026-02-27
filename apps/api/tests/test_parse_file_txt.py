"""
QA — POST /profile/parse-file endpoint tests.

Covers: TXT upload, determinism, schema, skill count, error cases.
Fast (<1s), no LLM, no external deps.
"""
import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

CV_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "cv" / "cv_fixture_v0.txt"

TECH_CV = "Python SQL Docker Git Excel Pandas machine learning ETL statistics data analysis"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    import os
    os.environ.setdefault("ELEVIA_DEV_TOOLS", "1")
    from api.main import app
    return TestClient(app)


def _post_txt(client, text: str, filename: str = "cv.txt"):
    """Helper: POST text as a TXT file upload."""
    return client.post(
        "/profile/parse-file",
        files={"file": (filename, io.BytesIO(text.encode("utf-8")), "text/plain")},
    )


# ── Basic contract ────────────────────────────────────────────────────────────

def test_parse_file_txt_returns_200(client):
    """Valid TXT upload must return 200."""
    resp = _post_txt(client, TECH_CV)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"


def test_parse_file_txt_schema(client):
    """Response must include all required fields with correct types."""
    resp = _post_txt(client, TECH_CV)
    assert resp.status_code == 200
    body = resp.json()
    required = {"source", "mode", "ai_available", "ai_added_count", "filename", "content_type", "extracted_text_length",
                "canonical_count", "skills_raw", "skills_canonical", "profile", "warnings",
                "raw_tokens", "filtered_tokens", "validated_labels"}
    assert required.issubset(body.keys()), f"Missing keys: {required - body.keys()}"
    assert body["source"] == "baseline"
    assert body["mode"] in {"baseline", "llm"}
    assert isinstance(body["canonical_count"], int)
    assert isinstance(body["skills_raw"], list)
    assert isinstance(body["skills_canonical"], list)
    assert isinstance(body["profile"], dict)
    assert isinstance(body["warnings"], list)


def test_parse_file_txt_profile_shape(client):
    """Profile dict must be inbox-compatible: has 'id' and 'skills' list."""
    resp = _post_txt(client, TECH_CV)
    assert resp.status_code == 200
    profile = resp.json()["profile"]
    assert "skills" in profile, "profile missing 'skills'"
    assert isinstance(profile["skills"], list)


def test_parse_file_txt_filename_in_response(client):
    """Filename in response must match uploaded filename (sanitized)."""
    resp = _post_txt(client, TECH_CV, filename="my_cv.txt")
    assert resp.status_code == 200
    assert resp.json()["filename"] == "my_cv.txt"


def test_parse_file_txt_extracted_text_length(client):
    """extracted_text_length must be > 0 for non-empty input."""
    resp = _post_txt(client, TECH_CV)
    assert resp.status_code == 200
    assert resp.json()["extracted_text_length"] > 0


# ── Fixture-based tests ───────────────────────────────────────────────────────

def test_parse_file_fixture_exists():
    """CV fixture file must be present."""
    assert CV_FIXTURE_PATH.exists(), f"Missing fixture: {CV_FIXTURE_PATH}"


def test_parse_file_fixture_minimum_count(client):
    """Fixture CV must yield >= 10 canonical skills via parse-file."""
    assert CV_FIXTURE_PATH.exists(), "Fixture missing — skip"
    text = CV_FIXTURE_PATH.read_text(encoding="utf-8")
    resp = _post_txt(client, text, filename="cv_fixture_v0.txt")
    assert resp.status_code == 200
    count = resp.json()["canonical_count"]
    assert count >= 10, f"Expected >= 10 canonical skills, got {count}"


def test_parse_file_fixture_deterministic(client):
    """Same fixture → same output twice (determinism)."""
    assert CV_FIXTURE_PATH.exists(), "Fixture missing — skip"
    text = CV_FIXTURE_PATH.read_text(encoding="utf-8")
    r1 = _post_txt(client, text)
    r2 = _post_txt(client, text)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["canonical_count"] == r2.json()["canonical_count"]
    assert r1.json()["skills_canonical"] == r2.json()["skills_canonical"]


# ── Error cases ───────────────────────────────────────────────────────────────

def test_parse_file_unsupported_type_returns_415(client):
    """Uploading a non-PDF/TXT file type must return 415."""
    resp = client.post(
        "/profile/parse-file",
        files={"file": ("doc.docx", io.BytesIO(b"dummy"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert resp.status_code == 415, f"Expected 415, got {resp.status_code}"


def test_parse_file_empty_txt_returns_422(client):
    """Empty text file must return 422 (no text extracted)."""
    resp = _post_txt(client, "   \n\t  ", filename="empty.txt")
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"


def test_parse_file_txt_content_type_in_response(client):
    """content_type field must reflect the uploaded file type."""
    resp = _post_txt(client, TECH_CV)
    assert resp.status_code == 200
    ct = resp.json()["content_type"]
    assert "text" in ct or ct == "application/octet-stream"


def test_parse_file_debug_arrays_capped(client):
    """Debug arrays must be present and capped."""
    resp = _post_txt(client, TECH_CV)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body.get("raw_tokens", [])) <= 200
    assert len(body.get("filtered_tokens", [])) <= 200
    assert len(body.get("validated_labels", [])) <= 200
