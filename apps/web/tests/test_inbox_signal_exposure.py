"""
Static checks for Inbox signal exposure.
"""
from pathlib import Path


CARD = Path("apps/web/src/components/inbox/InboxCardV2.tsx").read_text(encoding="utf-8")
PAGE = Path("apps/web/src/pages/InboxPage.tsx").read_text(encoding="utf-8")


def test_inbox_uses_score_first_sorting_contract():
    assert 'const sortMode = "score_desc" as const;' in PAGE
    assert "function sortInboxItemsForDisplay(items: NormalizedInboxItem[]): NormalizedInboxItem[]" in PAGE
    assert "explanationScore(b) - explanationScore(a)" in PAGE
    assert "blockersCount(a) - blockersCount(b)" in PAGE
    assert "strengthsCount(b) - strengthsCount(a)" in PAGE
    assert "recencyValue(b.publication_date) - recencyValue(a.publication_date)" in PAGE
    assert "sortInboxItemsForDisplay(normalizeInboxItems(data.items))" in PAGE
    assert "const displayedItems = useMemo(() => sortInboxItemsForDisplay(availableItems), [availableItems]);" in PAGE


def test_inbox_prefers_backend_explanation_score_for_display():
    assert "typeof explanation.score === \"number\"" in PAGE
    assert "? explanation.score" in PAGE


def test_inbox_card_exposes_role_signal_and_filters_generic_noise():
    assert "const roleSignal = offerIntelligence?.dominant_role_block" in CARD
    assert "selectVisibleSignals(explanation.strengths, 4)" in CARD
    assert '"communication"' in CARD
    assert '"gestion de projet"' in CARD
    assert 'const missingLabel = explanation.blockers.length > 0 ? "Blocages" : "À combler";' in CARD
    assert "Prochaine action:" in CARD


def test_inbox_card_still_has_no_legacy_explainability_usage():
    assert "whyMatch" not in CARD
    assert "mainBlockers" not in CARD
    assert "nextMove" not in CARD
    assert "distance:" not in CARD
