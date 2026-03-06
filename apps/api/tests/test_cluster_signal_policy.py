"""Tests for deterministic cluster signal policy."""
from __future__ import annotations

import sys
from pathlib import Path

# ── Path setup ─────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.cluster_signal_policy import build_candidates_for_ai, filter_offer_domain_tokens


def test_data_it_machine_learning_kept():
    result = build_candidates_for_ai(
        cluster="DATA_IT",
        ignored_tokens=["machine learning"],
        noise_tokens=[],
        validated_esco_labels=[],
    )
    assert "machine learning" in result["candidates"]


def test_data_it_generic_dropped():
    result = build_candidates_for_ai(
        cluster="DATA_IT",
        ignored_tokens=["paris", "anglais", "business"],
        noise_tokens=[],
        validated_esco_labels=[],
    )
    assert result["candidates"] == []
    dropped_reasons = result["stats"]["dropped_by_reason"]
    assert dropped_reasons.get("generic", 0) >= 1


def test_dedupe_against_validated_esco():
    result = build_candidates_for_ai(
        cluster="DATA_IT",
        ignored_tokens=["Python"],
        noise_tokens=[],
        validated_esco_labels=["Python"],
    )
    assert result["candidates"] == []


def test_deterministic_output():
    args = dict(
        cluster="DATA_IT",
        ignored_tokens=["machine", "learning", "Power-BI"],
        noise_tokens=["paris"],
        validated_esco_labels=[],
    )
    r1 = build_candidates_for_ai(**args)
    r2 = build_candidates_for_ai(**args)
    assert r1 == r2


def test_offer_token_filter_keeps_signal():
    result = filter_offer_domain_tokens(
        cluster="DATA_IT",
        tokens=["machine learning", "paris", "bi"],
    )
    assert "machine learning" in result["kept"]
    assert "bi" in result["kept"]
    assert "paris" not in result["kept"]
