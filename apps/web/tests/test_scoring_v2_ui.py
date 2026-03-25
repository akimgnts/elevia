"""
Static checks for scoring_v2 exposure in Inbox and Offer Detail.
"""
from pathlib import Path


CARD = Path("apps/web/src/components/inbox/InboxCardV2.tsx").read_text(encoding="utf-8")
MODAL = Path("apps/web/src/components/OfferDetailModal.tsx").read_text(encoding="utf-8")
PAGE = Path("apps/web/src/pages/InboxPage.tsx").read_text(encoding="utf-8")
API = Path("apps/web/src/lib/api.ts").read_text(encoding="utf-8")


def test_api_contract_exposes_scoring_v2():
    assert "export interface ScoringV2" in API
    assert "scoring_v2?: ScoringV2 | null;" in API


def test_inbox_page_normalizes_and_passes_scoring_v2():
    assert "type ScoringV2," in PAGE
    assert 'rec.scoring_v2 && typeof rec.scoring_v2 === "object"' in PAGE
    assert "scoringV2={offer.scoring_v2}" in PAGE


def test_inbox_card_renders_score_metier_line():
    assert "scoringV2?: {" in CARD
    assert 'Score métier:' in CARD
    assert "Alignement métier fort" in CARD


def test_offer_detail_renders_scoring_v2_block():
    assert "const scoreV2 = scoringV2 ?? offer.scoring_v2 ?? null;" in MODAL
    assert 'Lecture du score' in MODAL
    assert 'Score métier:' in MODAL
    assert 'Métier:' in MODAL
    assert 'Domaines:' in MODAL
    assert 'Matching:' in MODAL
    assert 'Gaps:' in MODAL
    assert "function toLevel(value: number)" in MODAL
    assert "function gapLabel(value: number)" in MODAL


def test_missing_scoring_v2_does_not_crash_render_path():
    assert "scoreV2 && scoreV2Pct !== null" in MODAL
