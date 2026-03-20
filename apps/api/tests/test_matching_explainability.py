from __future__ import annotations

import json
from pathlib import Path

import pytest

from compass.canonical.skill_proximity import reset_proximity_store
from compass.matching_explainability import build_matching_explainability


def _write_proximity(tmp_path: Path) -> Path:
    data = {
        "version": "0.1.0",
        "proximity_rules": [
            {
                "source": "skill:deep_learning",
                "target": "skill:machine_learning",
                "relation": "specialization_of",
                "strength": 0.9,
                "status": "active",
            }
        ],
    }
    path = tmp_path / "proximity.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_near_match_detected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write_proximity(tmp_path)
    monkeypatch.setenv("ELEVIA_CANONICAL_PROXIMITY_PATH", str(path))
    reset_proximity_store()
    result = build_matching_explainability(
        profile_labels=["machine learning"],
        offer_labels=["deep learning"],
    )
    assert result["near_match_count"] == 1
    assert len(result["near_matches"]) == 1
    link = result["near_matches"][0]
    assert link["relation"] == "specialization_of"
    assert link["strength"] == 0.9
    assert link["profile_label"]
    assert link["offer_label"]


def test_exact_match_excluded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write_proximity(tmp_path)
    monkeypatch.setenv("ELEVIA_CANONICAL_PROXIMITY_PATH", str(path))
    reset_proximity_store()
    result = build_matching_explainability(
        profile_labels=["machine learning"],
        offer_labels=["machine learning"],
    )
    assert result["near_match_count"] == 0
    assert result["near_matches"] == []


def test_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write_proximity(tmp_path)
    monkeypatch.setenv("ELEVIA_CANONICAL_PROXIMITY_PATH", str(path))
    reset_proximity_store()
    r1 = build_matching_explainability(
        profile_labels=["machine learning"],
        offer_labels=["deep learning"],
    )
    r2 = build_matching_explainability(
        profile_labels=["machine learning"],
        offer_labels=["deep learning"],
    )
    assert r1 == r2


def test_empty_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write_proximity(tmp_path)
    monkeypatch.setenv("ELEVIA_CANONICAL_PROXIMITY_PATH", str(path))
    reset_proximity_store()
    result = build_matching_explainability(profile_labels=[], offer_labels=[])
    assert result["near_match_count"] == 0
    assert result["near_matches"] == []


def test_invariant_scoring_core_frozen() -> None:
    src = Path("apps/api/src/matching/matching_v1.py").read_text(encoding="utf-8")
    assert "matching_explainability" not in src
