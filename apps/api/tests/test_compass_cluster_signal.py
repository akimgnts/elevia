"""
test_compass_cluster_signal.py — Unit tests for the Compass cluster-level IDF signal.

5 tests:
  1. test_cluster_idf_is_deterministic
  2. test_sector_signal_thresholds
  3. test_sector_signal_does_not_change_score
  4. test_low_sector_signal_caps_confidence_only_in_margin
  5. test_rerank_uses_sector_signal_without_score_change

Constraints:
  - No IO (in-memory data only)
  - No LLM / ML
  - Deterministic
  - score_core invariance preserved
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.cluster_signal import (
    compute_cluster_skill_stats,
    compute_cluster_idf,
    compute_sector_signal,
)
from compass.contracts import SkillRef
from compass.signal_layer import (
    build_explain_payload_v1,
    compute_confidence,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _skill(label: str, uri: str | None = None) -> SkillRef:
    return SkillRef(uri=uri, label=label)


_EMPTY_CFG: dict = {
    "generic_cap_ratio": 0.15,
    "rare_signal_thresholds": {"low": 0.30, "med": 0.55},
    "max_tool_hits": 5,
    "max_list_items_ui": 8,
    "sector_signal_enabled": True,
}

# Minimal cluster IDF table with equal weights for threshold tests
_UNIFORM_CLUSTER_IDF = {
    "DATA_IT": {
        "http://data.europa.eu/esco/skill/a": 1.0,
        "http://data.europa.eu/esco/skill/b": 1.0,
        "http://data.europa.eu/esco/skill/c": 1.0,
        "http://data.europa.eu/esco/skill/d": 1.0,
    }
}

_ALL_URIS = [
    "http://data.europa.eu/esco/skill/a",
    "http://data.europa.eu/esco/skill/b",
    "http://data.europa.eu/esco/skill/c",
    "http://data.europa.eu/esco/skill/d",
]


# ── Test 1 — Determinism ───────────────────────────────────────────────────────

def test_cluster_idf_is_deterministic():
    """
    Same catalog + cluster assignments → identical cluster IDF tables (twice).
    """
    offers = [
        {"id": "o1", "skills_uri": [
            "http://data.europa.eu/esco/skill/a",
            "http://data.europa.eu/esco/skill/b",
        ]},
        {"id": "o2", "skills_uri": [
            "http://data.europa.eu/esco/skill/b",
            "http://data.europa.eu/esco/skill/c",
        ]},
        {"id": "o3", "skills_uri": [
            "http://data.europa.eu/esco/skill/c",
        ]},
    ]
    clusters = {"o1": "DATA_IT", "o2": "DATA_IT", "o3": "FINANCE_LEGAL"}

    stats_1 = compute_cluster_skill_stats(offers, clusters)
    idf_1 = compute_cluster_idf(stats_1)

    stats_2 = compute_cluster_skill_stats(offers, clusters)
    idf_2 = compute_cluster_idf(stats_2)

    assert idf_1 == idf_2, "cluster IDF must be deterministic"

    # Sanity: DATA_IT should have entries, FINANCE_LEGAL should have entries
    assert "DATA_IT" in idf_1
    assert "FINANCE_LEGAL" in idf_1

    # Skill b appears in 2/2 DATA_IT offers → lower IDF than skill a (1/2)
    idf_data = idf_1["DATA_IT"]
    uri_a = "http://data.europa.eu/esco/skill/a"
    uri_b = "http://data.europa.eu/esco/skill/b"
    assert idf_data[uri_a] > idf_data[uri_b], (
        f"Skill a (df=1) should be rarer than skill b (df=2) in DATA_IT: "
        f"idf(a)={idf_data[uri_a]:.4f}, idf(b)={idf_data[uri_b]:.4f}"
    )


# ── Test 2 — Sector signal thresholds ─────────────────────────────────────────

def test_sector_signal_thresholds():
    """
    Craft matched sets against uniform cluster IDF to deterministically hit
    LOW (< 0.30), MED ([0.30, 0.55)), and HIGH (>= 0.55) levels.
    """
    # LOW: 1 matched out of 4 → ratio = 0.25 < 0.30
    result_low = compute_sector_signal(
        matched_skill_keys=[_ALL_URIS[0]],
        offer_skill_keys=_ALL_URIS,
        offer_cluster="DATA_IT",
        cluster_idf_table=_UNIFORM_CLUSTER_IDF,
    )
    assert result_low["sector_signal_level"] == "LOW", (
        f"Expected LOW, got {result_low['sector_signal_level']} (ratio={result_low['sector_signal']})"
    )
    assert result_low["sector_signal"] < 0.30

    # MED: 2 matched out of 4 → ratio = 0.50, in [0.30, 0.55)
    result_med = compute_sector_signal(
        matched_skill_keys=_ALL_URIS[:2],
        offer_skill_keys=_ALL_URIS,
        offer_cluster="DATA_IT",
        cluster_idf_table=_UNIFORM_CLUSTER_IDF,
    )
    assert result_med["sector_signal_level"] == "MED", (
        f"Expected MED, got {result_med['sector_signal_level']} (ratio={result_med['sector_signal']})"
    )
    assert 0.30 <= result_med["sector_signal"] < 0.55

    # HIGH: 3 matched out of 4 → ratio = 0.75 >= 0.55
    result_high = compute_sector_signal(
        matched_skill_keys=_ALL_URIS[:3],
        offer_skill_keys=_ALL_URIS,
        offer_cluster="DATA_IT",
        cluster_idf_table=_UNIFORM_CLUSTER_IDF,
    )
    assert result_high["sector_signal_level"] == "HIGH", (
        f"Expected HIGH, got {result_high['sector_signal_level']} (ratio={result_high['sector_signal']})"
    )
    assert result_high["sector_signal"] >= 0.55


# ── Test 3 — Score invariance ──────────────────────────────────────────────────

def test_sector_signal_does_not_change_score():
    """
    build_explain_payload_v1 with sector signal enabled must NOT modify score_core.
    """
    score_input = 0.8532
    offer_uris = [
        "http://data.europa.eu/esco/skill/a",
        "http://data.europa.eu/esco/skill/b",
    ]
    matched_uris = ["http://data.europa.eu/esco/skill/a"]

    idf_map = {u: 1.5 for u in offer_uris}
    cluster_idf = {
        "DATA_IT": {u: 1.0 for u in offer_uris},
    }

    payload = build_explain_payload_v1(
        score_core=score_input,
        matched_skills=[_skill("A", matched_uris[0])],
        offer_skills=[_skill("A", offer_uris[0]), _skill("B", offer_uris[1])],
        offer_text="",
        domain_bucket="strict",
        idf_map=idf_map,
        cfg=_EMPTY_CFG,
        offer_cluster="DATA_IT",
        cluster_idf_table=cluster_idf,
    )

    assert payload.score_core == round(score_input, 4), (
        f"score_core must be read-only. Got {payload.score_core}, expected {round(score_input, 4)}"
    )
    # Sector signal should be computed and present
    assert payload.sector_signal is not None
    assert payload.sector_signal_level is not None


# ── Test 4 — Sector nudge caps confidence in the margin only ───────────────────

def test_low_sector_signal_caps_confidence_only_in_margin():
    """
    Scenario:
      - score_core >= 0.90 (very high)
      - rare_signal_level = HIGH
      - cluster_level = STRICT
      - no other incoherence reasons
      - sector_signal_level = LOW
    → baseline confidence = HIGH
    → sector nudge applies: confidence = MED + LOW_SECTOR_SIGNAL reason
    """
    confidence, reasons = compute_confidence(
        score_core=0.92,          # >= 0.90 threshold
        rare_signal_level="HIGH",
        cluster_level="STRICT",
        generic_ratio=0.05,       # below generic_cap=0.15
        tool_notes=[],
        cfg=_EMPTY_CFG,
        sector_signal_level="LOW",
    )

    assert confidence == "MED", (
        f"Expected MED after sector nudge, got {confidence}"
    )
    assert "LOW_SECTOR_SIGNAL" in reasons, (
        f"Expected LOW_SECTOR_SIGNAL in reasons, got {reasons}"
    )

    # Verify nudge does NOT apply when score_core < 0.90
    conf_no_nudge, reasons_no_nudge = compute_confidence(
        score_core=0.85,          # < 0.90, nudge should NOT apply
        rare_signal_level="HIGH",
        cluster_level="STRICT",
        generic_ratio=0.05,
        tool_notes=[],
        cfg=_EMPTY_CFG,
        sector_signal_level="LOW",
    )
    assert conf_no_nudge == "HIGH", (
        f"Nudge must NOT apply for score_core < 0.90, got {conf_no_nudge}"
    )
    assert "LOW_SECTOR_SIGNAL" not in reasons_no_nudge

    # Verify nudge does NOT apply when confidence is already LOW
    conf_already_low, reasons_low = compute_confidence(
        score_core=0.95,
        rare_signal_level="LOW",  # forces LOW
        cluster_level="STRICT",
        generic_ratio=0.05,
        tool_notes=[],
        cfg=_EMPTY_CFG,
        sector_signal_level="LOW",
    )
    assert conf_already_low == "LOW"
    assert "LOW_SECTOR_SIGNAL" not in reasons_low


# ── Test 5 — Rerank uses sector signal without changing scores ─────────────────

def test_rerank_uses_sector_signal_without_score_change():
    """
    Two offers with the same score_core but different sector fit:
      - Offer A: rare skill matched → HIGH sector signal
      - Offer B: common skill matched → LOW sector signal

    After sorting by sector_signal DESC, A comes before B.
    score_core is identical in both payloads (invariance).
    """
    score = 0.75
    cfg_with_sector = {**_EMPTY_CFG, "sector_signal_enabled": True}

    # Cluster IDF: rare_skill is highly discriminant (high weight), common_skill is ubiquitous (low weight)
    # Both offers share the same 2-skill set so coverage is identical (1/2 matched).
    # What differs is WHICH skill was matched — rare vs common.
    cluster_idf = {
        "DATA_IT": {
            "http://data.europa.eu/esco/skill/rare": 3.0,   # very discriminant → high weight
            "http://data.europa.eu/esco/skill/common": 0.1, # ubiquitous → low weight
        }
    }
    offer_skills_both = [
        _skill("Rare Skill", "http://data.europa.eu/esco/skill/rare"),
        _skill("Common Skill", "http://data.europa.eu/esco/skill/common"),
    ]

    # Offer A: matched the rare skill only
    # sector_signal = idf(rare) / (idf(rare) + idf(common)) = 3.0 / 3.1 ≈ 0.97 → HIGH
    payload_a = build_explain_payload_v1(
        score_core=score,
        matched_skills=[_skill("Rare Skill", "http://data.europa.eu/esco/skill/rare")],
        offer_skills=offer_skills_both,
        offer_text="",
        domain_bucket="strict",
        idf_map={},
        cfg=cfg_with_sector,
        offer_cluster="DATA_IT",
        cluster_idf_table=cluster_idf,
    )

    # Offer B: matched the common skill only
    # sector_signal = idf(common) / (idf(rare) + idf(common)) = 0.1 / 3.1 ≈ 0.03 → LOW
    payload_b = build_explain_payload_v1(
        score_core=score,
        matched_skills=[_skill("Common Skill", "http://data.europa.eu/esco/skill/common")],
        offer_skills=offer_skills_both,
        offer_text="",
        domain_bucket="strict",
        idf_map={},
        cfg=cfg_with_sector,
        offer_cluster="DATA_IT",
        cluster_idf_table=cluster_idf,
    )

    # Both scores must remain unchanged
    assert payload_a.score_core == round(score, 4), "score_core must be unchanged for A"
    assert payload_b.score_core == round(score, 4), "score_core must be unchanged for B"

    # Sector signals must differ and be present
    assert payload_a.sector_signal is not None
    assert payload_b.sector_signal is not None
    assert payload_a.sector_signal > payload_b.sector_signal, (
        f"Rare skill A (sector={payload_a.sector_signal}) should outrank "
        f"common skill B (sector={payload_b.sector_signal})"
    )

    # Simulate rerank: sort by (-sector_signal) — A should come first
    payloads = [payload_b, payload_a]  # B first initially
    reranked = sorted(payloads, key=lambda p: -(p.sector_signal or 0.0))
    assert reranked[0] is payload_a, "A (higher sector signal) should be first after rerank"
    assert reranked[1] is payload_b

    # Scores still unchanged after sort
    for p in reranked:
        assert p.score_core == round(score, 4)
