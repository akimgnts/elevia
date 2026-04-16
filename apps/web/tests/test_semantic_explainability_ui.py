"""
Static checks for semantic explainability exposure in Inbox and Offer Detail.
"""
from pathlib import Path


CARD = Path("apps/web/src/components/inbox/InboxCardV2.tsx").read_text(encoding="utf-8")
MODAL = Path("apps/web/src/components/OfferDetailModal.tsx").read_text(encoding="utf-8")
PAGE = Path("apps/web/src/pages/InboxPage.tsx").read_text(encoding="utf-8")
API = Path("apps/web/src/lib/api.ts").read_text(encoding="utf-8")
HELPER = Path("apps/web/src/lib/inboxItems.ts").read_text(encoding="utf-8")


def test_api_contract_exposes_semantic_explainability():
    assert "export interface SemanticExplainability" in API
    assert "semantic_explainability?: SemanticExplainability | null;" in API
    assert "export interface ProfileSemanticContext" in API



def test_inbox_page_passes_semantic_explainability_to_card():
    assert "semantic_explainability?: SemanticExplainability | null;" in HELPER
    assert "semanticExplainability={offer.semantic_explainability}" in PAGE
    assert "rec.semantic_explainability && typeof rec.semantic_explainability === \"object\"" in HELPER



def test_inbox_card_routes_semantic_explainability_through_narrative_builder():
    assert "semanticExplainability?: SemanticExplainability | null;" in CARD
    assert "buildOfferNarrative({" in CARD
    assert "semanticExplainability," in CARD
    assert "Ce qu'il faut retenir" in CARD



def test_offer_detail_renders_semantic_match_section():
    assert "const semantic = semanticExplainability ?? offer.semantic_explainability ?? null;" in MODAL
    assert "Pourquoi ce poste te correspond" in MODAL
    assert "Points d'écart" in MODAL
    assert "Détail du diagnostic" in MODAL
