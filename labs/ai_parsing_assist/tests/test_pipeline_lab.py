from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))

from labs.ai_parsing_assist.assist import run_ai_parsing_assist


CANDIDATE_UNITS = [
    {
        "segment_index": 0,
        "raw_text": "Coordination avec les parties prenantes internes et preparation des reportings mensuels.",
        "source_section": "experience",
        "action": "coordination",
        "object": "parties prenantes internes",
        "domain": "unknown",
        "actions": ["coordination", "reporting"],
        "tools": ["Excel"],
        "object_quality_score": 0.7,
    },
    {
        "segment_index": 1,
        "raw_text": "Suivi budgetaire sous Excel.",
        "source_section": "experience",
        "action": "monitoring",
        "object": "suivi budgetaire",
        "domain": "finance",
        "actions": ["monitoring"],
        "tools": ["Excel"],
        "object_quality_score": 0.82,
    },
]

SEGMENTS = [{"raw_text": item["raw_text"]} for item in CANDIDATE_UNITS]


def test_lab_ai_parsing_assist_flag_off_keeps_experiment_disabled(monkeypatch):
    monkeypatch.delenv("ELEVIA_ENABLE_AI_PARSING_ASSIST", raising=False)
    result = run_ai_parsing_assist(candidate_units=CANDIDATE_UNITS, segments=SEGMENTS)
    assert result["enabled"] is False
    assert result["triggered_segment_count"] == 0


def test_lab_ai_parsing_assist_runs_in_isolated_mode(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_AI_PARSING_ASSIST", "1")
    monkeypatch.setattr("labs.ai_parsing_assist.assist.get_llm_api_key", lambda: "sk-test")

    def _fake_call(*, system_prompt: str, user_prompt: str):
        return (
            {
                "should_enrich": True,
                "action": "reporting",
                "object": "reportings mensuels",
                "domain": "finance",
                "tools": ["Excel"],
                "semantic_label": "financial monthly reporting",
                "confidence": 0.86,
                "evidence_span": "reportings mensuels",
                "reasoning": "The segment clearly mentions monthly reporting.",
            },
            0,
            0,
            0,
        )

    monkeypatch.setattr("labs.ai_parsing_assist.assist.call_llm_json", _fake_call)

    result = run_ai_parsing_assist(candidate_units=CANDIDATE_UNITS, segments=SEGMENTS)
    assert result["enabled"] is True
    assert result["triggered_segment_count"] >= 1
    assert result["accepted_count"] >= 1
    assert result["accepted_enrichments"]
