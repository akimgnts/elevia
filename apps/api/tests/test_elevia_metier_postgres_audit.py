from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_run_elevia_metier_postgres_audit_quick_mode_generates_expected_artifacts(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "run_elevia_metier_postgres_audit.py"
    output_json = tmp_path / "postgres_audit.json"
    output_md = tmp_path / "postgres_audit.md"

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--mode",
            "quick",
            "--output-json",
            str(output_json),
            "--output-md",
            str(output_md),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert output_json.exists()
    assert output_md.exists()

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["scope"]["source"] == "business_france"
    assert "domain_distribution" in payload
    assert "domains" in payload
    assert "generic_signals" in payload
    assert "emerging_patterns" in payload
    assert "recommendations_v1" in payload
    assert "data_centric_bias_risks" in payload

    domain_names = {item["domain"] for item in payload["domain_distribution"]}
    assert "data" in domain_names
    assert "engineering" in domain_names
