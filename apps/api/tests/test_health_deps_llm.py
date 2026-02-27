"""Tests for /health/deps LLM status flag."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(scope="module")
def client():
    from api.main import app
    return TestClient(app)


def test_health_deps_llm_missing(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    resp = client.get("/health/deps")
    assert resp.status_code == 200
    llm = resp.json().get("deps", {}).get("llm", {})
    assert llm.get("status") == "missing"
    assert llm.get("provider") == "openai"
    assert llm.get("key_present") is False


def test_health_deps_llm_ok(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    resp = client.get("/health/deps")
    assert resp.status_code == 200
    llm = resp.json().get("deps", {}).get("llm", {})
    assert llm.get("status") == "ok"
    assert llm.get("provider") == "openai"
    assert llm.get("key_present") is True
