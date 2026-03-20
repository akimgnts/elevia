"""
Static checks for offer intelligence exposure in Inbox and Offer Detail.
"""
from pathlib import Path


CARD = Path("apps/web/src/components/inbox/InboxCardV2.tsx").read_text(encoding="utf-8")
PAGE = Path("apps/web/src/pages/InboxPage.tsx").read_text(encoding="utf-8")
MODAL = Path("apps/web/src/components/OfferDetailModal.tsx").read_text(encoding="utf-8")
API = Path("apps/web/src/lib/api.ts").read_text(encoding="utf-8")


def test_inbox_page_passes_offer_intelligence_to_card():
    assert "offer_intelligence?: OfferIntelligence | null;" in PAGE
    assert "offerIntelligence={offer.offer_intelligence}" in PAGE
    assert "rec.offer_intelligence && typeof rec.offer_intelligence === \"object\"" in PAGE



def test_inbox_card_renders_offer_intelligence_as_role_and_offer_signal():
    assert "offerIntelligence?: {" in CARD
    assert "const roleSignal = offerIntelligence?.dominant_role_block" in CARD
    assert 'Ce que le poste est' in CARD
    assert "const visibleOfferSignals = selectVisibleSignals(" in CARD
    assert "const offerSummary = offerIntelligence?.offer_summary;" in CARD



def test_offer_detail_renders_offer_intelligence_sections():
    assert "const intelligence = offerIntelligence ?? offer.offer_intelligence ?? null;" in MODAL
    assert 'Ce que le poste demande vraiment' in MODAL
    assert 'Compétences requises' in MODAL
    assert 'Compétences bonus' in MODAL
    assert "intelligence?.offer_summary" in MODAL



def test_offer_api_contract_exposes_offer_intelligence():
    assert "offer_intelligence?: OfferIntelligence | null;" in API
