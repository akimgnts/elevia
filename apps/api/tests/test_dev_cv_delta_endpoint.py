import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app
from api.routes import dev_tools


@pytest.fixture
def client():
    return TestClient(app)


def test_dev_cv_delta_requires_env(client, monkeypatch):
    monkeypatch.delenv("ELEVIA_DEV_TOOLS", raising=False)
    resp = client.post(
        "/dev/cv-delta",
        files={"file": ("sample.txt", b"python sql docker", "text/plain")},
    )
    assert resp.status_code == 403
    payload = resp.json()
    assert payload["error"]["code"] == "DEV_TOOLS_DISABLED"


def test_dev_cv_delta_with_llm_missing_key(client, monkeypatch):
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    resp = client.post(
        "/dev/cv-delta",
        data={"with_llm": "true"},
        files={"file": ("sample.txt", b"python sql docker", "text/plain")},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["meta"]["run_mode"] == "A"
    assert payload["meta"]["warning"]
    assert payload["canonical_count"] >= 1


def test_dev_cv_delta_schema_contract(client, monkeypatch):
    """Response must always include all required keys regardless of content."""
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    resp = client.post(
        "/dev/cv-delta",
        files={"file": ("cv.txt", b"Python Django React machine learning SQL", "text/plain")},
    )
    assert resp.status_code == 200
    payload = resp.json()
    required_keys = {
        "meta", "canonical_count", "added_skills",
        "removed_skills", "unchanged_skills_count", "added_esco", "removed_esco",
    }
    assert required_keys.issubset(payload.keys()), f"Missing: {required_keys - payload.keys()}"
    meta = payload["meta"]
    assert meta["run_mode"] in {"A", "A+B"}
    assert isinstance(payload["canonical_count"], int)
    assert isinstance(payload["added_skills"], list)
    assert isinstance(payload["removed_skills"], list)


def test_dev_cv_delta_get_not_allowed(client):
    """GET /dev/cv-delta must return 405, not 404."""
    resp = client.get("/dev/cv-delta")
    assert resp.status_code == 405


def test_dev_cv_delta_pdf_upload_clean_422(client, monkeypatch):
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    pdf_path = Path(__file__).parent.parent / "fixtures" / "cv_samples" / "sample_cv.pdf"
    assert pdf_path.exists(), "Missing PDF fixture"
    with pdf_path.open("rb") as handle:
        resp = client.post(
            "/dev/cv-delta",
            files={"file": ("sample_cv.pdf", handle, "application/pdf")},
        )
    assert resp.status_code in {200, 422}
    if resp.status_code == 422:
        payload = resp.json()
        assert payload["error"]["code"] in {"PDF_TEXT_EMPTY", "PDF_PARSE_FAILED", "PDF_PARSER_UNAVAILABLE"}


def test_dev_cv_delta_rejects_unsupported_filetype(client, monkeypatch):
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    resp = client.post(
        "/dev/cv-delta",
        files={"file": ("sample.docx", b"not a docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert resp.status_code == 415
    payload = resp.json()
    assert payload["error"]["code"] == "UNSUPPORTED_FILETYPE"


def test_dev_cv_delta_rejects_large_file(client, monkeypatch):
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    data = b"a" * (dev_tools.MAX_FILE_BYTES + 1)
    resp = client.post(
        "/dev/cv-delta",
        files={"file": ("big.txt", data, "text/plain")},
    )
    assert resp.status_code == 413
    payload = resp.json()
    assert payload["error"]["code"] == "FILE_TOO_LARGE"
