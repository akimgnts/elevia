from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from evaluate_document_understanding_phase2_block1 import (
    _aggregate_results,
    _comparison_label,
    _markdown_report,
)


def test_comparison_label_rules_are_deterministic():
    better_identity = {
        "identity_detected_legacy": False,
        "identity_detected_understanding": True,
        "experience_count_legacy": 1,
        "experience_count_understanding": 1,
        "suspicious_merges_count": 0,
    }
    better_experience = {
        "identity_detected_legacy": True,
        "identity_detected_understanding": True,
        "experience_count_legacy": 1,
        "experience_count_understanding": 2,
        "suspicious_merges_count": 0,
    }
    worse_identity = {
        "identity_detected_legacy": True,
        "identity_detected_understanding": False,
        "experience_count_legacy": 1,
        "experience_count_understanding": 1,
        "suspicious_merges_count": 0,
    }
    worse_experience = {
        "identity_detected_legacy": True,
        "identity_detected_understanding": True,
        "experience_count_legacy": 2,
        "experience_count_understanding": 0,
        "suspicious_merges_count": 0,
    }
    mixed_identity = {
        "identity_detected_legacy": False,
        "identity_detected_understanding": True,
        "experience_count_legacy": 2,
        "experience_count_understanding": 0,
        "suspicious_merges_count": 0,
    }
    mixed_experience = {
        "identity_detected_legacy": True,
        "identity_detected_understanding": False,
        "experience_count_legacy": 0,
        "experience_count_understanding": 2,
        "suspicious_merges_count": 0,
    }
    equal = {
        "identity_detected_legacy": True,
        "identity_detected_understanding": True,
        "experience_count_legacy": 1,
        "experience_count_understanding": 1,
        "suspicious_merges_count": 1,
    }

    assert _comparison_label(better_identity) == "better"
    assert _comparison_label(better_experience) == "better"
    assert _comparison_label(worse_identity) == "worse"
    assert _comparison_label(worse_experience) == "worse"
    assert _comparison_label(mixed_identity) == "mixed"
    assert _comparison_label(mixed_experience) == "mixed"
    assert _comparison_label(equal) == "equal"


def test_aggregate_results_counts_labels_and_errors():
    report = _aggregate_results(
        [
            {"status": "ok", "comparison_label": "better"},
            {"status": "ok", "comparison_label": "equal"},
            {"status": "ok", "comparison_label": "mixed"},
            {"status": "error", "error": "parse_failed"},
        ]
    )

    assert report["count"] == 4
    assert report["parsed_count"] == 3
    assert report["error_count"] == 1
    assert report["label_counts"] == {
        "better": 1,
        "equal": 1,
        "worse": 0,
        "mixed": 1,
    }


def test_aggregate_results_preserve_full_label_shape_with_empty_input():
    report = _aggregate_results([])

    assert report == {
        "count": 0,
        "parsed_count": 0,
        "error_count": 0,
        "label_counts": {
            "better": 0,
            "equal": 0,
            "worse": 0,
            "mixed": 0,
        },
    }


def test_markdown_report_includes_aggregate_and_case_metrics():
    markdown = _markdown_report(
        {
            "input": {
                "directory": "/tmp/cvtest",
                "file_count": 2,
            },
            "aggregate": {
                "parsed_count": 1,
                "error_count": 1,
                "label_counts": {
                    "better": 1,
                    "equal": 0,
                    "worse": 0,
                    "mixed": 0,
                },
            },
            "cases": [
                {
                    "file": "good.pdf",
                    "status": "ok",
                    "comparison_label": "better",
                    "comparison_reason": "identity improved",
                    "comparison_metrics": {
                        "identity_detected_legacy": False,
                        "identity_detected_understanding": True,
                        "experience_count_legacy": 0,
                        "experience_count_understanding": 1,
                        "project_count_understanding": 0,
                        "suspicious_merges_count": 0,
                        "orphan_lines_count": 2,
                        "invalid_experience_headers_count": 1,
                    },
                },
                {
                    "file": "bad.pdf",
                    "status": "error",
                    "error": "parse_failed",
                    "error_detail": "boom",
                },
            ],
        }
    )

    assert "# Document Understanding Phase 2 Block 1 Report" in markdown
    assert "- better: `1`" in markdown
    assert "- `good.pdf`: `ok`" in markdown
    assert "identity_legacy=False" in markdown
    assert "invalid_headers=1" in markdown
    assert "- `bad.pdf`: `error`" in markdown
    assert "detail: `boom`" in markdown
