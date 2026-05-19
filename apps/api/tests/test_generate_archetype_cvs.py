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


def test_hybrid_sector_config_requires_minimum_offer_count_of_10_and_real_two_sided_definition():
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
        components = config.get("components", ())
        explicit_sides = config.get("explicit_sides", ())
        if components:
            assert len(components) == 2, (
                f"hybrid sector {sector_name} must define exactly two components when using components"
            )
        else:
            assert len(explicit_sides) == 2, (
                f"hybrid sector {sector_name} must define exactly two explicit sides"
            )
            for side in explicit_sides:
                assert side["domains"], (
                    f"hybrid sector {sector_name} explicit sides must declare non-empty domains"
                )
                assert side["keywords"], (
                    f"hybrid sector {sector_name} explicit sides must declare non-empty keywords"
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


def test_normalize_bf_offer_rows_extracts_domains_skills_and_text():
    module = _load_module()

    rows = [
        {
            "source": "business_france",
            "external_id": "BF-001",
            "title": "Financial Controller",
            "description": "Budget control, forecasting and SAP reporting.",
            "offer_domain_enrichment": {
                "domain_tag": "finance",
                "domain_tags": ["finance", "operations"],
            },
            "offer_skills": [
                {"skill_label": "Budgeting", "skill_uri": "skill:budgeting"},
                {"skill_label": "SAP", "skill_uri": "skill:sap"},
            ],
        }
    ]

    normalized = module.normalize_bf_offer_rows(rows)

    assert normalized == [
        {
            "source": "business_france",
            "external_id": "BF-001",
            "offer_id": "business_france:BF-001",
            "title": "Financial Controller",
            "description": "Budget control, forecasting and SAP reporting.",
            "text": "financial controller budget control forecasting and sap reporting",
            "domain_tags": ["finance", "operations"],
            "skill_labels": ["budgeting", "sap"],
            "skill_uris": ["skill:budgeting", "skill:sap"],
        }
    ]


def test_central_selection_keeps_80_percent_central_and_20_percent_coherent_peripheral():
    module = _load_module()

    rows = [
        {
            "source": "business_france",
            "external_id": f"F-{index}",
            "title": f"Financial Controller {index}",
            "description": "Budget control, forecasting, reporting and SAP.",
            "offer_domain_enrichment": {"domain_tag": "finance"},
            "offer_skills": [{"skill_label": "Budgeting"}, {"skill_label": "SAP"}],
        }
        for index in range(1, 9)
    ] + [
        {
            "source": "business_france",
            "external_id": "P-1",
            "title": "BI Analyst Finance",
            "description": "Dashboards, SQL reporting and finance KPIs.",
            "offer_domain_enrichment": {"domain_tag": "data"},
            "offer_skills": [{"skill_label": "SQL"}, {"skill_label": "Reporting"}],
        },
        {
            "source": "business_france",
            "external_id": "P-2",
            "title": "Operations Cost Analyst",
            "description": "Cost control, process reporting and budget follow-up.",
            "offer_domain_enrichment": {"domain_tag": "operations"},
            "offer_skills": [{"skill_label": "Cost control"}, {"skill_label": "Reporting"}],
        },
        {
            "source": "business_france",
            "external_id": "X-1",
            "title": "Recruiter",
            "description": "Talent sourcing and interviews.",
            "offer_domain_enrichment": {"domain_tag": "hr"},
            "offer_skills": [{"skill_label": "Recruitment"}],
        },
    ]

    offers = module.normalize_bf_offer_rows(rows)
    central = module.select_central_sector_offers(
        offers,
        sector_key="finance_controller",
        target_count=10,
    )
    selected_ids = {entry["offer"]["offer_id"] for entry in central}
    peripheral = module.select_coherent_peripheral_offers(
        offers,
        sector_key="finance_controller",
        already_selected_offer_ids=selected_ids,
        target_count=10,
    )

    assert [entry["offer"]["offer_id"] for entry in central] == [
        "business_france:F-1",
        "business_france:F-2",
        "business_france:F-3",
        "business_france:F-4",
        "business_france:F-5",
        "business_france:F-6",
        "business_france:F-7",
        "business_france:F-8",
    ]
    assert {entry["offer"]["offer_id"] for entry in peripheral} == {
        "business_france:P-1",
        "business_france:P-2",
    }
    assert central[0]["fit"]["central_domain_hits"] == ["finance"]
    assert "budget" in central[0]["fit"]["matched_keywords"]
    assert peripheral[0]["fit"]["peripheral_domain_hits"]
    assert len(central) == 8
    assert len(peripheral) == 2


def test_hybrid_selection_refuses_when_offer_count_is_below_minimum_threshold():
    module = _load_module()

    rows = [
        {
            "source": "business_france",
            "external_id": f"FB-{index}",
            "title": f"Finance BI {index}",
            "description": "Finance reporting, dashboards, SQL and controlling.",
            "offer_domain_enrichment": {"domain_tags": ["finance", "data"]},
            "offer_skills": [{"skill_label": "SQL"}, {"skill_label": "Budgeting"}],
        }
        for index in range(1, 10)
    ]

    offers = module.normalize_bf_offer_rows(rows)

    with pytest.raises(ValueError, match="requires at least 10 offers"):
        module.select_hybrid_sector_offers(
            offers,
            sector_key="finance_bi",
            target_count=10,
        )


def test_hybrid_selection_requires_both_sides_of_the_hybrid_to_contribute_evidence():
    module = _load_module()

    rows = [
        {
            "source": "business_france",
            "external_id": f"OS-BOTH-{index}",
            "title": f"Operations Supply Planner {index}",
            "description": "Supply planning, logistics coordination and process improvement.",
            "offer_domain_enrichment": {"domain_tags": ["operations", "supply"]},
            "offer_skills": [{"skill_label": "Supply planning"}, {"skill_label": "Process improvement"}],
        }
        for index in range(1, 5)
    ] + [
        {
            "source": "business_france",
            "external_id": f"OS-OPS-{index}",
            "title": f"Operations Coordinator {index}",
            "description": "Process improvement, operations reporting and lean execution.",
            "offer_domain_enrichment": {"domain_tags": ["operations"]},
            "offer_skills": [{"skill_label": "Lean"}, {"skill_label": "Process improvement"}],
        }
        for index in range(1, 4)
    ] + [
        {
            "source": "business_france",
            "external_id": f"OS-SUP-{index}",
            "title": f"Supply Planner {index}",
            "description": "Supply planning, inventory flow and logistics execution.",
            "offer_domain_enrichment": {"domain_tags": ["supply"]},
            "offer_skills": [{"skill_label": "Supply planning"}, {"skill_label": "Logistics"}],
        }
        for index in range(1, 4)
    ]

    offers = module.normalize_bf_offer_rows(rows)
    selected = module.select_hybrid_sector_offers(
        offers,
        sector_key="operations_supply",
        target_count=10,
    )

    assert [entry["offer"]["offer_id"] for entry in selected] == [
        "business_france:OS-BOTH-1",
        "business_france:OS-BOTH-2",
        "business_france:OS-BOTH-3",
        "business_france:OS-BOTH-4",
    ]
    assert selected[0]["fit"]["side_fits"][0]["matched_keywords"]
    assert selected[0]["fit"]["side_fits"][1]["matched_keywords"]


def test_explicit_side_hybrid_rejects_dual_tag_offer_without_second_side_real_evidence():
    module = _load_module()

    rows = [
        {
            "source": "business_france",
            "external_id": f"OS-BOTH-{index}",
            "title": f"Operations Supply Planner {index}",
            "description": "Supply planning, logistics coordination and process improvement.",
            "offer_domain_enrichment": {"domain_tags": ["operations", "supply"]},
            "offer_skills": [{"skill_label": "Supply planning"}, {"skill_label": "Process improvement"}],
        }
        for index in range(1, 10)
    ] + [
        {
            "source": "business_france",
            "external_id": "OS-PSEUDO-1",
            "title": "Operations Planner",
            "description": "Process improvement, lean planning and operations reporting.",
            "offer_domain_enrichment": {"domain_tags": ["operations", "supply"]},
            "offer_skills": [{"skill_label": "Lean"}, {"skill_label": "Process improvement"}],
        }
    ]

    offers = module.normalize_bf_offer_rows(rows)
    selected = module.select_hybrid_sector_offers(
        offers,
        sector_key="operations_supply",
        target_count=10,
    )

    selected_ids = [entry["offer"]["offer_id"] for entry in selected]
    assert "business_france:OS-PSEUDO-1" not in selected_ids


def test_component_hybrid_rejects_dual_tag_offer_without_second_side_real_evidence():
    module = _load_module()

    rows = [
        {
            "source": "business_france",
            "external_id": f"FB-BOTH-{index}",
            "title": f"Finance BI Analyst {index}",
            "description": "Finance reporting, SQL dashboards and controlling KPIs.",
            "offer_domain_enrichment": {"domain_tags": ["finance", "data"]},
            "offer_skills": [{"skill_label": "Budgeting"}, {"skill_label": "SQL"}],
        }
        for index in range(1, 10)
    ] + [
        {
            "source": "business_france",
            "external_id": "FB-PSEUDO-1",
            "title": "Finance Controller",
            "description": "Budget control, forecasting, SAP reporting and cost follow-up.",
            "offer_domain_enrichment": {"domain_tags": ["finance", "data"]},
            "offer_skills": [{"skill_label": "Budgeting"}, {"skill_label": "SAP"}],
        }
    ]

    offers = module.normalize_bf_offer_rows(rows)
    selected = module.select_hybrid_sector_offers(
        offers,
        sector_key="finance_bi",
        target_count=10,
    )

    selected_ids = [entry["offer"]["offer_id"] for entry in selected]
    assert "business_france:FB-PSEUDO-1" not in selected_ids
