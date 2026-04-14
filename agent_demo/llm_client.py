from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
API_ENV_PATH = REPO_ROOT / "apps" / "api" / ".env"
DEFAULT_MODEL = "gpt-4o-mini"


class LlmUnavailableError(RuntimeError):
    """Raised when the demo cannot initialize an LLM cleanly."""


load_dotenv(API_ENV_PATH, override=False)


def get_api_key() -> str | None:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        return key
    legacy = os.getenv("LLM_API_KEY", "").strip()
    return legacy or None


def is_llm_available() -> bool:
    return bool(get_api_key())


def get_model_name() -> str:
    return os.getenv("LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def get_llm(temperature: float = 0.15):
    api_key = get_api_key()
    if not api_key:
        raise LlmUnavailableError(
            "OPENAI_API_KEY is not configured. Add it to apps/api/.env or export it in the shell."
        )

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise LlmUnavailableError(
            "langchain-openai is not installed. Install agent_demo/requirements.txt in the repo .venv."
        ) from exc

    return ChatOpenAI(
        model=get_model_name(),
        temperature=temperature,
        api_key=api_key,
        max_tokens=1800,
        timeout=60,
    )
