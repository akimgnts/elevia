from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda

from .llm_client import get_llm
from .prompts import ANALYSIS_PROMPT, EXTRACTION_PROMPT, REQUIRED_HEADERS


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)
    return cleaned.strip()


def _parse_extraction(raw_text: str) -> dict[str, Any]:
    try:
        return json.loads(_strip_code_fences(raw_text))
    except json.JSONDecodeError:
        return {
            "role_title": "Unknown",
            "role_scope": "Extraction failed; relying on raw documents.",
            "required_skills": [],
            "required_tools": [],
            "candidate_title": "Unknown",
            "candidate_scope": "Extraction failed; relying on raw documents.",
            "candidate_strengths": [],
            "candidate_tools": [],
            "overlaps": [],
            "gaps": [],
            "positioning_angle": "Clarify the fit directly from the documents.",
        }


def _extract_sections(markdown: str) -> dict[str, str]:
    text = markdown.strip()
    positions: list[tuple[str, int]] = []
    for header in REQUIRED_HEADERS:
        idx = text.find(header)
        if idx != -1:
            positions.append((header, idx))
    positions.sort(key=lambda item: item[1])

    sections: dict[str, str] = {}
    for index, (header, start) in enumerate(positions):
        end = positions[index + 1][1] if index + 1 < len(positions) else len(text)
        body = text[start + len(header) : end].strip()
        sections[header] = body
    return sections


def ensure_markdown_sections(markdown: str) -> str:
    sections = _extract_sections(markdown)
    normalized_parts: list[str] = []
    for header in REQUIRED_HEADERS:
        body = sections.get(header, "- Information not available.")
        normalized_parts.append(f"{header}\n\n{body}".rstrip())
    return "\n\n".join(normalized_parts).strip() + "\n"


def run_fit_analysis(candidate_text: str, offer_text: str) -> str:
    llm = get_llm()

    extraction_chain = EXTRACTION_PROMPT | llm | StrOutputParser()

    def build_analysis_inputs(payload: dict[str, str]) -> dict[str, str]:
        extraction_raw = extraction_chain.invoke(
            {
                "offer_text": payload["offer_text"],
                "candidate_text": payload["candidate_text"],
            }
        )
        extraction_json = json.dumps(
            _parse_extraction(extraction_raw), ensure_ascii=False, indent=2
        )
        return {
            "offer_text": payload["offer_text"],
            "candidate_text": payload["candidate_text"],
            "extraction_json": extraction_json,
        }

    analysis_chain = (
        RunnableLambda(build_analysis_inputs)
        | ANALYSIS_PROMPT
        | llm
        | StrOutputParser()
        | RunnableLambda(ensure_markdown_sections)
    )

    return analysis_chain.invoke(
        {
            "offer_text": offer_text,
            "candidate_text": candidate_text,
        }
    )
