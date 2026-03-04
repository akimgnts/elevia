"""
Static checks to prevent UI regressions for Analyze AI recovery error mapping.
"""
from pathlib import Path

ANALYZE_PAGE = Path("apps/web/src/pages/AnalyzePage.tsx").read_text(encoding="utf-8")
API_TS = Path("apps/web/src/lib/api.ts").read_text(encoding="utf-8")


def test_no_undefined_rendered():
    assert "undefined" not in ANALYZE_PAGE, (
        "AnalyzePage should never render raw 'undefined' in error messages"
    )


def test_error_fallback_codes_present():
    for code in ["UNKNOWN_ERROR", "NETWORK_ERROR", "AI_DISABLED"]:
        assert code in ANALYZE_PAGE, (
            f"AnalyzePage should map fallback error code {code}"
        )


def test_api_network_error_mapping_present():
    assert "NETWORK_ERROR" in API_TS, (
        "fetchRecoverSkills should map network errors to NETWORK_ERROR"
    )
