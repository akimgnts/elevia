"""
test_analyze_skill_recovery.py — Backend tests for cluster-aware AI skill recovery.

Tests (4):
  1. test_recovery_rejects_generic_words            — guardrail filter rejects soft skills / generic
  2. test_recovery_recombines_machine_learning       — multi-word skill survives filter
  3. test_recovery_caps_to_20                        — result capped at MAX_RECOVERED_SKILLS
  4. test_endpoint_dev_only_gate                     — endpoint returns 400 without ELEVIA_DEV_TOOLS=1

No real LLM calls — LLM layer is mocked.
"""
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

from compass.analyze_skill_recovery import (
    MAX_RECOVERED_SKILLS,
    RecoveredSkillItem,
    RecoveryResult,
    _filter_recovered,
    _is_valid_label,
    recover_skills_cluster_aware,
)


# ── Helper ─────────────────────────────────────────────────────────────────────

def _make_raw_item(label: str, **kwargs) -> dict:
    return {
        "label": label,
        "kind": kwargs.get("kind", "tool"),
        "confidence": kwargs.get("confidence", 0.8),
        "source": kwargs.get("source", "ignored_token"),
        "evidence": kwargs.get("evidence", f"found '{label}' in tokens"),
        "why_cluster_fit": kwargs.get("why_cluster_fit", "relevant to cluster"),
    }


# ── Test 1: guardrail rejects generic words ────────────────────────────────────

class TestRecoveryRejectsGenericWords:
    """Deterministic guardrail filter rejects soft skills, verbs, stopwords."""

    def test_autonomie_rejected(self):
        valid, reason = _is_valid_label("autonomie", "DATA_IT")
        assert not valid, f"Expected 'autonomie' to be rejected, got reason={reason}"
        assert reason == "generic_blacklist"

    def test_leadership_rejected(self):
        valid, reason = _is_valid_label("leadership", "DATA_IT")
        assert not valid

    def test_communication_rejected(self):
        valid, reason = _is_valid_label("communication", "DATA_IT")
        assert not valid

    def test_short_label_rejected(self):
        valid, reason = _is_valid_label("ab", "DATA_IT")
        assert not valid, f"Expected 2-char label rejected, got reason={reason}"

    def test_number_only_rejected(self):
        valid, reason = _is_valid_label("2024", "DATA_IT")
        assert not valid
        assert reason == "number_only"

    def test_handle_slug_rejected(self):
        # Pure lowercase slug of 8 chars or fewer that matches handle pattern
        valid, reason = _is_valid_label("ml-v2", "DATA_IT")
        assert not valid
        assert reason == "looks_like_handle"

    def test_filter_removes_generics_from_list(self):
        raw = [
            _make_raw_item("autonomie"),
            _make_raw_item("leadership"),
            _make_raw_item("Python"),  # valid for DATA_IT
        ]
        out = _filter_recovered(raw, cluster="DATA_IT", esco_labels_lower=set())
        labels = [s.label for s in out]
        assert "autonomie" not in labels
        assert "leadership" not in labels
        assert "Python" in labels

    def test_esco_duplicate_rejected(self):
        """Labels already in validated_esco_labels are skipped."""
        raw = [_make_raw_item("Python"), _make_raw_item("SQL")]
        esco_lower = {"python"}
        out = _filter_recovered(raw, cluster="DATA_IT", esco_labels_lower=esco_lower)
        labels = [s.label for s in out]
        assert "Python" not in labels
        assert "SQL" in labels


# ── Test 2: multi-word recombination survives filter ──────────────────────────

class TestRecoveryRecombinesMachinelearning:
    """Multi-word technical labels pass the guardrail when cluster-coherent."""

    def test_machine_learning_valid(self):
        valid, reason = _is_valid_label("Machine Learning", "DATA_IT")
        assert valid, f"Expected 'Machine Learning' to be valid, got reason={reason}"

    def test_power_bi_valid(self):
        valid, reason = _is_valid_label("Power BI", "DATA_IT")
        assert valid, f"Expected 'Power BI' to be valid, got reason={reason}"

    def test_apache_spark_valid(self):
        valid, reason = _is_valid_label("Apache Spark", "DATA_IT")
        assert valid

    def test_machine_learning_survives_filter(self):
        raw = [_make_raw_item("Machine Learning")]
        out = _filter_recovered(raw, cluster="DATA_IT", esco_labels_lower=set())
        assert len(out) == 1
        assert out[0].label == "Machine Learning"

    def test_full_pipeline_with_mock_llm(self, monkeypatch):
        """recover_skills_cluster_aware returns multi-word label when LLM is mocked."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
        monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")

        mock_llm_response = [
            {
                "label": "Machine Learning",
                "kind": "method",
                "confidence": 0.92,
                "source": "recombined",
                "evidence": "machine learning pipeline",
                "why_cluster_fit": "core DATA_IT technique",
            }
        ]

        with patch(
            "compass.analyze_skill_recovery._call_llm",
            return_value=mock_llm_response,
        ):
            result = recover_skills_cluster_aware(
                cluster="DATA_IT",
                ignored_tokens=["machine", "learning"],
                validated_esco_labels=[],
            )

        assert result.ai_available is True
        assert len(result.recovered_skills) == 1
        assert result.recovered_skills[0].label == "Machine Learning"
        assert result.error is None


# ── Test 3: result capped at MAX_RECOVERED_SKILLS ─────────────────────────────

class TestRecoveryCapsTo20:
    """Result is always capped at MAX_RECOVERED_SKILLS (= 20)."""

    def test_cap_enforced_by_filter(self):
        # Produce 30 valid DATA_IT items: all use "Python" variant to pass coherence
        valid_labels = [f"PythonTool{i}" for i in range(30)]
        raw = [_make_raw_item(lbl) for lbl in valid_labels]
        # Patch coherence: DATA_IT pattern matches "python"
        out = _filter_recovered(raw, cluster="DATA_IT", esco_labels_lower=set())
        assert len(out) <= MAX_RECOVERED_SKILLS == 20, (
            f"Expected ≤ {MAX_RECOVERED_SKILLS} results, got {len(out)}"
        )

    def test_cap_from_pipeline_with_mock_llm(self, monkeypatch):
        """Pipeline caps results even when LLM returns 30 items."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")

        # 30 valid items — all cluster-coherent
        mock_response = [
            {
                "label": f"Spark Module {i}",
                "kind": "tool",
                "confidence": 0.8,
                "source": "ignored_token",
                "evidence": f"spark tool {i}",
                "why_cluster_fit": "Spark is DATA_IT",
            }
            for i in range(30)
        ]

        with patch(
            "compass.analyze_skill_recovery._call_llm",
            return_value=mock_response,
        ):
            result = recover_skills_cluster_aware(
                cluster="DATA_IT",
                ignored_tokens=[f"spark{i}" for i in range(30)],
            )

        assert len(result.recovered_skills) <= MAX_RECOVERED_SKILLS, (
            f"Expected ≤ {MAX_RECOVERED_SKILLS}, got {len(result.recovered_skills)}"
        )


# ── Test 4: endpoint DEV gate ─────────────────────────────────────────────────

class TestEndpointDevOnlyGate:
    """POST /analyze/recover-skills returns 400 without ELEVIA_DEV_TOOLS=1."""

    def test_endpoint_blocked_without_dev_tools(self, monkeypatch):
        monkeypatch.delenv("ELEVIA_DEV_TOOLS", raising=False)

        from fastapi.testclient import TestClient

        # Import main app (loads .env before importing routes)
        from api.main import app
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/analyze/recover-skills",
            json={
                "cluster": "DATA_IT",
                "ignored_tokens": ["python", "sql"],
                "noise_tokens": [],
                "validated_esco_labels": [],
            },
        )

        assert response.status_code == 400, (
            f"Expected 400 when ELEVIA_DEV_TOOLS not set, got {response.status_code}"
        )
        body = response.json()
        assert "error" in body
        error = body["error"]
        assert error.get("code") == "DEV_TOOLS_DISABLED"
        assert body.get("error_code") == "DEV_TOOLS_DISABLED"

    def test_endpoint_accessible_with_dev_tools(self, monkeypatch):
        monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")
        # No OPENAI_API_KEY → ai_available=False, graceful response
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        from fastapi.testclient import TestClient
        from api.main import app
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/analyze/recover-skills",
            json={
                "cluster": "DATA_IT",
                "ignored_tokens": ["python"],
                "noise_tokens": [],
                "validated_esco_labels": [],
            },
        )

        assert response.status_code == 200, (
            f"Expected 200 with DEV_TOOLS=1, got {response.status_code}: {response.text}"
        )
        body = response.json()
        assert body["ai_available"] is False
        assert body["ai_error"] == "OPENAI_KEY_MISSING"
        assert body["error_code"] == "OPENAI_KEY_MISSING"
        assert isinstance(body["recovered_skills"], list)

    def test_invalid_request_returns_error_code(self, monkeypatch):
        """Invalid payload should return stable INVALID_REQUEST error code."""
        monkeypatch.setenv("ELEVIA_DEV_TOOLS", "1")

        from fastapi.testclient import TestClient
        from api.main import app
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post(
            "/analyze/recover-skills",
            json={"ignored_tokens": ["python"]},  # missing required 'cluster'
        )

        assert response.status_code == 400, (
            f"Expected 400 for invalid request, got {response.status_code}: {response.text}"
        )
        body = response.json()
        assert body.get("error_code") == "INVALID_REQUEST"
