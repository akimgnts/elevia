"""Cluster-aware promotion + offer symmetry tests (Sprint 6 Step 3)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ── Path setup ─────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.promotion.esco_promotion import promote_esco_skills
from compass.promotion.apply_promotion import apply_offer_esco_promotion
from compass.promotion.cluster_policy import ALLOWED_URIS_BY_CLUSTER
from esco.mapper import map_skill


def test_cluster_gating_rejects_out_of_cluster():
    expected = map_skill("apprentissage automatique", enable_fuzzy=False)
    assert expected is not None
    out = promote_esco_skills(
        ["machine learning"],
        base_skills_uri=[],
        cluster="FINANCE",
        _promote_override=True,
    )
    assert expected["esco_id"] not in out


def test_cluster_gating_allows_data_it():
    expected = map_skill("apprentissage automatique", enable_fuzzy=False)
    assert expected is not None
    out = promote_esco_skills(
        ["machine learning"],
        base_skills_uri=[],
        cluster="DATA_IT",
        _promote_override=True,
    )
    assert expected["esco_id"] in out


def test_offer_promotion_symmetry():
    expected = map_skill("apprentissage automatique", enable_fuzzy=False)
    assert expected is not None

    offer = {
        "skills_uri": [],
        "skills_unmapped": ["machine learning"],
    }

    promoted = apply_offer_esco_promotion(
        offer,
        base_skills_uri=offer.get("skills_uri") or [],
        candidate_labels=offer.get("skills_unmapped") or [],
        cluster="DATA_IT",
        _promote_override=True,
    )

    assert expected["esco_id"] in promoted
    assert expected["esco_id"] in offer.get("skills_uri", [])


def test_offer_promotion_flag_off_no_change():
    offer = {
        "skills_uri": ["uri:base"],
        "skills_unmapped": ["machine learning"],
    }

    promoted = apply_offer_esco_promotion(
        offer,
        base_skills_uri=offer.get("skills_uri") or [],
        candidate_labels=offer.get("skills_unmapped") or [],
        cluster="DATA_IT",
        _promote_override=False,
    )

    assert promoted == []
    assert offer.get("skills_uri") == ["uri:base"]


def test_cluster_policy_not_empty_data_it():
    allowed = ALLOWED_URIS_BY_CLUSTER.get("DATA_IT") or set()
    assert len(allowed) > 0, "DATA_IT allowlist resolved to empty URIs"
