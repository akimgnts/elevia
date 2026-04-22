"""
Static checks for the OfferDetail career intelligence surface.
"""
from pathlib import Path


MODAL = Path("apps/web/src/components/OfferDetailModal.tsx").read_text(encoding="utf-8")
INBOX_ITEMS = Path("apps/web/src/lib/inboxItems.ts").read_text(encoding="utf-8")


def test_offer_detail_has_four_product_layers():
    assert "Comprendre l'offre" in MODAL
    assert "Comprendre ton fit" in MODAL
    assert "Que faire concretement" in MODAL
    assert "CareerFitSection" in MODAL


def test_offer_detail_uses_career_intelligence_as_fit_source():
    assert "career_intelligence?: CareerIntelligence | null" in MODAL
    assert "offer.career_intelligence" in MODAL
    assert "generic_ignored" not in MODAL


def test_inbox_normalizer_preserves_career_intelligence():
    assert "CareerIntelligence" in INBOX_ITEMS
    assert "career_intelligence:" in INBOX_ITEMS


def test_offer_detail_keeps_score_overlays_out_of_standard_surface():
    assert "Overlay analytique v3" not in MODAL
    assert "Overlay analytique v2" not in MODAL
