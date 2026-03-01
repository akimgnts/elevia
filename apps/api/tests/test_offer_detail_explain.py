"""
test_offer_detail_explain.py — Unit tests for offer detail explain_v1_full integration.

2 required tests:
  1. test_offer_detail_includes_explain_full  — explain_v1_full is built without crash
  2. test_score_invariance_offer_detail       — score_core == 0.0 in standalone view

Constraints:
  - No IO (in-memory data only — no DB, no file reads beyond registry)
  - No LLM
  - Deterministic
  - Score values identical to what was fed in (0.0 for standalone)
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure apps/api/src is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.signal_layer import build_explain_payload_v1, get_signal_cfg
from compass.contracts import SkillRef, ExplainPayloadV1


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_offer_skills(labels: list[str]) -> list[SkillRef]:
    """Build SkillRef list from labels (no URIs — matches offer_skills fetch)."""
    return [SkillRef(uri=None, label=s) for s in labels]


# ── Test 1 — explain_v1_full is built without crash ──────────────────────────

def test_offer_detail_includes_explain_full():
    """
    build_explain_payload_v1 called with score_core=0.0, matched_skills=[],
    offer_skills=[labels only], domain_bucket="out" must:
    - Return ExplainPayloadV1
    - Have non-empty tool_notes if offer_text mentions SAP
    - Have non-empty missing_offer_skills
    """
    offer_description = (
        "Expert SAP FI recherché pour piloter la clôture mensuelle. "
        "Vous maîtrisez le contrôle de gestion et la consolidation financière. "
        "Expérience en Salesforce appréciée."
    )
    esco_labels = ["SAP", "Finance", "Contrôle de gestion", "Reporting"]
    offer_skills = _make_offer_skills(esco_labels)

    cfg = get_signal_cfg()

    payload = build_explain_payload_v1(
        score_core=0.0,
        matched_skills=[],
        offer_skills=offer_skills,
        offer_text=offer_description,
        domain_bucket="out",
        idf_map={},
        cfg=cfg,
        offer_cluster=None,
        cluster_idf_table=None,
    )

    assert isinstance(payload, ExplainPayloadV1)

    # In standalone view, all offer skills are "missing" (no matched skills)
    assert len(payload.missing_offer_skills) == len(esco_labels), (
        f"Expected {len(esco_labels)} missing skills, got {len(payload.missing_offer_skills)}"
    )
    assert payload.matched_skills == [], (
        f"No matched skills in standalone view, got {payload.matched_skills}"
    )

    # Tool notes: SAP is in offer_text → must be detected (SPECIFIED or UNSPECIFIED)
    tool_keys = [n.tool_key for n in payload.tool_notes]
    assert "sap" in tool_keys, (
        f"SAP not detected in tool_notes: {tool_keys}"
    )

    # Salesforce also in text
    assert "salesforce" in tool_keys, (
        f"Salesforce not detected in tool_notes: {tool_keys}"
    )


# ── Test 2 — Score invariance ─────────────────────────────────────────────────

def test_score_invariance_offer_detail():
    """
    score_core must be exactly 0.0 (rounded to 4 decimal places) in standalone view.
    The signal layer must NOT modify this value.
    """
    cfg = get_signal_cfg()

    payload = build_explain_payload_v1(
        score_core=0.0,
        matched_skills=[],
        offer_skills=_make_offer_skills(["Python", "SQL", "Tableau"]),
        offer_text="Analyste Data maîtrisant Python et SQL.",
        domain_bucket="out",
        idf_map={},
        cfg=cfg,
    )

    assert payload.score_core == 0.0, (
        f"score_core must be 0.0 in standalone view, got {payload.score_core}"
    )

    # Bonus: verify cluster_level = OUT for domain_bucket="out"
    assert payload.cluster_level == "OUT", (
        f"Expected cluster_level=OUT for domain_bucket=out, got {payload.cluster_level}"
    )
