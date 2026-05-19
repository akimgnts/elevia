from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "scripts" / "generate_archetype_cvs.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("generate_archetype_cvs", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"unable to load module spec for {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_central_sector_config_contains_expected_five_sectors():
    module = _load_module()

    assert set(module.CENTRAL_SECTORS) == {
        "finance_controller",
        "hr_recruitment",
        "data_analytics",
        "software_engineering",
        "operations_process",
    }
    for archetype_name, config in module.CENTRAL_SECTORS.items():
        assert config["slug"], f"central archetype {archetype_name} must expose a non-empty slug"


def test_hybrid_sector_config_requires_minimum_offer_count_of_10():
    module = _load_module()

    assert set(module.HYBRID_SECTORS) == {
        "finance_bi",
        "hr_operations",
        "data_software",
        "operations_supply",
    }
    for sector_name, config in module.HYBRID_SECTORS.items():
        assert config["slug"] == sector_name, (
            f"hybrid sector {sector_name} must use a slug-style key that matches its slug"
        )
        assert config["min_offer_count"] >= 10, (
            f"hybrid sector {sector_name} must require min_offer_count >= 10"
        )


def test_output_path_helpers_split_markdown_and_json_into_central_and_hybrid():
    module = _load_module()
    output_root = Path("/tmp/archetype-cvs")

    central_markdown = module.build_markdown_output_path(
        output_root=output_root,
        sector_type="central",
        sector_slug="finance_control",
    )
    central_json = module.build_json_output_path(
        output_root=output_root,
        sector_type="central",
        sector_slug="finance_control",
    )
    hybrid_markdown = module.build_markdown_output_path(
        output_root=output_root,
        sector_type="hybrid",
        sector_slug="finance_bi",
    )
    hybrid_json = module.build_json_output_path(
        output_root=output_root,
        sector_type="hybrid",
        sector_slug="finance_bi",
    )

    assert central_markdown == output_root / "central" / "finance_control.md"
    assert central_json == output_root / "central" / "finance_control.json"
    assert hybrid_markdown == output_root / "hybrid" / "finance_bi.md"
    assert hybrid_json == output_root / "hybrid" / "finance_bi.json"


def test_output_path_helpers_fail_fast_for_misuse():
    module = _load_module()

    with pytest.raises(TypeError):
        module.build_markdown_output_path()

    with pytest.raises(ValueError, match="sector_slug"):
        module.build_json_output_path(
            output_root=Path("/tmp/archetype-cvs"),
            sector_type="central",
            sector_slug="",
        )

    with pytest.raises(ValueError, match="unsupported sector_type"):
        module.build_markdown_output_path(
            output_root=Path("/tmp/archetype-cvs"),
            sector_type="unsupported",
            sector_slug="finance_control",
        )
