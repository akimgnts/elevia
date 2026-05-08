"""
structured_cv_extractor.py — AI-powered structured CV extraction.

Extracts CV into strict JSON schema using LLM.
Graceful fallback if LLM unavailable or fails.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.utils.env import get_llm_api_key

from .structured_cv_schemas import StructuredCV
from .structured_cv_mock import extract_structured_cv_mock

logger = logging.getLogger(__name__)

# Note: Flags are checked at runtime in extract_structured_cv, not at import time
# This allows tests to change env vars and see the effect

_SYSTEM_PROMPT = """You are a professional CV parser. Extract structured information from CVs in strict JSON format.

RULES:
1. RESPOND ONLY WITH VALID JSON (no markdown, no explanation)
2. Never invent information not present in CV
3. Separate experiences from projects (projects = personal/academic work)
4. Responsibilities must describe job duties, NOT project titles
5. Skills should be contextual (attached to where they were used)
6. If unsure about a field, use empty string "" or empty list []
7. Keep original text formatting (no translation unless asked)

JSON Schema:
{
  "headline": "string or empty",
  "target_role": "string or empty",
  "summary": "string or empty",
  "experiences": [
    {
      "title": "Job title",
      "company": "Company name",
      "dates": "MM/YYYY - MM/YYYY or similar",
      "location": "City/Country",
      "responsibilities": ["bullet 1", "bullet 2"],
      "tools": ["tool1", "tool2"],
      "skills": ["skill1", "skill2"]
    }
  ],
  "projects": [
    {
      "name": "Project name",
      "description": "What it does",
      "tools": ["tool1"],
      "skills": ["skill1"]
    }
  ],
  "education": [
    {
      "institution": "University name",
      "degree": "Bachelor/Master etc",
      "field": "Field of study",
      "dates": "Year or date range",
      "location": "City/Country"
    }
  ],
  "certifications": [
    {
      "name": "Cert name",
      "issuer": "Issuing org",
      "date": "Year or date"
    }
  ],
  "global_skills": ["skill1", "skill2"],
  "languages": ["English - C1", "French - Native"],
  "warnings": ["any quality warnings"]
}
"""


def extract_structured_cv(cv_text: str) -> Optional[StructuredCV]:
    """
    Extract CV into structured JSON using LLM or mock.

    Returns:
        StructuredCV if successful, None if disabled or failed.

    On failure:
        Logs warning, returns None (caller uses fallback parser).
    """
    # Check flags at runtime (allows test env var changes)
    mock_enabled = os.getenv("ELEVIA_STRUCTURED_CV_MOCK", "").lower() in ("1", "true", "yes")
    ai_enabled = os.getenv("ELEVIA_STRUCTURED_CV_AI", "").lower() in ("1", "true", "yes")

    # Try mock first (development/testing only)
    if mock_enabled:
        mock_cv = extract_structured_cv_mock(cv_text)
        if mock_cv:
            logger.info("[structured-cv] Using MOCK extraction (ELEVIA_STRUCTURED_CV_MOCK=1)")
            return mock_cv

    if not ai_enabled:
        logger.debug("[structured-cv] AI extraction disabled (ELEVIA_STRUCTURED_CV_AI not set)")
        return None

    key = get_llm_api_key()
    if not key:
        logger.debug("[structured-cv] LLM key not set, using fallback parser")
        return None

    try:
        import openai
    except ImportError:
        logger.warning("[structured-cv] openai not installed, using fallback")
        return None

    try:
        client = openai.OpenAI(api_key=key)
        response = client.chat.completions.create(
            model=os.getenv("ELEVIA_CV_STRUCTURER_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": cv_text},
            ],
            temperature=0.2,  # Low temp for deterministic parsing
            max_tokens=4000,
            timeout=30,
        )

        raw_response = response.choices[0].message.content or ""

        # Extract JSON from response (may have prefix/suffix)
        json_str = _extract_json_from_response(raw_response)
        if not json_str:
            logger.warning("[structured-cv] No JSON in LLM response")
            return None

        data = json.loads(json_str)
        structured = StructuredCV(**data)

        logger.info("[structured-cv] Extraction OK: %d exp, %d proj",
                   len(structured.experiences), len(structured.projects))
        return structured

    except json.JSONDecodeError as e:
        logger.warning("[structured-cv] JSON parse error: %s", e)
        return None
    except Exception as e:
        logger.warning("[structured-cv] Extraction failed: %s", type(e).__name__)
        return None


def _extract_json_from_response(text: str) -> Optional[str]:
    """Extract JSON block from LLM response (may have markdown/explanation)."""
    text = text.strip()

    # Try direct JSON parse first
    if text.startswith("{"):
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass

    # Try markdown code block
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            return text[start:end].strip()

    if "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            candidate = text[start:end].strip()
            if candidate.startswith("{"):
                return candidate

    # Last resort: find { ... }
    if "{" in text and "}" in text:
        start = text.find("{")
        # Find matching closing brace
        count = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                count += 1
            elif text[i] == "}":
                count -= 1
                if count == 0:
                    return text[start : i + 1]

    return None
