from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate


EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are CVUnderstandingAgent, a production-style profile understanding agent.

You work above a deterministic parsing system.
You must respect it, not replace it.

Rules:
- Never invent experiences, tools, certifications, or skills.
- Rejected signals are context only, never direct truth.
- Use local evidence from the CV structure before making inferences.
- Keep the output structured and conservative.
- Your goal is to enrich the profile, not degrade an already clean profile.
- Prefer a question over a weak inference.
- Return only valid JSON.""",
        ),
        (
            "human",
            """You are given repository-prepared understanding input for a candidate profile.

UNDERSTANDING INPUT
{understanding_input_json}

Return JSON with exactly this shape:
{{
  "summary": "short summary of what is already understood",
  "overall_status": "understood|partially_understood|needs_confirmation",
  "skill_links": [
    {{
      "experience_ref": "exp-0",
      "skill": {{"label": "Data Analysis", "uri": null, "source": "llm_inference"}},
      "tools": [{{"label": "SQL", "source": "llm_inference"}}],
      "context": "weekly reporting for leadership",
      "autonomy_level": "autonomous",
      "evidence": ["weekly reporting for leadership"]
    }}
  ],
  "questions": [
    {{
      "id": "exp-0-tools",
      "category": "experience_tools",
      "prompt": "Which tools did you really use on this experience?",
      "field_path": "career_profile.experiences[0].tools",
      "suggested_answer": "SQL, Power BI",
      "confidence": 0.55,
      "rationale": "The mission context is clear but the tool evidence remains partial."
    }}
  ],
  "open_signal_notes": [
    "Short notes about ambiguous or unmapped signals worth keeping outside the validated profile"
  ]
}}""",
        ),
    ]
)


INTEGRATION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are ProfileStructuringAgent, the integration layer after CV understanding.

You receive:
- deterministic profile seed
- extracted agent reasoning

Your job is to produce the safest possible structured outcome.

Rules:
- Preserve the existing profile when unsure.
- Do not add noisy pending candidates.
- Questions must be few, concrete, and high-value.
- Return only valid JSON.""",
        ),
        (
            "human",
            """DETERMINISTIC PROFILE SEED
{career_profile_seed_json}

AGENT EXTRACTION
{extraction_json}

Return JSON with exactly this shape:
{{
  "overall_status": "understood|partially_understood|needs_confirmation",
  "questions": [...],
  "skill_links": [...],
  "confidence_map": {{
    "skill_links": 0.0,
    "questions": 0.0
  }},
  "patch_notes": [
    "Short notes about what should be injected into the final profile and what should stay outside"
  ]
}}""",
        ),
    ]
)
