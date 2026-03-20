from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))

from labs.ai_parsing_assist.assist import run_ai_parsing_assist


def test_lab_ai_parsing_assist_result_counters_are_consistent(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_AI_PARSING_ASSIST", "1")
    monkeypatch.setattr("labs.ai_parsing_assist.assist.get_llm_api_key", lambda: "sk-test")
    monkeypatch.setattr(
        "labs.ai_parsing_assist.assist.call_llm_json",
        lambda **kwargs: (
            {
                "should_enrich": True,
                "action": "monitoring",
                "object": "reportings mensuels",
                "domain": "finance",
                "tools": ["Excel"],
                "semantic_label": "financial monthly reporting",
                "confidence": 0.83,
                "evidence_span": "reportings mensuels",
                "reasoning": "The segment is about monthly reporting.",
            },
            0,
            0,
            0,
        ),
    )

    result = run_ai_parsing_assist(
        candidate_units=[
                {
                    "segment_index": 0,
                    "raw_text": "Preparation des reportings mensuels sous Excel.",
                    "source_section": "experience",
                    "action": "management",
                    "object": "reportings",
                    "domain": "unknown",
                    "actions": ["management"],
                    "tools": ["Excel"],
                    "object_quality_score": 0.7,
                }
            ],
            segments=[{"raw_text": "Preparation des reportings mensuels sous Excel."}],
        )

    assert result["enabled"] is True
    assert result["triggered_segment_count"] == 1
    assert result["accepted_count"] == 1
    assert result["rejected_count"] == 0
    assert result["abstention_count"] == 0
