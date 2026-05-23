from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_show_elevia_metier_clusters_supports_json_and_markdown(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "show_elevia_metier_clusters.py"
    markdown_output = tmp_path / "clusters.md"

    json_result = subprocess.run(
        [sys.executable, str(script_path), "--json"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert json_result.returncode == 0, json_result.stderr
    payload = json.loads(json_result.stdout)
    assert payload["registry_version"]
    assert payload["cluster_count"] == 8
    assert payload["cluster_order"][0] == "DATA_ENGINEERING"
    assert payload["clusters"]["FINANCE_CONTROL"]["strong_signals"]
    assert "forbidden_standalone_anchors" in payload["clusters"]["BI_ANALYTICS"]

    markdown_result = subprocess.run(
        [sys.executable, str(script_path), "--markdown", "--output", str(markdown_output)],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert markdown_result.returncode == 0, markdown_result.stderr
    assert markdown_output.exists()
    content = markdown_output.read_text(encoding="utf-8")
    assert "# Elevia Metier Clusters V1 Overview" in content
    assert "## `DATA_ENGINEERING`" in content
    assert "## `HR_TALENT_OPERATIONS`" in content
