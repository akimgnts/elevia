import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app


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
