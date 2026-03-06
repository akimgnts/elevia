"""Tests for ESCO promotion mapping (Sprint 6 Step 2)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ── Path setup ─────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.promotion.esco_promotion import promote_esco_skills
from compass.promotion.aliases import ALIAS_TO_CANONICAL_RAW
from esco.mapper import map_skill


def test_flag_off_no_promotion():
    out = promote_esco_skills([
        "machine learning",
        "power bi",
    ], base_skills_uri=[], _promote_override=False)
    assert out == []


def test_machine_learning_promoted():
    expected = map_skill("apprentissage automatique", enable_fuzzy=False)
    assert expected is not None, "ESCO label lookup failed for apprentissage automatique"
    out = promote_esco_skills([
        "machine learning",
        "ml",
        "apprentissage automatique",
    ], base_skills_uri=[], _promote_override=True)
    assert expected["esco_id"] in out


def test_alias_canonical_labels_exist():
    canonical_labels = sorted(set(ALIAS_TO_CANONICAL_RAW.values()))
    missing = []
    for label in canonical_labels:
        if not map_skill(label, enable_fuzzy=False):
            missing.append(label)
    assert not missing, f"Missing ESCO labels for aliases: {missing}"


def test_reject_if_already_in_base():
    expected = map_skill("apprentissage automatique", enable_fuzzy=False)
    assert expected is not None, "ESCO label lookup failed for apprentissage automatique"
    out = promote_esco_skills(
        ["machine learning"],
        base_skills_uri=[expected["esco_id"]],
        _promote_override=True,
    )
    assert expected["esco_id"] not in out


def test_unknown_label_rejected():
    out = promote_esco_skills(["zz_unknown_skill_123"], base_skills_uri=[], _promote_override=True)
    assert out == []


def test_dedup_and_sort():
    out = promote_esco_skills([
        "machine learning",
        "ML",
        "machine-learning",
    ], base_skills_uri=[], _promote_override=True)
    assert len(out) == 1


def test_cap_respected(monkeypatch):
    # Patch map_skill to return unique URIs deterministically
    def _stub_map_skill(raw, enable_fuzzy=False):
        return {
            "esco_id": f"uri:{raw}",
            "label": raw,
        }

    monkeypatch.setattr("compass.promotion.esco_promotion.map_skill", _stub_map_skill)
    labels = [f"Skill {i}" for i in range(50)]
    out = promote_esco_skills(labels, base_skills_uri=[], _promote_override=True, max_promoted=20)
    assert len(out) == 20
    assert out == sorted(out)


def test_deterministic_ordering(monkeypatch):
    def _stub_map_skill(raw, enable_fuzzy=False):
        return {
            "esco_id": f"uri:{raw}",
            "label": raw,
        }

    monkeypatch.setattr("compass.promotion.esco_promotion.map_skill", _stub_map_skill)
    labels = ["B", "A", "C"]
    out1 = promote_esco_skills(labels, base_skills_uri=[], _promote_override=True, max_promoted=20)
    out2 = promote_esco_skills(labels, base_skills_uri=[], _promote_override=True, max_promoted=20)
    assert out1 == out2
    assert out1 == sorted(out1)
