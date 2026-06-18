from pathlib import Path


API_DIR = Path(__file__).resolve().parents[1]


def _read_requirements(name: str) -> list[str]:
    path = API_DIR / name
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_prod_requirements_exclude_heavy_optional_packages():
    requirements = _read_requirements("requirements.txt")

    heavy_prefixes = (
        "jupyter",
        "ipykernel",
        "notebook",
        "matplotlib",
        "seaborn",
        "sentence-transformers",
        "torch",
    )

    for requirement in requirements:
        normalized = requirement.lower()
        assert not normalized.startswith(heavy_prefixes), requirement


def test_optional_dependency_sets_are_split_out():
    ml_requirements = _read_requirements("requirements-ml.txt")
    notebook_requirements = _read_requirements("requirements-notebook.txt")

    assert any(req.lower().startswith("sentence-transformers") for req in ml_requirements)
    assert any(req.lower().startswith("jupyter") for req in notebook_requirements)
