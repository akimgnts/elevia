"""
Static checks for Offer Detail explainability migration.
"""
from pathlib import Path


MODAL = Path("apps/web/src/components/OfferDetailModal.tsx").read_text(encoding="utf-8")
API = Path("apps/web/src/lib/api.ts").read_text(encoding="utf-8")


def test_offer_detail_uses_explanation_as_primary_contract():
    assert "const explanation = offer.explanation;" in MODAL
    assert "explanation.summary_reason" in MODAL
    assert "explanation.fit_label" in MODAL
    assert "uniqueVisible(explanation.strengths, 5)" in MODAL
    assert "explanation.gaps.filter(" in MODAL
    assert "uniqueVisible(explanation.next_actions, 3)" in MODAL


def test_offer_detail_no_longer_uses_legacy_verdict_logic():
    assert "Position Elevia" not in MODAL
    assert "derivePositionElevia" not in MODAL
    assert "distanceBadgeClass" not in MODAL
    assert "verdictBadgeClass" not in MODAL
    assert "getVerdict" not in MODAL
    assert "Action principale (bientôt)" not in MODAL


def test_offer_detail_keeps_raw_score_and_compass_signal_in_debug_only():
    assert "{showDebug && (" in MODAL
    assert 'h3 className="text-sm font-semibold text-neutral-200">Détail du score</h3>' in MODAL
    assert 'h3 className="text-sm font-semibold text-neutral-200">Preuve du match</h3>' in MODAL


def test_offer_api_contract_exposes_explanation():
    assert "explanation: OfferExplanation;" in API
