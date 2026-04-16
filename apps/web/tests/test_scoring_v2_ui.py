"""
Static checks for scoring_v2 exposure in Inbox and Offer Detail.
"""
from pathlib import Path


CARD = Path("apps/web/src/components/inbox/InboxCardV2.tsx").read_text(encoding="utf-8")
MODAL = Path("apps/web/src/components/OfferDetailModal.tsx").read_text(encoding="utf-8")
PAGE = Path("apps/web/src/pages/InboxPage.tsx").read_text(encoding="utf-8")
API = Path("apps/web/src/lib/api.ts").read_text(encoding="utf-8")
HELPER = Path("apps/web/src/lib/inboxItems.ts").read_text(encoding="utf-8")


def test_api_contract_exposes_scoring_v2():
    assert "export interface ScoringV2" in API
    assert "scoring_v2?: ScoringV2 | null;" in API


def test_inbox_page_normalizes_scoring_v2_for_fallback_contract():
    assert 'rec.scoring_v2 && typeof rec.scoring_v2 === "object"' in HELPER


def test_inbox_card_no_longer_uses_scoring_v2_as_primary_surface():
    assert "scoringV2" not in CARD
    assert "Score métier:" not in CARD


def test_offer_detail_keeps_scoring_v2_as_secondary_reference():
    assert "const scoreV2 = scoringV2 ?? offer.scoring_v2 ?? null;" in MODAL
    assert "Référence v2" in MODAL


def test_missing_scoring_v2_does_not_crash_render_path():
    assert "scoreV3?.summary" in MODAL
