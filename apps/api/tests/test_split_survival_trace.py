"""
test_split_survival_trace.py — verify split survival trace is emitted and deterministic.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.extraction.tight_skill_extractor import extract_tight_skills


ALLOWED_REASONS = {
    "duplicate_existing_candidate",
    "filtered_score_too_low",
    "removed_by_generic_filter",
    "removed_by_numeric_filter",
    "removed_by_repetition_filter",
    "generated_composite_rejected",
}


def _get_trace(text: str):
    result = extract_tight_skills(text, cluster="DATA_IT")
    return result.metrics.get("split_trace") or []


def test_trace_contains_generated_chunks():
    trace = _get_trace("API REST JSON Power BI")
    assert trace, "Split trace must be present for mixed chunk"
    first = trace[0]
    generated = first.get("generated") or []
    assert "api rest" in generated, f"expected api rest in generated, got {generated}"
    assert "power bi" in generated, f"expected power bi in generated, got {generated}"


def test_trace_contains_sql_python_api():
    trace = _get_trace("analyse technique SQL Python APIs")
    assert trace, "Split trace must be present for mixed chunk"
    generated = trace[0].get("generated") or []
    for expected in ("sql", "python", "api"):
        assert expected in generated, f"expected {expected} in generated, got {generated}"


def test_drop_reason_enum():
    trace = _get_trace("API REST JSON Power BI")
    for item in trace:
        for dropped in item.get("dropped") or []:
            reason = dropped.get("reason")
            assert reason in ALLOWED_REASONS, f"invalid drop reason: {reason}"


def test_deterministic_trace():
    t1 = _get_trace("API REST JSON Power BI")
    t2 = _get_trace("API REST JSON Power BI")
    assert t1 == t2, "split_trace must be deterministic"
