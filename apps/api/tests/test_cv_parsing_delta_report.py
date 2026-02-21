from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_cv_parsing_delta_report_subprocess():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "apps" / "api" / "scripts" / "cv_parsing_delta_report.py"
    fixture = repo_root / "apps" / "api" / "fixtures" / "cv_samples" / "sample_delta.txt"

    result = subprocess.run(
        [sys.executable, str(script), "--text", str(fixture), "--json"],
        capture_output=True,
        text=True,
        check=True,
    )

    report = json.loads(result.stdout)
    assert "A" in report
    assert "B" in report
    assert "delta" in report
    assert report["A"]["skills"]


def test_cv_parsing_delta_report_with_llm(monkeypatch, tmp_path):
    api_root = Path(__file__).resolve().parents[1]
    scripts_dir = api_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    import cv_parsing_delta_report as delta  # noqa: E402

    fixture = api_root / "fixtures" / "cv_samples" / "sample_delta.txt"
    text = fixture.read_text(encoding="utf-8")

    llm_skills = {"snowflake", "kafka", "vector database"}

    def fake_get_llm_skills(
        cv_text: str,
        provider: str,
        model: str,
        max_skills: int,
        cache_dir: Path = delta.CACHE_DIR,
        cache_bust: bool = False,
    ):
        return llm_skills, True, "fake-cache-key"

    monkeypatch.setattr(delta, "get_llm_skills", fake_get_llm_skills)

    report = delta.build_report(
        cv_text=text,
        with_llm=True,
        provider="openai",
        model="gpt-4o-mini",
        max_skills=30,
        cache_dir=tmp_path,
        cache_bust=True,
        input_path=str(fixture),
    )

    added = set(report["delta"]["added_skills"])
    assert llm_skills.issubset(added)
    assert report["delta"]["unchanged_skills_count"] >= 1
