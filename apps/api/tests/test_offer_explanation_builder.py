#!/usr/bin/env python3
"""Test offer_explanation_builder — Verify explanation narrative generation."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.schemas.inbox import ExplainBlock, SkillExplainItem, ExplainBreakdown
from explain.offer_explanation_builder import (
    build_offer_explanation,
    format_explanation_for_display,
    _score_to_label,
)


class TestOfferExplanationBuilder:
    """Test narrative generation from ExplainBlock."""

    def test_score_to_label(self):
        """Test score label conversion (French)."""
        assert _score_to_label(95) == "Excellent match"
        assert _score_to_label(70) == "Bon match"
        assert _score_to_label(50) == "Match moyen"
        assert _score_to_label(30) == "Match faible"
        assert _score_to_label(10) == "Peu pertinent"
        print("✓ test_score_to_label PASSED")

    def test_developer_profile(self):
        """Test with Developer profile (high skill overlap)."""
        # Simulate Developer profile vs Python/React offer
        matched_core = [
            SkillExplainItem(label="Python", weighted=True),
            SkillExplainItem(label="SQL", weighted=True),
            SkillExplainItem(label="JavaScript", weighted=True),
        ]
        missing_core = [
            SkillExplainItem(label="Docker", weighted=False),
            SkillExplainItem(label="Kubernetes", weighted=False),
        ]
        missing_secondary = [
            SkillExplainItem(label="Terraform", weighted=False),
        ]

        breakdown = ExplainBreakdown(
            skills_score=60.0,
            skills_weight=70,
            language_score=10.0,
            language_weight=15,
            language_match=True,
            education_score=5.0,
            education_weight=10,
            education_match=False,
            country_score=0.0,
            country_weight=5,
            country_match=False,
            total=75.0,
        )

        explain_block = ExplainBlock(
            matched_display=matched_core,
            missing_display=missing_core,
            matched_full=matched_core,
            missing_full=missing_core + missing_secondary,
            matched_core=matched_core,
            missing_core=missing_core,
            missing_secondary=missing_secondary,
            breakdown=breakdown,
        )

        explanation = build_offer_explanation(
            score=75,
            skill_overlap=3,
            title="Senior Python Developer",
            explain_block=explain_block,
            domain_affinity="aligned",
        )

        # Verify structure
        assert explanation.score == 75
        assert explanation.fit_label == "Bon match"
        assert "compétences" in explanation.summary_reason.lower()
        assert len(explanation.strengths) > 0
        assert any("docker" in g.lower() for g in explanation.gaps)
        assert len(explanation.next_actions) > 0

        print("✓ test_developer_profile PASSED")
        print(f"  Summary: {explanation.summary_reason}")
        print(f"  Strengths: {explanation.strengths}")
        print(f"  Gaps: {explanation.gaps}")
        print(f"  Next actions: {explanation.next_actions}")

    def test_data_analyst_profile(self):
        """Test with Data Analyst profile (moderate overlap)."""
        matched_core = [
            SkillExplainItem(label="Python", weighted=True),
            SkillExplainItem(label="SQL", weighted=True),
        ]
        missing_core = [
            SkillExplainItem(label="Power BI", weighted=False),
            SkillExplainItem(label="Apache Spark", weighted=False),
            SkillExplainItem(label="Statistics", weighted=False),
        ]

        breakdown = ExplainBreakdown(
            skills_score=45.0,
            skills_weight=70,
            language_score=10.0,
            language_weight=15,
            language_match=True,
            education_score=5.0,
            education_weight=10,
            education_match=False,
            country_score=0.0,
            country_weight=5,
            country_match=False,
            total=60.0,
        )

        explain_block = ExplainBlock(
            matched_display=matched_core,
            missing_display=missing_core,
            matched_full=matched_core,
            missing_full=missing_core,
            matched_core=matched_core,
            missing_core=missing_core,
            breakdown=breakdown,
        )

        explanation = build_offer_explanation(
            score=60,
            skill_overlap=2,
            title="Data Analyst",
            explain_block=explain_block,
            domain_affinity="related",
        )

        assert explanation.score == 60
        assert explanation.fit_label == "Bon match"
        assert "2 sur" in explanation.summary_reason or "2" in explanation.summary_reason
        assert len(explanation.gaps) >= 2
        assert len(explanation.next_actions) >= 2

        print("✓ test_data_analyst_profile PASSED")
        print(f"  Summary: {explanation.summary_reason}")
        print(f"  Next actions: {explanation.next_actions}")

    def test_low_overlap_profile(self):
        """Test with low skill overlap (potential match)."""
        matched_core = [
            SkillExplainItem(label="Communication", weighted=True),
        ]
        missing_core = [
            SkillExplainItem(label="Sales", weighted=False),
            SkillExplainItem(label="CRM", weighted=False),
            SkillExplainItem(label="Negotiation", weighted=False),
            SkillExplainItem(label="Account Management", weighted=False),
        ]

        breakdown = ExplainBreakdown(
            skills_score=25.0,
            skills_weight=70,
            language_score=10.0,
            language_weight=15,
            language_match=True,
            education_score=5.0,
            education_weight=10,
            education_match=False,
            country_score=0.0,
            country_weight=5,
            country_match=False,
            total=40.0,
        )

        explain_block = ExplainBlock(
            matched_display=matched_core,
            missing_display=missing_core[:2],
            matched_full=matched_core,
            missing_full=missing_core,
            matched_core=matched_core,
            missing_core=missing_core,
            breakdown=breakdown,
        )

        explanation = build_offer_explanation(
            score=40,
            skill_overlap=1,
            title="Enterprise Sales Manager",
            explain_block=explain_block,
            domain_affinity="out",
        )

        assert explanation.score == 40
        assert explanation.fit_label == "Match moyen"
        assert "manquent" in str(explanation.blockers).lower() or len(explanation.blockers) > 0
        assert len(explanation.next_actions) >= 2

        print("✓ test_low_overlap_profile PASSED")
        print(f"  Summary: {explanation.summary_reason}")
        print(f"  Blockers: {explanation.blockers}")

    def test_format_for_display(self):
        """Test JSON formatting for API response."""
        matched_core = [
            SkillExplainItem(label="Python", weighted=True),
        ]
        missing_core = [
            SkillExplainItem(label="Docker", weighted=False),
        ]

        breakdown = ExplainBreakdown(
            skills_score=50.0,
            skills_weight=70,
            language_score=10.0,
            language_weight=15,
            language_match=True,
            education_score=0.0,
            education_weight=10,
            education_match=False,
            country_score=0.0,
            country_weight=5,
            country_match=False,
            total=60.0,
        )

        explain_block = ExplainBlock(
            matched_display=matched_core,
            missing_display=missing_core,
            matched_full=matched_core,
            missing_full=missing_core,
            matched_core=matched_core,
            missing_core=missing_core,
            breakdown=breakdown,
        )

        explanation = build_offer_explanation(
            score=60,
            skill_overlap=1,
            title="Backend Engineer",
            explain_block=explain_block,
        )

        formatted = format_explanation_for_display(explanation)

        # Verify JSON structure
        assert isinstance(formatted, dict)
        assert "score" in formatted
        assert "fit_label" in formatted
        assert "summary_reason" in formatted
        assert "strengths" in formatted
        assert "gaps" in formatted
        assert "blockers" in formatted
        assert "next_actions" in formatted
        assert isinstance(formatted["strengths"], list)

        print("✓ test_format_for_display PASSED")
        print(f"  Formatted output: {formatted}")

    def test_no_explain_block(self):
        """Test fallback when no ExplainBlock provided."""
        explanation = build_offer_explanation(
            score=50,
            skill_overlap=0,
            title="Some Role",
            explain_block=None,
        )

        assert explanation.score == 50
        assert explanation.fit_label == "Match moyen"
        assert explanation.summary_reason  # Should have fallback text
        assert explanation.strengths == []
        assert explanation.gaps == []

        print("✓ test_no_explain_block PASSED")


if __name__ == "__main__":
    test = TestOfferExplanationBuilder()

    test.test_score_to_label()
    test.test_developer_profile()
    test.test_data_analyst_profile()
    test.test_low_overlap_profile()
    test.test_format_for_display()
    test.test_no_explain_block()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
