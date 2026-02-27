"""
llm_skill_suggester.py — Optional LLM skill suggestions (best-effort).

Returns candidate skill tokens only. Never required for baseline.
"""
from __future__ import annotations

import importlib
import json
import logging
import os
import re
from typing import Dict, List, Optional

from api.utils.env import get_llm_api_key

logger = logging.getLogger(__name__)

MAX_LLM_CHARS = 12_000
DEFAULT_MODEL = os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL") or "gpt-4o-mini"

_WS_RE = re.compile(r"\s+")

try:
    from ..esco.extract import STOPWORDS, MIN_TOKEN_LENGTH
except ImportError:
    _esco_extract = importlib.import_module("esco.extract")
    STOPWORDS = _esco_extract.STOPWORDS
    MIN_TOKEN_LENGTH = _esco_extract.MIN_TOKEN_LENGTH


def _normalize_token(token: str) -> str:
    return _WS_RE.sub(" ", token.strip().lower())


def _build_prompt(cv_text: str, max_skills: int) -> str:
    return (
        "Extract skill keywords from the CV text. "
        "Return JSON only in this exact schema: { \"skills\": [\"skill1\", \"skill2\"] }. "
        f"Return at most {max_skills} skills. "
        "Skills only, no explanations. The CV can be bilingual French/English.\n\n"
        "CV TEXT:\n"
        f"{cv_text}"
    )


def _parse_skills(raw: str) -> List[str]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            payload = json.loads(raw[start : end + 1])
        else:
            return []
    if not isinstance(payload, dict):
        return []
    skills = payload.get("skills", [])
    if not isinstance(skills, list):
        return []
    cleaned: List[str] = []
    seen = set()
    for item in skills:
        if not isinstance(item, str):
            continue
        token = _normalize_token(item)
        if not token:
            continue
        if token in STOPWORDS:
            continue
        if len(token) < MIN_TOKEN_LENGTH:
            continue
        if token in seen:
            continue
        seen.add(token)
        cleaned.append(token)
    return cleaned


def suggest_skills_from_cv(cv_text: str, *, max_skills: int = 60) -> Dict[str, Optional[object]]:
    """
    Return LLM skill suggestions, or an error message if unavailable.

    Returns:
        {
            "skills": List[str],
            "error": Optional[str],
            "warning": Optional[str],
            "model": Optional[str],
        }
    """
    key = get_llm_api_key()
    if not key:
        return {
            "skills": [],
            "error": "OPENAI_API_KEY is not set",
            "warning": "LLM enrichment skipped: OPENAI_API_KEY not set",
            "model": None,
        }

    try:
        import openai
    except ImportError:
        return {
            "skills": [],
            "error": "openai package not installed",
            "warning": "LLM enrichment skipped: openai package not installed",
            "model": None,
        }

    text = (cv_text or "")[:MAX_LLM_CHARS]
    prompt = _build_prompt(text, max_skills=max_skills)
    model = DEFAULT_MODEL

    try:
        client = openai.OpenAI(api_key=key)
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": "You extract skill keywords and return JSON only."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        if not response.choices:
            return {
                "skills": [],
                "error": "LLM response empty",
                "warning": "LLM enrichment failed: empty response",
                "model": model,
            }
        raw = response.choices[0].message.content or ""
        skills = _parse_skills(raw)[:max_skills]
        return {"skills": skills, "error": None, "warning": None, "model": model}
    except Exception as exc:
        logger.warning("[llm_suggester] LLM call failed: %s", type(exc).__name__)
        return {
            "skills": [],
            "error": f"LLM call failed: {type(exc).__name__}",
            "warning": f"LLM enrichment failed: {type(exc).__name__}",
            "model": model,
        }
