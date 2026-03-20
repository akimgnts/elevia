from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))

from labs.ai_parsing_assist.gating import gate_ai_enrichment


SEGMENT = "Preparation des reportings mensuels et suivi budgetaire sous Excel"
HINTS = {
    "existing_action": "monitoring",
    "existing_object": "reportings",
    "existing_domain": "unknown",
    "detected_tools": ["Excel"],
}


def test_ai_parsing_assist_gating_accepts_evidence_backed_enrichment():
    accepted, reason, parsed = gate_ai_enrichment(
        enrichment={
            "should_enrich": True,
            "action": "reporting",
            "object": "reportings mensuels",
            "domain": "finance",
            "tools": ["Excel"],
            "semantic_label": "financial monthly reporting",
            "confidence": 0.88,
            "evidence_span": "reportings mensuels",
            "reasoning": "The segment explicitly mentions monthly reporting.",
        },
        segment_text=SEGMENT,
        deterministic_hints=HINTS,
        allowed_tool_labels=["Excel"],
    )

    assert accepted is True
    assert reason == "accepted"
    assert parsed["domain"] == "finance"


def test_ai_parsing_assist_gating_rejects_low_confidence_or_unsupported_output():
    accepted, reason, _ = gate_ai_enrichment(
        enrichment={
            "should_enrich": True,
            "action": "analysis",
            "object": "reportings mensuels",
            "domain": "finance",
            "tools": ["Excel"],
            "semantic_label": "financial reporting",
            "confidence": 0.61,
            "evidence_span": "reportings mensuels",
            "reasoning": "Weak confidence.",
        },
        segment_text=SEGMENT,
        deterministic_hints=HINTS,
        allowed_tool_labels=["Excel"],
    )
    assert accepted is False
    assert reason == "low_confidence"

    accepted, reason, _ = gate_ai_enrichment(
        enrichment={
            "should_enrich": True,
            "action": "reporting",
            "object": "reportings mensuels",
            "domain": "finance",
            "tools": ["Power BI"],
            "semantic_label": "financial reporting",
            "confidence": 0.91,
            "evidence_span": "reportings mensuels",
            "reasoning": "Invented tool.",
        },
        segment_text=SEGMENT,
        deterministic_hints=HINTS,
        allowed_tool_labels=["Excel"],
    )
    assert accepted is False
    assert reason == "unsupported_tool"
