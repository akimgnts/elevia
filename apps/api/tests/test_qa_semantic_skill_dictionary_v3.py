#!/usr/bin/env python3
"""test_qa_semantic_skill_dictionary_v3 — tests for semantic QA audit."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_script_executes_without_error():
    """Script should run without error."""
    result = subprocess.run(
        ["python3", "apps/api/scripts/qa_semantic_skill_dictionary_v3.py"],
        cwd=Path(__file__).parent.parent.parent.parent.parent,
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Script failed:\n{result.stderr}"


def test_output_files_created():
    """Both output files should be created."""
    json_path = Path(__file__).parent.parent.parent.parent / "audit" / "skill_dictionary_v3_semantic_findings.json"
    md_path = Path(__file__).parent.parent.parent.parent / "audit" / "SKILL_DICTIONARY_V3_SEMANTIC_QA.md"

    assert json_path.exists(), f"JSON file not created: {json_path}"
    assert md_path.exists(), f"Markdown file not created: {md_path}"


def test_json_contains_required_keys():
    """JSON should have all required keys."""
    json_path = Path(__file__).parent.parent.parent.parent / "audit" / "skill_dictionary_v3_semantic_findings.json"

    data = json.loads(json_path.read_text())

    required_keys = [
        "status",
        "qa_score",
        "compression_ratio",
        "semantic_duplicate_candidates",
        "polluted_clusters",
        "over_specific_canonicals",
        "low_quality_labels",
        "domain_tag_fixes",
        "priority_fix_plan"
    ]

    for key in required_keys:
        assert key in data, f"Missing key: {key}"


def test_markdown_contains_executive_summary():
    """Markdown should contain Executive Summary."""
    md_path = Path(__file__).parent.parent.parent.parent / "audit" / "SKILL_DICTIONARY_V3_SEMANTIC_QA.md"

    content = md_path.read_text()
    assert "Executive Summary" in content, "Missing Executive Summary section"
    assert "NOT_READY" in content, "Missing NOT_READY verdict"


def test_compression_ratio_calculated():
    """Compression ratio should be calculated."""
    json_path = Path(__file__).parent.parent.parent.parent / "audit" / "skill_dictionary_v3_semantic_findings.json"

    data = json.loads(json_path.read_text())

    assert "compression_ratio" in data
    assert isinstance(data["compression_ratio"], (int, float))
    assert data["compression_ratio"] > 1.0


def test_compression_blocker_when_low():
    """If compression_ratio < 1.5, status should NOT be READY."""
    json_path = Path(__file__).parent.parent.parent.parent / "audit" / "skill_dictionary_v3_semantic_findings.json"

    data = json.loads(json_path.read_text())

    if data["compression_ratio"] < 1.5:
        assert data["status"] != "READY", "Status should not be READY when compression < 1.5x"


def test_semantic_duplicates_detected():
    """Should detect semantic duplicate groups."""
    json_path = Path(__file__).parent.parent.parent.parent / "audit" / "skill_dictionary_v3_semantic_findings.json"

    data = json.loads(json_path.read_text())

    # Should have some semantic duplicates
    assert len(data["semantic_duplicate_candidates"]) > 0, "No semantic duplicates detected"


def test_duplicate_python_detected():
    """Should detect python and python_programming as duplicates."""
    json_path = Path(__file__).parent.parent.parent.parent / "audit" / "skill_dictionary_v3_semantic_findings.json"

    data = json.loads(json_path.read_text())

    python_groups = [
        dup for dup in data["semantic_duplicate_candidates"]
        if any("python" in label.lower() for label in dup.get("labels", []))
    ]

    assert len(python_groups) > 0, "Should detect python duplicate group"


def test_low_quality_labels_detected():
    """Should detect low quality labels."""
    json_path = Path(__file__).parent.parent.parent.parent / "audit" / "skill_dictionary_v3_semantic_findings.json"

    data = json.loads(json_path.read_text())

    assert len(data["low_quality_labels"]) > 0, "No low quality labels detected"


def test_domain_tag_mismatches_detected():
    """Should detect domain tag semantic mismatches."""
    json_path = Path(__file__).parent.parent.parent.parent / "audit" / "skill_dictionary_v3_semantic_findings.json"

    data = json.loads(json_path.read_text())

    assert len(data["domain_tag_fixes"]) > 0, "No domain tag mismatches detected"


def test_qa_score_not_perfect():
    """QA score should not be 100 (since dictionary has issues)."""
    json_path = Path(__file__).parent.parent.parent.parent / "audit" / "skill_dictionary_v3_semantic_findings.json"

    data = json.loads(json_path.read_text())

    # V2 has known issues, so score should be < 85
    assert data["qa_score"] < 85, "QA score should reflect dictionary issues"


def test_status_not_ready():
    """Status should be NOT_READY for V2."""
    json_path = Path(__file__).parent.parent.parent.parent / "audit" / "skill_dictionary_v3_semantic_findings.json"

    data = json.loads(json_path.read_text())

    assert data["status"] == "NOT_READY", "V2 should be marked as NOT_READY"


def test_priority_fix_plan_populated():
    """Priority fix plan should have P0 blockers."""
    json_path = Path(__file__).parent.parent.parent.parent / "audit" / "skill_dictionary_v3_semantic_findings.json"

    data = json.loads(json_path.read_text())

    assert "priority_fix_plan" in data
    assert len(data["priority_fix_plan"].get("P0", [])) > 0, "Should have P0 blockers"
