"""
Static checks for Inbox explainability finalization.
"""
from pathlib import Path


CARD = Path("apps/web/src/components/inbox/InboxCardV2.tsx").read_text(encoding="utf-8")
PAGE = Path("apps/web/src/pages/InboxPage.tsx").read_text(encoding="utf-8")
API = Path("apps/web/src/lib/api.ts").read_text(encoding="utf-8")


def test_inbox_card_depends_only_on_explanation_contract():
    assert "explanation.fit_label" in CARD
    assert "explanation.summary_reason" in CARD
    assert "selectVisibleSignals(explanation.strengths, 4)" in CARD
    assert "explanation.blockers.length > 0 ? explanation.blockers : explanation.gaps" in CARD
    assert "explanation.next_actions[0]" in CARD


def test_inbox_card_has_no_legacy_explainability_props():
    assert "fitScore" not in CARD
    assert "whyMatch" not in CARD
    assert "mainBlockers" not in CARD
    assert "nextMove" not in CARD
    assert "distance:" not in CARD
    assert "Match signal:" not in CARD


def test_inbox_page_requires_explanation_and_does_not_normalize_legacy_fields():
    assert 'console.warn("[inbox] Item missing explanation contract:"' in PAGE
    assert "explanation={offer.explanation}" in PAGE
    assert "match_strength" not in PAGE
    assert "explain_v1" not in PAGE
    assert "fit_score" not in PAGE
    assert "why_match" not in PAGE
    assert "main_blockers" not in PAGE
    assert "next_move" not in PAGE


def test_inbox_api_type_uses_explanation_as_primary_contract():
    assert "explanation: OfferExplanation;" in API
    assert "@deprecated Inbox UI no longer uses this. Safe backend cleanup candidate." in API
    assert "fit_score?: number;" not in API
    assert "why_match?: string[];" not in API
    assert "main_blockers?: string[];" not in API
    assert "next_move?: string;" not in API
