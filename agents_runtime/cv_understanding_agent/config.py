from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ENV_PATH = REPO_ROOT / "apps" / "api" / ".env"

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.15

load_dotenv(API_ENV_PATH, override=False)


class LlmUnavailableError(RuntimeError):
    """Raised when the runtime cannot initialize an LLM."""


def get_api_key() -> str | None:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        return key
    legacy = os.getenv("LLM_API_KEY", "").strip()
    return legacy or None


def get_model_name() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def get_llm(temperature: float = DEFAULT_TEMPERATURE):
    api_key = get_api_key()
    if not api_key:
        raise LlmUnavailableError(
            "OPENAI_API_KEY is not configured. Add it to apps/api/.env or export it before starting the agent runtime."
        )

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise LlmUnavailableError(
            "langchain-openai is not installed. Install agents_runtime/requirements.txt before running this runtime."
        ) from exc

    return ChatOpenAI(
        model=get_model_name(),
        temperature=temperature,
        api_key=api_key,
        max_tokens=2500,
        timeout=90,
    )
