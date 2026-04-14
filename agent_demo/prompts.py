from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

REQUIRED_HEADERS = [
    "# Role Summary",
    "# Candidate Summary",
    "# Relevant Overlaps",
    "# Gaps / Weaker Signals",
    "# Recommended Positioning",
    "# CV Improvement Suggestions",
    "# Final Assessment",
]

EXTRACTION_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an experienced recruiter operating inside Elevia.
Your job is to extract only decision-useful facts from a role and a candidate profile.
Be precise, concrete, and conservative.
Return only valid JSON.""",
        ),
        (
            "human",
            """Review the offer and the candidate profile below.

OFFER
{offer_text}

CANDIDATE PROFILE
{candidate_text}

Return JSON with exactly these keys:
{{
  "role_title": "...",
  "role_scope": "2-3 sentence summary of the role, company context, and mission",
  "required_skills": ["..."],
  "required_tools": ["..."],
  "candidate_title": "...",
  "candidate_scope": "2-3 sentence summary of the candidate profile",
  "candidate_strengths": ["..."],
  "candidate_tools": ["..."],
  "overlaps": ["..."],
  "gaps": ["..."],
  "positioning_angle": "1-2 sentence positioning recommendation"
}}""",
        ),
    ]
)

ANALYSIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are an operator-facing recruiting analyst.
Write a concise, recruiter-credible markdown report.
Rules:
- Use only evidence present in the offer or candidate profile.
- No hidden scoring logic, no internal algorithm talk.
- Plain, direct language.
- Output ONLY the requested markdown headers in the requested order.
- Under each section, use short paragraphs or bullets.
- Final assessment must end with one of these labels: STRONG FIT, GOOD FIT, PARTIAL FIT, WEAK FIT.""",
        ),
        (
            "human",
            """Use the structured extraction below to write the final analysis.

EXTRACTION
{extraction_json}

RAW OFFER
{offer_text}

RAW CANDIDATE PROFILE
{candidate_text}

Use EXACTLY these sections and nothing else:
# Role Summary
# Candidate Summary
# Relevant Overlaps
# Gaps / Weaker Signals
# Recommended Positioning
# CV Improvement Suggestions
# Final Assessment""",
        ),
    ]
)
