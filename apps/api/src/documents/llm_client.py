"""
llm_client.py — Safe OpenAI wrapper for CV Generator.

Rules:
  - API key read once via get_llm_api_key() — NEVER logged, NEVER returned
  - 1 call per CV generation (no chain-of-thought)
  - JSON mode enforced via response_format
  - 1 retry on transient failure
  - Raises RuntimeError with safe message on failure
  - Log: DOC_CV_LLM_CALL (model, chars, duration — no content)
"""

import json
import logging
import os
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"
_TIMEOUT_S = 30
_MAX_RETRIES = 1
_MAX_TOKENS = 1200


def _get_api_key() -> Optional[str]:
    """
    Return LLM API key — NEVER log or return this value externally.
    Priority: get_llm_api_key() → OPENAI_API_KEY → OPENAI_KEY.
    """
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from api.utils.env import get_llm_api_key
        key = get_llm_api_key()
        if key:
            return key
    except Exception:
        pass

    for name in ("OPENAI_API_KEY", "OPENAI_KEY", "LLM_API_KEY"):
        v = os.environ.get(name, "").strip()
        if v:
            return v

    return None


def is_llm_available() -> bool:
    """Check if LLM is configured — safe (no key value returned)."""
    return bool(_get_api_key())


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
) -> Tuple[dict, int, int, int]:
    """
    Call OpenAI with JSON mode. Single call, 1 retry on transient error.

    Args:
        system_prompt: System message (instructs JSON-only output)
        user_prompt:   User message with context

    Returns:
        (parsed_dict, input_chars, output_chars, duration_ms)

    Raises:
        RuntimeError with safe message (no secrets) on any failure.

    Logs:
        DOC_CV_LLM_CALL — model, char counts, duration. No content.
    """
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("LLM_DISABLED: no API key configured")

    try:
        from openai import OpenAI, APITimeoutError, APIConnectionError, APIStatusError
    except ImportError:
        raise RuntimeError("LLM_DISABLED: openai package not installed")

    client = OpenAI(api_key=api_key, timeout=_TIMEOUT_S)
    input_chars = len(system_prompt) + len(user_prompt)
    last_error: Optional[Exception] = None
    t0 = time.time()

    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=_MAX_TOKENS,
            )
            break
        except (APITimeoutError, APIConnectionError) as exc:
            last_error = exc
            if attempt < _MAX_RETRIES:
                time.sleep(1.5)
                continue
            raise RuntimeError("LLM_ERROR: timeout/connection") from exc
        except APIStatusError as exc:
            raise RuntimeError(f"LLM_ERROR: status {exc.status_code}") from exc
        except Exception as exc:
            raise RuntimeError(f"LLM_ERROR: {type(exc).__name__}") from exc

    duration_ms = int((time.time() - t0) * 1000)
    raw: str = (response.choices[0].message.content or "{}").strip()
    output_chars = len(raw)

    # Structured log — no content, no key
    logger.info(
        '{"event":"DOC_CV_LLM_CALL","model":"%s","input_chars":%d,'
        '"output_chars":%d,"duration_ms":%d}',
        _MODEL,
        input_chars,
        output_chars,
        duration_ms,
    )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"LLM_JSON_PARSE_ERROR: {exc}") from exc

    return parsed, input_chars, output_chars, duration_ms
