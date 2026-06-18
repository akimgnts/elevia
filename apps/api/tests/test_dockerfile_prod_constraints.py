from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_staging_api_dockerfile_does_not_upgrade_pip():
    dockerfile = (ROOT / "deploy" / "staging" / "api.Dockerfile").read_text(encoding="utf-8")
    assert "pip install --upgrade pip" not in dockerfile


def test_api_dockerfile_does_not_upgrade_pip():
    dockerfile = (ROOT / "apps" / "api" / "Dockerfile").read_text(encoding="utf-8")
    assert "pip install --upgrade pip" not in dockerfile
