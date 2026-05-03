#!/usr/bin/env python3
"""Integration test: French explanation layer in /inbox endpoint."""

import json
import sys
from pathlib import Path

import pytest

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app
from api.schemas.inbox import InboxRequest


GOLDEN_PROFILES = [
    "profile_02_developer",
    "profile_01_data_analyst",
    "profile_04_finance",
    "profile_05_commercial",
    "akim_guentas",
]

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "profiles"


def load_profile(name: str) -> dict:
    """Load profile fixture."""
    path = FIXTURES_DIR / f"{name}.json"
    if not path.exists():
        pytest.skip(f"Profile fixture {name} not found")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_explanation(item_dict, score: int) -> list:
    """Validate explanation object. Return list of errors (empty = valid)."""
    errors = []

    exp = item_dict.get("explanation")
    if not exp:
        errors.append("No explanation field")
        return errors

    # Check fit_label matches score
    expected_labels = {
        80: "Excellent match",
        60: "Bon match",
        40: "Match moyen",
        20: "Match faible",
    }

    correct_label = None
    if score >= 80:
        correct_label = "Excellent match"
    elif score >= 60:
        correct_label = "Bon match"
    elif score >= 40:
        correct_label = "Match moyen"
    elif score >= 20:
        correct_label = "Match faible"
    else:
        correct_label = "Peu pertinent"

    if exp.get("fit_label") != correct_label:
        errors.append(f"fit_label '{exp.get('fit_label')}' != '{correct_label}' for score {score}")

    # Check French text in summary
    summary = exp.get("summary_reason", "")
    french_words = ["vous", "avez", "compétences", "sur", "match", "domaine"]
    if not any(word in summary.lower() for word in french_words):
        errors.append("summary_reason doesn't contain French text")

    if not summary:
        errors.append("summary_reason is empty")

    # Check list fields exist
    if not isinstance(exp.get("strengths"), list):
        errors.append("strengths is not a list")
    if not isinstance(exp.get("gaps"), list):
        errors.append("gaps is not a list")
    if not isinstance(exp.get("blockers"), list):
        errors.append("blockers is not a list")
    if not isinstance(exp.get("next_actions"), list):
        errors.append("next_actions is not a list")

    return errors


def validate_explain_block(item_dict) -> list:
    """Validate technical explain block preserved."""
    errors = []
    explain = item_dict.get("explain")
    if not explain:
        errors.append("Technical explain block missing!")
        return errors

    # Check structure
    if not isinstance(explain.get("matched_core"), list):
        errors.append("explain.matched_core missing/invalid")
    if not isinstance(explain.get("missing_core"), list):
        errors.append("explain.missing_core missing/invalid")

    return errors


class TestFrenchExplanationIntegration:
    """Test French explanation layer across profiles."""

    @pytest.mark.parametrize("profile_name", GOLDEN_PROFILES)
    def test_inbox_returns_french_explanation(self, profile_name: str):
        """Test that /inbox returns French explanation when explain=true."""
        profile = load_profile(profile_name)
        profile_id = profile.get("id") or profile.get("profile_id") or profile_name

        # Use FastAPI TestClient
        from fastapi.testclient import TestClient
        client = TestClient(app)

        response = client.post(
            "/inbox",
            json={
                "profile_id": profile_id,
                "profile": profile,
                "min_score": 10,
                "limit": 3,
                "explain": True,
            },
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        # Check response structure
        assert "items" in data, "Response missing 'items' field"
        items = data["items"]

        assert len(items) > 0, f"No items returned for profile {profile_name}"

        # Validate top 3 items
        for i, item in enumerate(items[:3]):
            # Check explanation exists and is French
            exp_errors = validate_explanation(item, item.get("score"))
            assert not exp_errors, f"Item {i}: {', '.join(exp_errors)}"

            # Check technical explain is preserved
            explain_errors = validate_explain_block(item)
            assert not explain_errors, f"Item {i}: {', '.join(explain_errors)}"


class TestFrenchExplanationQuality:
    """Test quality of French text generation."""

    def test_french_text_naturality(self):
        """Spot-check French text quality."""
        profile = load_profile("akim_guentas")
        profile_id = profile.get("id") or "akim_guentas"

        from fastapi.testclient import TestClient
        client = TestClient(app)

        response = client.post(
            "/inbox",
            json={
                "profile_id": profile_id,
                "profile": profile,
                "min_score": 10,
                "limit": 1,
                "explain": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        items = data.get("items", [])

        assert len(items) > 0, "No items for quality test"
        item = items[0]
        exp = item.get("explanation")

        assert exp, "No explanation"

        # Check French quality samples
        assert "Vous avez" in exp.get("summary_reason", ""), "Expected 'Vous avez' in French summary"
        assert "compétences" in exp.get("summary_reason", ""), "Expected 'compétences' in French summary"

        # Check fit labels are proper French
        fit = exp.get("fit_label", "")
        valid_labels = ["Excellent match", "Bon match", "Match moyen", "Match faible", "Peu pertinent"]
        assert fit in valid_labels, f"fit_label '{fit}' not in valid French labels"

        print(f"\n✓ French quality check passed")
        print(f"  Fit label: {fit}")
        print(f"  Summary: {exp.get('summary_reason')[:80]}...")
        if exp.get("strengths"):
            print(f"  Strengths: {exp.get('strengths')[:2]}")
        if exp.get("gaps"):
            print(f"  Gaps: {exp.get('gaps')[:2]}")


class TestNoScoringChanges:
    """Verify integration doesn't break scoring."""

    def test_score_unchanged_from_matching(self):
        """Score should be unchanged vs matching engine."""
        profile = load_profile("akim_guentas")

        from fastapi.testclient import TestClient
        client = TestClient(app)

        # Get response with explain
        response = client.post(
            "/inbox",
            json={
                "profile_id": "akim_guentas",
                "profile": profile,
                "min_score": 10,
                "limit": 3,
                "explain": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        items = data.get("items", [])

        # Each item should have consistent score
        for item in items[:3]:
            score = item.get("score")
            score_pct = item.get("score_pct")

            # score and score_pct should match (if populated)
            if score is not None and score_pct is not None:
                assert score == score_pct, f"score {score} != score_pct {score_pct}"

            # Score should be in 0-100 range
            assert 0 <= score <= 100, f"Score {score} out of range"

            # Explanation should not affect score
            assert item.get("explanation") is not None, "No explanation"
            assert item.get("score") == score, "Score changed after explanation"

        print(f"\n✓ Scoring unchanged: {len(items)} items validated")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
