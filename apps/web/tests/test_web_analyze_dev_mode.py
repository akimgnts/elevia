"""
Static checks for Analyze Dev Mode panel wiring.
"""
from pathlib import Path


ANALYZE_PAGE = Path("apps/web/src/pages/AnalyzePage.tsx").read_text(encoding="utf-8")
DEV_PANEL = Path("apps/web/src/components/analyze/DevPanel.tsx").read_text(encoding="utf-8")


def test_dev_panel_is_dev_gated_and_receives_analyze_dev():
    assert "showDevPanel" in ANALYZE_PAGE, "AnalyzePage must define showDevPanel"
    assert "showDevPanel &&" in ANALYZE_PAGE, "DevPanel must be gated by showDevPanel"
    assert "DevPanel" in ANALYZE_PAGE, "AnalyzePage must render DevPanel"
    assert "analyze_dev" in ANALYZE_PAGE, "AnalyzePage must pass analyze_dev to DevPanel"


def test_dev_panel_renders_counters_block():
    assert "Counters" in DEV_PANEL, "DevPanel should render counters section"
    assert "raw_count" in DEV_PANEL, "DevPanel should display raw_count"
    assert "not_available_at_parse_stage" in DEV_PANEL, "DevPanel should show fallback status"
