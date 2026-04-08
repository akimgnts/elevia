"""
Static checks for scoring_v3 exposure and primary usage in Inbox and Offer Detail.
"""
from pathlib import Path


MODAL = Path("apps/web/src/components/OfferDetailModal.tsx").read_text(encoding="utf-8")
PAGE = Path("apps/web/src/pages/InboxPage.tsx").read_text(encoding="utf-8")
API = Path("apps/web/src/lib/api.ts").read_text(encoding="utf-8")
HELPER = Path("apps/web/src/lib/inboxItems.ts").read_text(encoding="utf-8")


def test_api_contract_exposes_scoring_v3():
    assert "export interface ScoringV3" in API
    assert "scoring_v3?: ScoringV3 | null;" in API


def test_inbox_page_normalizes_scoring_v3_and_prefers_it_for_display():
    assert 'rec.scoring_v3 && typeof rec.scoring_v3 === "object"' in HELPER
    assert "const score = resolvePrimaryScore(rec, baseExplanation ?? buildFallbackExplanation(rec, 0));" in HELPER
    assert "primaryDisplayScore(b) - primaryDisplayScore(a)" in HELPER
    assert "? { ...offer.explanation, score: offer.scoring_v3.score_pct }" in PAGE


def test_offer_detail_modal_uses_scoring_v3_as_primary_score():
    assert "const scoreV3 = scoringV3 ?? offer.scoring_v3 ?? null;" in MODAL
    assert "const primaryScore =" in MODAL
    assert "Score principal :" in MODAL
    assert "Référence v2" in MODAL
