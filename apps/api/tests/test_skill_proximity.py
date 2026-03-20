from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from compass.canonical.skill_proximity import (
    compute_skill_proximity,
    reset_proximity_store,
)


def _write_rules(tmp_path: Path, rules: list[dict]) -> Path:
    path = tmp_path / "proximity.json"
    path.write_text(json.dumps({"version": "0.1.0", "proximity_rules": rules}), encoding="utf-8")
    return path


def test_proximity_missing_file_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "missing.json"
    monkeypatch.setenv("ELEVIA_CANONICAL_PROXIMITY_PATH", str(missing))
    reset_proximity_store()
    result = compute_skill_proximity(
        ["skill:deep_learning"], ["skill:machine_learning"]
    )
    assert result["links"] == []
    assert result["summary"]["match_count"] == 0


def test_proximity_simple_link(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write_rules(
        tmp_path,
        [
            {
                "source": "skill:deep_learning",
                "target": "skill:machine_learning",
                "relation": "specialization_of",
                "strength": 0.9,
                "status": "active",
            }
        ],
    )
    monkeypatch.setenv("ELEVIA_CANONICAL_PROXIMITY_PATH", str(path))
    reset_proximity_store()
    result = compute_skill_proximity(
        ["skill:deep_learning"], ["skill:machine_learning"]
    )
    assert result["summary"]["match_count"] == 1
    link = result["links"][0]
    assert link["source_id"] == "skill:deep_learning"
    assert link["target_id"] == "skill:machine_learning"
    assert link["relation"] == "specialization_of"
    assert link["strength"] == 0.9


def test_proximity_exact_match_not_counted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write_rules(
        tmp_path,
        [
            {
                "source": "skill:machine_learning",
                "target": "skill:machine_learning",
                "relation": "adjacent_to",
                "strength": 0.5,
                "status": "active",
            }
        ],
    )
    monkeypatch.setenv("ELEVIA_CANONICAL_PROXIMITY_PATH", str(path))
    reset_proximity_store()
    result = compute_skill_proximity(
        ["skill:machine_learning"], ["skill:machine_learning"]
    )
    assert result["summary"]["match_count"] == 0
    assert result["links"] == []


def test_proximity_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write_rules(
        tmp_path,
        [
            {
                "source": "skill:deep_learning",
                "target": "skill:machine_learning",
                "relation": "specialization_of",
                "strength": 0.9,
                "status": "active",
            }
        ],
    )
    monkeypatch.setenv("ELEVIA_CANONICAL_PROXIMITY_PATH", str(path))
    reset_proximity_store()
    result1 = compute_skill_proximity(
        ["skill:deep_learning"], ["skill:machine_learning"]
    )
    result2 = compute_skill_proximity(
        ["skill:deep_learning"], ["skill:machine_learning"]
    )
    assert result1["links"] == result2["links"]
    assert result1["summary"] == result2["summary"]


@pytest.fixture(scope="module")
def client():
    import os

    os.environ.setdefault("ELEVIA_DEV_TOOLS", "1")
    from api.main import app

    return __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(app)


def _post_txt(client, text: str, filename: str = "cv.txt"):
    return client.post(
        "/profile/parse-file",
        files={"file": (filename, io.BytesIO(text.encode("utf-8")), "text/plain")},
    )


def test_profile_proximity_fields_present(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ELEVIA_CANONICAL_PROXIMITY_PATH", raising=False)
    reset_proximity_store()
    resp = _post_txt(
        client,
        "Machine learning and deep learning experience with Python and SQL.",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "skill_proximity_links" in body
    assert "skill_proximity_count" in body
    assert "skill_proximity_summary" in body
    assert isinstance(body["skill_proximity_links"], list)
    assert isinstance(body["skill_proximity_count"], int)
    assert isinstance(body["skill_proximity_summary"], dict)
    assert body["skill_proximity_count"] == body["skill_proximity_summary"].get(
        "match_count", body["skill_proximity_count"]
    )
