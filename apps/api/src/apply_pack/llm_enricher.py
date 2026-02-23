"""
llm_enricher.py — Optional LLM enrichment for Apply Pack v0.

Best-effort: if LLM fails or key is absent, caller gets baseline + warning.
Never logs raw text content.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.utils.env import get_llm_api_key  # noqa: E402

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a professional career assistant. "
    "You are given a baseline CV and cover letter in French markdown. "
    "Rewrite them to be more polished and professional.\n"
    "STRICT RULES:\n"
    "- Do NOT invent personal data, companies, or work experiences not present in the input.\n"
    "- Keep all placeholders like 'Candidat(e)' if no real name is provided.\n"
    "- Keep the same markdown structure (headings, bullets).\n"
    "- Keep the same language (French).\n"
    "- Keep the total length reasonable (CV ≤ 400 words, letter ≤ 300 words).\n"
    "- Return ONLY the rewritten texts, separated by exactly this delimiter on its own line: ---LETTER---\n"
    "  First the CV, then ---LETTER---, then the letter."
)


def enrich_with_llm(
    cv_text: str,
    letter_text: str,
    offer_title: str,
    company: str,
) -> Tuple[str, str, list]:
    """
    Attempt LLM enrichment of baseline cv_text and letter_text.

    Returns:
        (enriched_cv, enriched_letter, warnings)
        On failure: returns original texts + warning.
    """
    key = get_llm_api_key()
    if not key:
        logger.info("[apply-pack] LLM enrichment skipped: no API key")
        return cv_text, letter_text, ["LLM enrichment skipped: OPENAI_API_KEY not set"]

    try:
        import openai  # lazy import — not required in baseline mode
    except ImportError:
        logger.warning("[apply-pack] openai package not installed — skipping LLM")
        return cv_text, letter_text, ["LLM enrichment skipped: openai package not installed"]

    user_content = (
        f"# CV à réécrire (poste: {offer_title} — {company})\n\n"
        f"{cv_text}\n\n"
        f"---LETTER---\n\n"
        f"{letter_text}"
    )

    try:
        client = openai.OpenAI(api_key=key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.4,
            max_tokens=1500,
            timeout=20,
        )
        raw = response.choices[0].message.content or ""
        if "---LETTER---" in raw:
            parts = raw.split("---LETTER---", 1)
            enriched_cv = parts[0].strip()
            enriched_letter = parts[1].strip()
        else:
            # Fallback: treat whole response as CV, keep original letter
            logger.warning("[apply-pack] LLM response missing delimiter — using as CV only")
            enriched_cv = raw.strip() or cv_text
            enriched_letter = letter_text

        logger.info(
            "[apply-pack] LLM enrichment OK cv_len=%d letter_len=%d",
            len(enriched_cv), len(enriched_letter),
        )
        return enriched_cv, enriched_letter, []

    except Exception as exc:
        logger.warning("[apply-pack] LLM enrichment failed: %s", type(exc).__name__)
        return cv_text, letter_text, [f"LLM enrichment failed: {type(exc).__name__}"]
