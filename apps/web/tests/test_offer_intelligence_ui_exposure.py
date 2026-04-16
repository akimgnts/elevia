"""
Static checks for offer intelligence exposure in Inbox and Offer Detail.
"""
from pathlib import Path


CARD = Path("apps/web/src/components/inbox/InboxCardV2.tsx").read_text(encoding="utf-8")
PAGE = Path("apps/web/src/pages/InboxPage.tsx").read_text(encoding="utf-8")
MODAL = Path("apps/web/src/components/OfferDetailModal.tsx").read_text(encoding="utf-8")
API = Path("apps/web/src/lib/api.ts").read_text(encoding="utf-8")
HELPER = Path("apps/web/src/lib/inboxItems.ts").read_text(encoding="utf-8")


def test_inbox_page_passes_offer_intelligence_to_card():
    assert "offer_intelligence?: OfferIntelligence | null;" in HELPER
    assert "offerIntelligence={offer.offer_intelligence}" in PAGE
    assert "rec.offer_intelligence && typeof rec.offer_intelligence === \"object\"" in HELPER



def test_inbox_card_uses_offer_intelligence_via_narrative_builder():
    assert "offerIntelligence?: OfferIntelligence | null;" in CARD
    assert "buildOfferNarrative({" in CARD
    assert "offerIntelligence," in CARD



def test_offer_detail_renders_offer_intelligence_sections():
    assert "const intelligence = offerIntelligence ?? offer.offer_intelligence ?? null;" in MODAL
    assert 'Ce que le poste attend vraiment' in MODAL
    assert "intelligence?.top_offer_signals" in MODAL
    assert "intelligence?.required_skills" in MODAL



def test_offer_api_contract_exposes_offer_intelligence():
    assert "offer_intelligence?: OfferIntelligence | null;" in API
