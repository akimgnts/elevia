from __future__ import annotations

from pathlib import Path


def test_analyze_parse_file_default_no_legacy_llm():
    source = Path("apps/web/src/pages/AnalyzePage.tsx").read_text(encoding="utf-8")

    assert "parseFileEnriched" in source, "Legacy LLM path should exist but be dev-gated."
    assert "legacyLlmEnabled" in source, "DEV toggle for legacy LLM must gate the call."

    idx_use = source.find("useLegacyLlm")
    idx_call = source.find("? await parseFileEnriched")
    assert idx_use != -1 and idx_call != -1 and idx_use < idx_call, (
        "parseFileEnriched must be gated behind useLegacyLlm."
    )

    assert "analysisMode === \"llm\"" not in source, (
        "Analyze default flow must not call legacy LLM based on analysisMode."
    )
