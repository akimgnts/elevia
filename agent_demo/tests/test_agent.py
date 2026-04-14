from __future__ import annotations

from langchain_core.runnables import RunnableLambda

from agent_demo.agent import ensure_markdown_sections, run_fit_analysis
from agent_demo.prompts import REQUIRED_HEADERS


def test_ensure_markdown_sections_normalizes_required_headers() -> None:
    raw = "# Candidate Summary\n\nBody only\n\n# Final Assessment\n\nGOOD FIT"
    normalized = ensure_markdown_sections(raw)
    for header in REQUIRED_HEADERS:
        assert header in normalized
    assert normalized.index("# Role Summary") < normalized.index("# Final Assessment")


def test_run_fit_analysis_works_with_mocked_llm(monkeypatch) -> None:
    def fake_llm(prompt_value):
        text = "\n".join(message.content for message in prompt_value.to_messages())
        if "Return JSON with exactly these keys" in text:
            return '{"role_title":"Business Developer","role_scope":"Role scope","required_skills":["prospection"],"required_tools":["CRM"],"candidate_title":"Business Developer","candidate_scope":"Candidate scope","candidate_strengths":["prospection"],"candidate_tools":["HubSpot"],"overlaps":["prospection B2B"],"gaps":["marché allemand"],"positioning_angle":"Positionner sur la vente B2B technique."}'
        return "# Role Summary\n\nRole\n\n# Candidate Summary\n\nCandidate\n\n# Relevant Overlaps\n\n- overlap\n\n# Gaps / Weaker Signals\n\n- gap\n\n# Recommended Positioning\n\nPositioning\n\n# CV Improvement Suggestions\n\n- improve\n\n# Final Assessment\n\nGOOD FIT"

    monkeypatch.setattr("agent_demo.agent.get_llm", lambda: RunnableLambda(fake_llm))

    result = run_fit_analysis(
        candidate_text="Expérience en prospection B2B.",
        offer_text="Business Developer Allemagne.",
    )

    for header in REQUIRED_HEADERS:
        assert header in result
    assert "GOOD FIT" in result
