"""Tests for Analyze recovery persistence cache and determinism."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ── Path setup ─────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))


def _payload(fingerprint: str) -> dict:
    return {
        "cluster": "DATA_IT",
        "ignored_tokens": ["machine learning", "power bi"],
        "noise_tokens": ["paris"],
        "validated_esco_labels": [],
        "profile_fingerprint": fingerprint,
    }


def test_cache_hit_on_second_call(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ELEVIA_ANALYZE_RECOVERY_DB", str(tmp_path / "cache.db"))

    from fastapi.testclient import TestClient
    from api.main import app

    mock_llm_response = [
        {
            "label": "Power BI",
            "kind": "tool",
            "confidence": 0.9,
            "source": "ignored_token",
            "evidence": "power bi",
            "why_cluster_fit": "data it",
        },
        {
            "label": "Machine Learning",
            "kind": "method",
            "confidence": 0.9,
            "source": "ignored_token",
            "evidence": "machine learning",
            "why_cluster_fit": "data it",
        },
    ]

    with patch("compass.analyze_skill_recovery._call_llm", return_value=mock_llm_response):
        client = TestClient(app, raise_server_exceptions=False)
        first = client.post("/analyze/recover-skills", json=_payload("pf-1")).json()
        second = client.post("/analyze/recover-skills", json=_payload("pf-1")).json()

    assert first.get("cache_hit") is False
    assert first.get("ai_fired") is True
    assert second.get("cache_hit") is True
    assert second.get("ai_fired") is False
    assert first.get("recovered_skills") == second.get("recovered_skills")


def test_cache_miss_for_different_fingerprint(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ELEVIA_ANALYZE_RECOVERY_DB", str(tmp_path / "cache.db"))

    from fastapi.testclient import TestClient
    from api.main import app

    mock_llm_response = [
        {
            "label": "Machine Learning",
            "kind": "method",
            "confidence": 0.9,
            "source": "ignored_token",
            "evidence": "machine learning",
            "why_cluster_fit": "data it",
        }
    ]

    with patch("compass.analyze_skill_recovery._call_llm", return_value=mock_llm_response):
        client = TestClient(app, raise_server_exceptions=False)
        a = client.post("/analyze/recover-skills", json=_payload("pf-A")).json()
        b = client.post("/analyze/recover-skills", json=_payload("pf-B")).json()

    assert a.get("cache_hit") is False
    assert b.get("cache_hit") is False
    assert a.get("request_hash") == b.get("request_hash")


def test_deterministic_ordering(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ELEVIA_ANALYZE_RECOVERY_DB", str(tmp_path / "cache.db"))

    from fastapi.testclient import TestClient
    from api.main import app

    # Reverse order to verify stable sort
    mock_llm_response = [
        {
            "label": "Power BI",
            "kind": "tool",
            "confidence": 0.9,
            "source": "ignored_token",
            "evidence": "power bi",
            "why_cluster_fit": "data it",
        },
        {
            "label": "Machine Learning",
            "kind": "method",
            "confidence": 0.9,
            "source": "ignored_token",
            "evidence": "machine learning",
            "why_cluster_fit": "data it",
        },
    ]

    with patch("compass.analyze_skill_recovery._call_llm", return_value=mock_llm_response):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/analyze/recover-skills", json=_payload("pf-sort")).json()

    labels = [s.get("label") for s in resp.get("recovered_skills", [])]
    assert labels == sorted(labels, key=lambda s: s.lower())
