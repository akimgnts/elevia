from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from semantic_retrieval.llm_interpreter import interpret_phrase
from semantic_retrieval.schemas import RetrievedCandidate


def test_interpreter_filters_unknown_references(monkeypatch):
    monkeypatch.setattr("semantic_retrieval.llm_interpreter.is_llm_available", lambda: True)

    def _fake_call(_system: str, _user: str):
        return (
            {
                "source_phrase": "coordination avec les prestataires",
                "proposed_skills": [
                    {
                        "reference": "unknown:ref",
                        "confidence": 0.99,
                        "evidence_span": "coordination avec les prestataires",
                        "rationale": "should be ignored",
                    },
                    {
                        "reference": "canonical:canonical_skill:skill:logistics_coordination",
                        "confidence": 0.84,
                        "evidence_span": "coordination avec les prestataires",
                        "rationale": "clear logistics coordination signal",
                    },
                ],
                "proposed_occupations": [],
                "abstain": False,
                "abstain_reason": "",
            },
            10,
            20,
            30,
        )

    monkeypatch.setattr("semantic_retrieval.llm_interpreter.call_llm_json", _fake_call)
    candidates = [
        RetrievedCandidate(
            reference="canonical:canonical_skill:skill:logistics_coordination",
            source_system="canonical",
            source_type="canonical_skill",
            source_id="skill:logistics_coordination",
            label="Logistics Coordination",
            aliases=[],
            short_description="",
            cluster="",
            metadata={},
            score=3.2,
            searchable_text="logistics coordination",
        )
    ]

    result = interpret_phrase(source_phrase="coordination avec les prestataires", retrieved_candidates=candidates)

    assert len(result.proposed_skills) == 1
    assert result.proposed_skills[0].reference == candidates[0].reference
