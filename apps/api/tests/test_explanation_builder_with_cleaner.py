#!/usr/bin/env python3
"""Test explanation builder with skill label cleaning."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.schemas.inbox import ExplainBlock, SkillExplainItem, ExplainBreakdown
from explain.offer_explanation_builder import build_offer_explanation


class TestExplanationWithCleaner:
    """Test that blacklisted skills are filtered out."""

    def test_blacklisted_skills_filtered_from_gaps(self):
        """Skills like 'automate', 'clients' should not appear in gaps."""
        matched_core = [
            SkillExplainItem(label="Python", weighted=True),
        ]
        # Mix of good and bad labels
        missing_core = [
            SkillExplainItem(label="automate", weighted=False),  # blacklist
            SkillExplainItem(label="Docker", weighted=False),     # good
            SkillExplainItem(label="clients", weighted=False),    # blacklist
        ]

        breakdown = ExplainBreakdown(
            skills_score=50, skills_weight=70,
            language_score=10, language_weight=15, language_match=True,
            education_score=5, education_weight=10, education_match=False,
            country_score=0, country_weight=5, country_match=False,
            total=65
        )

        explain = ExplainBlock(
            matched_display=matched_core,
            missing_display=missing_core,
            matched_full=matched_core,
            missing_full=missing_core,
            matched_core=matched_core,
            missing_core=missing_core,
            breakdown=breakdown,
        )

        result = build_offer_explanation(
            score=65,
            skill_overlap=1,
            title="Backend Engineer",
            explain_block=explain,
        )

        # Check gaps
        gaps = result.gaps
        print(f"\nGaps detected: {gaps}")

        # Should have Docker but NOT automate or clients
        has_docker = any("docker" in g.lower() for g in gaps)
        has_automate = any("automate" in g.lower() for g in gaps)
        has_clients = any("client" in g.lower() for g in gaps)

        assert has_docker, "Should have Docker in gaps"
        assert not has_automate, "Should NOT have 'automate' in gaps (blacklisted)"
        assert not has_clients, "Should NOT have 'clients' in gaps (blacklisted)"

        print("✓ Blacklisted skills filtered from gaps")

    def test_blacklisted_skills_filtered_from_next_actions(self):
        """Blacklisted skills should not appear in next_actions."""
        matched_core = [
            SkillExplainItem(label="Python", weighted=True),
        ]
        missing_core = [
            SkillExplainItem(label="automate", weighted=False),  # blacklist
            SkillExplainItem(label="Kubernetes", weighted=False),  # good
        ]

        breakdown = ExplainBreakdown(
            skills_score=50, skills_weight=70,
            language_score=10, language_weight=15, language_match=True,
            education_score=5, education_weight=10, education_match=False,
            country_score=0, country_weight=5, country_match=False,
            total=65
        )

        explain = ExplainBlock(
            matched_display=matched_core,
            missing_display=missing_core,
            matched_full=matched_core,
            missing_full=missing_core,
            matched_core=matched_core,
            missing_core=missing_core,
            breakdown=breakdown,
        )

        result = build_offer_explanation(
            score=65,
            skill_overlap=1,
            title="DevOps Engineer",
            explain_block=explain,
        )

        actions = result.next_actions
        print(f"\nNext actions: {actions}")

        # Should have Kubernetes but NOT automate
        has_k8s = any("kubernetes" in a.lower() for a in actions)
        has_automate = any("automate" in a.lower() for a in actions)

        assert has_k8s, "Should have Kubernetes in next actions"
        assert not has_automate, "Should NOT have 'automate' in next actions"

        print("✓ Blacklisted skills filtered from next_actions")

    def test_good_skills_cleaned_and_formatted(self):
        """Good skills should be cleaned and properly formatted."""
        matched_core = [
            SkillExplainItem(label="Python", weighted=True),
            SkillExplainItem(label="SQL", weighted=True),
        ]
        missing_core = [
            SkillExplainItem(label="machine_learning", weighted=False),
            SkillExplainItem(label="data_analysis", weighted=False),
        ]

        breakdown = ExplainBreakdown(
            skills_score=50, skills_weight=70,
            language_score=10, language_weight=15, language_match=True,
            education_score=5, education_weight=10, education_match=False,
            country_score=0, country_weight=5, country_match=False,
            total=65
        )

        explain = ExplainBlock(
            matched_display=matched_core,
            missing_display=missing_core,
            matched_full=matched_core,
            missing_full=missing_core,
            matched_core=matched_core,
            missing_core=missing_core,
            breakdown=breakdown,
        )

        result = build_offer_explanation(
            score=65,
            skill_overlap=2,
            title="Data Scientist",
            explain_block=explain,
        )

        gaps = result.gaps
        print(f"\nFormatted gaps: {gaps}")

        # Should have properly formatted French labels
        has_ml = any("machine learning" in g.lower() for g in gaps)
        has_analysis = any("analyse" in g.lower() for g in gaps)

        assert has_ml or has_analysis, f"Should have cleaned skill labels, got: {gaps}"

        print("✓ Good skills properly formatted")


if __name__ == "__main__":
    test = TestExplanationWithCleaner()
    test.test_blacklisted_skills_filtered_from_gaps()
    test.test_blacklisted_skills_filtered_from_next_actions()
    test.test_good_skills_cleaned_and_formatted()

    print("\n" + "="*60)
    print("ALL CLEANER INTEGRATION TESTS PASSED")
    print("="*60)
