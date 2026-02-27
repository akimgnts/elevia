"""
env.py — Environment key helpers.

Canonical LLM key: OPENAI_API_KEY
Legacy fallback:   LLM_API_KEY  (logs a deprecation warning)
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def get_llm_api_key() -> Optional[str]:
    """
    Return the active LLM API key, or None if not set.

    Priority:
      1. OPENAI_API_KEY  (canonical — set this one)
      2. LLM_API_KEY     (legacy — triggers a deprecation warning)
    """
    key = os.getenv("OPENAI_API_KEY")
    if key and key.strip():
        return key.strip()

    key = os.getenv("LLM_API_KEY")
    if key and key.strip():
        logger.warning(
            "[env] LLM_API_KEY is deprecated — set OPENAI_API_KEY instead. "
            "Support for LLM_API_KEY will be removed in a future release."
        )
        return key.strip()

    return None
