from pathlib import Path
import subprocess


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / ".git").exists() and (candidate / ".gitignore").is_file():
            return candidate
    raise AssertionError("repo root not found")


def _check_ignore(path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "check-ignore", "--no-index", "-v", path],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )


def _check_not_ignored(path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "check-ignore", path],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )


def test_gitignore_blocks_runtime_and_archive_assets():
    expected_rules = {
        "data/raw/example.json": "data/raw/",
        "data/test/example.json": "data/test/",
        "data/report.csv": "data/*.csv",
        "data/report.json": "data/*.json",
        "raw_offers_example.json": "raw_offers_*.json",
        "apps/api/data/raw/example.json": "apps/api/data/raw/",
        "apps/api/data/db/offers.db": "apps/api/data/db/",
        "apps/api/data/processed/backtests/result.json": "apps/api/data/processed/backtests/",
        "apps/api/data/semantic_retrieval/example.jsonl": "apps/api/data/semantic_retrieval/",
        "apps/api/data/sample_payload.json": "apps/api/data/sample_*.json",
        "tmp/runtime.sqlite": "*.sqlite",
        "tmp/runtime.db": "*.db",
    }

    for path, rule in expected_rules.items():
        result = _check_ignore(path)
        assert result.returncode == 0, f"expected ignored path: {path}\n{result.stderr}"
        assert rule in result.stdout, f"expected rule {rule} for {path}\n{result.stdout}"


def test_gitignore_keeps_skills_reference_tracked():
    repo_root = _repo_root()
    allow_rule = "!apps/api/data/esco/v1_2_1/fr/skills_fr.csv"

    text = (repo_root / ".gitignore").read_text()
    assert allow_rule in text

    result = _check_not_ignored("apps/api/data/esco/v1_2_1/fr/skills_fr.csv")
    assert result.returncode == 1, result.stdout
