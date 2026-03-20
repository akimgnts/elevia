"""
Static checks for semantic explainability exposure in Inbox and Offer Detail.
"""
from pathlib import Path


CARD = Path("apps/web/src/components/inbox/InboxCardV2.tsx").read_text(encoding="utf-8")
MODAL = Path("apps/web/src/components/OfferDetailModal.tsx").read_text(encoding="utf-8")
PAGE = Path("apps/web/src/pages/InboxPage.tsx").read_text(encoding="utf-8")
API = Path("apps/web/src/lib/api.ts").read_text(encoding="utf-8")


def test_api_contract_exposes_semantic_explainability():
    assert "export interface SemanticExplainability" in API
    assert "semantic_explainability?: SemanticExplainability | null;" in API
    assert "export interface ProfileSemanticContext" in API



def test_inbox_page_passes_semantic_explainability_to_card():
    assert "semantic_explainability?: SemanticExplainability | null;" in PAGE
    assert "semanticExplainability={offer.semantic_explainability}" in PAGE
    assert "rec.semantic_explainability && typeof rec.semantic_explainability === \"object\"" in PAGE



def test_inbox_card_renders_semantic_alignment_as_primary_reading():
    assert "semanticExplainability?: {" in CARD
    assert 'Lecture du match' in CARD
    assert "const semanticSummary = semanticExplainability?.alignment_summary;" in CARD
    assert 'Signaux communs' in CARD
    assert 'Ecart structurel' in CARD
    assert 'Alignement fort' in CARD



def test_offer_detail_renders_semantic_match_section():
    assert "const semantic = semanticExplainability ?? offer.semantic_explainability ?? null;" in MODAL
    assert 'Lecture du match' in MODAL
    assert 'Profil:' in MODAL
    assert 'Poste:' in MODAL
    assert 'Domaine commun:' in MODAL
    assert 'Signaux manquants' in MODAL
