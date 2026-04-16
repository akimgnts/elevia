"""
Static checks for Offer Detail explainability migration.
"""
from pathlib import Path


MODAL = Path("apps/web/src/components/OfferDetailModal.tsx").read_text(encoding="utf-8")
API = Path("apps/web/src/lib/api.ts").read_text(encoding="utf-8")


def test_offer_detail_uses_explanation_as_primary_contract():
    assert "const narrative = buildOfferNarrative({" in MODAL
    assert "whyParagraph(narrative.summary, titleInfo.display)" in MODAL
    assert "narrative.expectations.length > 0 ? narrative.expectations : fallbackExpectations" in MODAL
    assert "narrative.gaps.length > 0" in MODAL


def test_offer_detail_no_longer_uses_legacy_verdict_logic():
    assert "Position Elevia" not in MODAL
    assert "derivePositionElevia" not in MODAL
    assert "distanceBadgeClass" not in MODAL
    assert "verdictBadgeClass" not in MODAL
    assert "getVerdict" not in MODAL
    assert "Action principale (bientôt)" not in MODAL


def test_offer_detail_keeps_raw_score_and_compass_signal_in_debug_only():
    assert "{showDebug && explainV1Full && (" in MODAL
    assert "Détail du diagnostic" in MODAL
    assert "Mode debug" in MODAL


def test_offer_api_contract_exposes_explanation():
    assert "explanation: OfferExplanation;" in API
