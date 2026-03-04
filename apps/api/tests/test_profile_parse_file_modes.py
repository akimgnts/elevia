from __future__ import annotations

import io
import os
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parent.parent / "src"
import sys
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="module")
def client():
    from api.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _post_txt(client, text: str, query: str = ""):
    url = "/profile/parse-file"
    if query:
        url = f"{url}?{query}"
    return client.post(
        url,
        files={"file": ("cv.txt", io.BytesIO(text.encode("utf-8")), "text/plain")},
    )


def test_parse_file_normal_canonical_compass(client):
    with patch.dict(os.environ, {"ELEVIA_ENABLE_COMPASS_E": "0"}):
        resp = _post_txt(client, "Data analyst. SQL, Python.")
    assert resp.status_code == 200, resp.text[:200]
    body = resp.json()
    assert body["pipeline_used"] == "canonical_compass"
    assert body["pipeline_variant"] == "canonical_compass_baseline"


def test_parse_file_enrich_llm_dev_only_blocked(client):
    with patch.dict(os.environ, {"ELEVIA_DEV_TOOLS": "", "ELEVIA_DEV": ""}):
        resp = _post_txt(client, "Data analyst. SQL, Python.", query="enrich_llm=1")
    assert resp.status_code == 400
    detail = resp.json().get("detail", {})
    assert "Legacy LLM enrichment is DEV-only" in detail.get("message", "")


def test_parse_file_enrich_llm_dev_only_allowed(client):
    with patch.dict(os.environ, {"ELEVIA_DEV_TOOLS": "1", "ELEVIA_ENABLE_COMPASS_E": "0"}):
        resp = _post_txt(client, "Data analyst. SQL, Python.", query="enrich_llm=1")
    assert resp.status_code == 200, resp.text[:200]
    body = resp.json()
    assert body["pipeline_used"] == "canonical_compass"
    assert body["pipeline_variant"] == "legacy_llm_enrichment"


def test_compass_e_default_on_in_dev_when_unset():
    from compass.canonical_pipeline import is_compass_e_enabled

    with patch.dict(os.environ, {"ELEVIA_ENABLE_COMPASS_E": "", "ELEVIA_DEV_TOOLS": "1"}):
        assert is_compass_e_enabled() is True
