from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_run_elevia_metier_audit_quick_mode_generates_expected_artifacts(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "run_elevia_metier_audit.py"
    output_json = tmp_path / "audit.json"
    output_md = tmp_path / "audit.md"

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
    assert "profiles" in payload
    assert "offers" in payload
    assert "summary" in payload
    assert "false_positives_observed" in payload["summary"]
    assert "clusters_ambigus" in payload["summary"]
    assert "signaux_reellement_discriminants" in payload["summary"]

    profile_map = {item["id"]: item for item in payload["profiles"]}
    assert profile_map["sample_delta_txt"]["result"]["primary_cluster"] == "DATA_ENGINEERING"
    assert profile_map["golden_01"]["result"]["primary_cluster"] == "BI_ANALYTICS"
