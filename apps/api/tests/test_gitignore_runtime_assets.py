from pathlib import Path


def test_gitignore_blocks_runtime_and_archive_assets():
    text = Path(".gitignore").read_text()

    required_patterns = [
        "data/raw/",
        "data/test/",
        "apps/api/data/raw/",
        "apps/api/data/db/",
        "apps/api/data/db/backups/",
        "apps/api/data/semantic_retrieval/",
    ]

    for pattern in required_patterns:
        assert pattern in text, f"missing ignore rule: {pattern}"


def test_gitignore_keeps_skills_reference_tracked():
    text = Path(".gitignore").read_text()
    assert "!apps/api/data/esco/v1_2_1/fr/skills_fr.csv" in text
