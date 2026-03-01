"""
test_compass_signal_layer.py — Unit tests for the Compass deterministic signal layer.

5 required tests:
  1. test_score_invariance_on_signal_layer       — score_core unchanged after explain
  2. test_generic_dominance_caps_confidence      — generic_ratio > cap → GENERIC_DOMINANCE reason
  3. test_tool_unspecified                       — SAP with no disambiguators → TOOL_UNSPECIFIED:sap
  4. test_tool_specified_finance                 — SAP + "fi" + "contrôle de gestion" → SPECIFIED:finance
  5. test_rare_signal_thresholds                 — IDF craft → LOW / MED / HIGH levels

Constraints:
  - No IO (uses in-memory data only)
  - No LLM
  - Deterministic
  - Score values identical before/after signal layer
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure apps/api/src is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.contracts import SkillRef, ExplainPayloadV1
from compass.signal_layer import (
    build_explain_payload_v1,
    build_explain_compact,
    compute_coverage_ratio,
    compute_rare_signal,
    compute_generic_ratio,
    compute_confidence,
    analyze_tools,
    normalize_text,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _skill(label: str, uri: str | None = None) -> SkillRef:
    return SkillRef(uri=uri, label=label)


def _make_idf(skills: list[str], base_idf: float = 1.5) -> dict[str, float]:
    """Return a simple IDF map keyed by lowercased skill."""
    return {s.lower().strip(): base_idf for s in skills}


_EMPTY_CFG: dict = {
    "generic_cap_ratio": 0.15,
    "rare_signal_thresholds": {"low": 0.30, "med": 0.55},
    "max_tool_hits": 5,
    "max_list_items_ui": 8,
}

_TOOL_REGISTRY_SAP = {
    "tools": [
        {
            "tool_key": "sap",
            "aliases": ["sap"],
            "min_context_hits": 1,
            "penalty_if_unspecified": 0.05,
            "senses": [
                {
                    "sense": "finance",
                    "disambiguators": ["fi", "fico", "contrôle de gestion", "finance"],
                },
                {
                    "sense": "supply",
                    "disambiguators": ["mm", "wm", "supply chain", "logistique"],
                },
                {
                    "sense": "data",
                    "disambiguators": ["hana", "bi", "analytics", "bw"],
                },
            ],
        }
    ]
}

_GENERIC_SET_FR = frozenset([
    "communication",
    "travail en equipe",
    "esprit d equipe",
    "gestion de projet",
    "microsoft office",
    "pack office",
    "rigueur",
    "autonomie",
    "adaptabilite",
])


# ── Test 1 — Score invariance ──────────────────────────────────────────────────

def test_score_invariance_on_signal_layer():
    """
    build_explain_payload_v1 must NOT modify score_core.
    The value fed in must equal the value stored in ExplainPayloadV1.score_core.
    """
    score_input = 0.7234
    offer_uris = {
        "http://data.europa.eu/esco/skill/a",
        "http://data.europa.eu/esco/skill/b",
    }
    matched_uris = {"http://data.europa.eu/esco/skill/a"}

    offer_skills = [_skill("Skill A", u) for u in offer_uris]
    matched_skills = [_skill("Skill A", u) for u in matched_uris]
    idf_map = _make_idf(list(offer_uris))

    payload = build_explain_payload_v1(
        score_core=score_input,
        matched_skills=matched_skills,
        offer_skills=offer_skills,
        offer_text="",
        domain_bucket="strict",
        idf_map=idf_map,
        cfg=_EMPTY_CFG,
    )

    assert payload.score_core == round(score_input, 4), (
        f"score_core must be read-only. Got {payload.score_core}, expected {round(score_input, 4)}"
    )
    # Compact version also preserves score_core
    compact = build_explain_compact(payload, len(offer_uris))
    assert compact.score_core == payload.score_core


# ── Test 2 — Generic dominance caps confidence ─────────────────────────────────

def test_generic_dominance_caps_confidence():
    """
    When generic_ratio > generic_cap_ratio (0.15), GENERIC_DOMINANCE is emitted
    and confidence cannot be HIGH.
    """
    # Craft matched skills: all generic labels
    generic_labels = ["communication", "travail en equipe", "rigueur", "autonomie"]
    matched_skills = [_skill(l) for l in generic_labels]
    offer_skills = matched_skills  # same set

    idf_map = _make_idf(generic_labels, base_idf=1.2)

    payload = build_explain_payload_v1(
        score_core=0.88,
        matched_skills=matched_skills,
        offer_skills=offer_skills,
        offer_text="",
        domain_bucket="strict",  # would be HIGH without generic dominance
        idf_map=idf_map,
        cfg=_EMPTY_CFG,
        generic_set=_GENERIC_SET_FR,
        tool_registry={"tools": []},
    )

    assert "GENERIC_DOMINANCE" in payload.incoherence_reasons, (
        f"Expected GENERIC_DOMINANCE in {payload.incoherence_reasons}"
    )
    assert payload.confidence != "HIGH", (
        f"Confidence must be capped when GENERIC_DOMINANCE present. Got {payload.confidence}"
    )


# ── Test 3 — Tool unspecified ──────────────────────────────────────────────────

def test_tool_unspecified():
    """
    Offer text contains 'SAP' with no sense disambiguators → TOOL_UNSPECIFIED:sap.
    """
    notes = analyze_tools(
        offer_text="Nous recherchons un expert SAP pour rejoindre notre équipe.",
        offer_skill_labels=["SAP", "Gestion de projet"],
        offer_cluster_level="STRICT",
        tool_registry=_TOOL_REGISTRY_SAP,
    )

    assert len(notes) == 1
    note = notes[0]
    assert note.tool_key == "sap"
    assert note.status == "UNSPECIFIED", f"Expected UNSPECIFIED, got {note.status}"
    assert note.sense is None


# ── Test 4 — Tool specified (finance sense) ────────────────────────────────────

def test_tool_specified_finance():
    """
    Offer text has 'SAP' + finance disambiguators ('fi', 'contrôle de gestion')
    → SPECIFIED with sense='finance'.
    """
    offer_text = (
        "Expert SAP FI requis. Vous maîtrisez le contrôle de gestion "
        "et la consolidation financière."
    )
    notes = analyze_tools(
        offer_text=offer_text,
        offer_skill_labels=["SAP FI", "Finance"],
        offer_cluster_level="STRICT",
        tool_registry=_TOOL_REGISTRY_SAP,
    )

    assert len(notes) == 1
    note = notes[0]
    assert note.tool_key == "sap"
    assert note.status == "SPECIFIED", f"Expected SPECIFIED, got {note.status}"
    assert note.sense == "finance", f"Expected sense=finance, got {note.sense}"
    assert len(note.hits) >= 1  # at least one disambiguator matched


# ── Test 5 — Rare signal thresholds ───────────────────────────────────────────

def test_rare_signal_thresholds():
    """
    Deterministically craft IDF maps to hit each threshold level:
      ratio < 0.30  → LOW
      ratio < 0.55  → MED
      ratio >= 0.55 → HIGH
    """
    uris_all = {
        "http://data.europa.eu/esco/skill/a",
        "http://data.europa.eu/esco/skill/b",
        "http://data.europa.eu/esco/skill/c",
        "http://data.europa.eu/esco/skill/d",
    }
    # All skills have equal IDF = 1.0 for simplicity

    # LOW: match 1 out of 4 → ratio = 0.25 < 0.30
    matched_low = {"http://data.europa.eu/esco/skill/a"}
    ratio_low, level_low = compute_rare_signal(matched_low, uris_all, {})
    assert level_low == "LOW", f"Expected LOW, got {level_low} (ratio={ratio_low})"
    assert ratio_low < 0.30

    # MED: match 2 out of 4 → ratio = 0.50, in [0.30, 0.55)
    matched_med = {
        "http://data.europa.eu/esco/skill/a",
        "http://data.europa.eu/esco/skill/b",
    }
    ratio_med, level_med = compute_rare_signal(matched_med, uris_all, {})
    assert level_med == "MED", f"Expected MED, got {level_med} (ratio={ratio_med})"
    assert 0.30 <= ratio_med < 0.55

    # HIGH: match 3 out of 4 → ratio = 0.75 >= 0.55
    matched_high = {
        "http://data.europa.eu/esco/skill/a",
        "http://data.europa.eu/esco/skill/b",
        "http://data.europa.eu/esco/skill/c",
    }
    ratio_high, level_high = compute_rare_signal(matched_high, uris_all, {})
    assert level_high == "HIGH", f"Expected HIGH, got {level_high} (ratio={ratio_high})"
    assert ratio_high >= 0.55
