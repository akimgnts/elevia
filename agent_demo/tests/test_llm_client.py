from __future__ import annotations

import pytest

from agent_demo.llm_client import LlmUnavailableError, get_api_key, is_llm_available, get_llm


def test_llm_detection_false_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert get_api_key() is None
    assert is_llm_available() is False


def test_get_llm_raises_cleanly_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(LlmUnavailableError):
        get_llm()
