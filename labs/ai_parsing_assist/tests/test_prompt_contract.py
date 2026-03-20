from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))

from labs.ai_parsing_assist.assist import _build_prompt_input, _build_prompts


def test_ai_parsing_assist_prompt_input_is_bounded_and_structured():
    candidate = {
        "raw_text": "Coordination avec les parties prenantes internes et preparation des reportings mensuels.",
        "action": "coordination",
        "object": "parties prenantes internes",
        "domain": "unknown",
        "tools": ["Excel"],
    }

    prompt_input = _build_prompt_input(
        candidate=candidate,
        previous_segment="Suivi budgetaire mensuel.",
        next_segment="Presentation des resultats au responsable financier.",
    )

    assert set(prompt_input.keys()) == {"segment_text", "neighbor_context", "deterministic_hints", "allowed_domains"}
    assert prompt_input["segment_text"] == candidate["raw_text"]
    assert len(prompt_input["neighbor_context"]) == 2
    assert prompt_input["deterministic_hints"]["existing_action"] == "coordination"
    assert "finance" in prompt_input["allowed_domains"]

    system_prompt, user_prompt = _build_prompts(prompt_input)
    assert "Return JSON only" in system_prompt
    assert "Context JSON" not in system_prompt
    assert "segment_text" in user_prompt
    assert "allowed_domains" in user_prompt
