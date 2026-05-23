from __future__ import annotations

import importlib.util
import json
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


def test_peripheral_selection_ignores_incidental_substring_keyword_collisions():
    module = _load_module()

    rows = [
        {
            "source": "business_france",
            "external_id": f"F-{index}",
            "title": f"Financial Controller {index}",
            "description": "Budget control and sap reporting.",
            "offer_domain_enrichment": {"domain_tag": "finance"},
            "offer_skills": [{"skill_label": "Budgeting"}, {"skill_label": "SAP"}],
        }
        for index in range(1, 8)
    ] + [
        {
            "source": "business_france",
            "external_id": "P-REAL-1",
            "title": "Operations Cost Analyst",
            "description": "Cost control for finance operations.",
            "offer_domain_enrichment": {"domain_tag": "operations"},
            "offer_skills": [{"skill_label": "Cost control"}],
        },
        {
            "source": "business_france",
            "external_id": "P-REAL-2",
            "title": "Operations SAP Coordinator",
            "description": "Sap migration support for finance operations.",
            "offer_domain_enrichment": {"domain_tag": "operations"},
            "offer_skills": [{"skill_label": "SAP"}],
        },
        {
            "source": "business_france",
            "external_id": "P-COLLIDE-1",
            "title": "Operations Planner",
            "description": "Costume handling and sapling reviews for operations.",
            "offer_domain_enrichment": {"domain_tag": "operations"},
            "offer_skills": [{"skill_label": "Planning"}],
        },
    ]

    offers = module.normalize_bf_offer_rows(rows)
    central = module.select_central_sector_offers(
        offers,
        sector_key="finance_controller",
        target_count=9,
    )
    peripheral = module.select_coherent_peripheral_offers(
        offers,
        sector_key="finance_controller",
        already_selected_offer_ids={entry["offer"]["offer_id"] for entry in central},
        target_count=9,
    )

    assert [entry["offer"]["offer_id"] for entry in peripheral] == [
        "business_france:P-REAL-1",
        "business_france:P-REAL-2",
    ]
    collide_entry = next(offer for offer in offers if offer["offer_id"] == "business_france:P-COLLIDE-1")
    collide_fit = module.compute_sector_fit(collide_entry, "finance_controller")
    assert collide_fit["matched_keywords"] == []


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
    side_fits = selected[0]["fit"]["side_fits"]
    assert side_fits[0] == {
        "side_key": "explicit_side_1",
        "side_kind": "explicit",
        "domain_hits": ["operations"],
        "matched_keywords": ["process", "operations", "planning"],
        "score": 12,
    }
    assert side_fits[1] == {
        "side_key": "explicit_side_2",
        "side_kind": "explicit",
        "domain_hits": ["supply"],
        "matched_keywords": ["supply", "logistics"],
        "score": 10,
    }


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


def test_explicit_side_hybrid_does_not_treat_substring_collisions_as_evidence():
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
            "external_id": "OS-COLLIDE-1",
            "title": "Operations Coordinator",
            "description": "Process improvement and complanning of routes.",
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
    assert "business_france:OS-COLLIDE-1" not in selected_ids


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


def test_component_hybrid_does_not_treat_incidental_combine_text_as_bi_evidence():
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
            "external_id": "FB-COMBINE-1",
            "title": "Finance Coordinator",
            "description": "Combine finance reporting, budget control and SAP follow-up.",
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
    assert "business_france:FB-COMBINE-1" not in selected_ids


def test_hybrid_side_fits_have_stable_shape_for_component_hybrids():
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
            "external_id": "FB-BOTH-10",
            "title": "Finance BI Specialist",
            "description": "Controlling, SQL and dashboard analytics.",
            "offer_domain_enrichment": {"domain_tags": ["finance", "data"]},
            "offer_skills": [{"skill_label": "Controlling"}, {"skill_label": "Dashboards"}],
        }
    ]

    offers = module.normalize_bf_offer_rows(rows)
    selected = module.select_hybrid_sector_offers(
        offers,
        sector_key="finance_bi",
        target_count=10,
    )

    entry_by_offer_id = {entry["offer"]["offer_id"]: entry for entry in selected}
    side_fits = entry_by_offer_id["business_france:FB-BOTH-1"]["fit"]["side_fits"]
    assert side_fits[0] == {
        "side_key": "finance_controller",
        "side_kind": "component",
        "domain_hits": ["finance"],
        "matched_keywords": ["budgeting", "controlling"],
        "score": 10,
        "source_sector_key": "finance_controller",
    }
    assert side_fits[1] == {
        "side_key": "data_analytics",
        "side_kind": "component",
        "domain_hits": ["data"],
        "matched_keywords": ["sql", "dashboards", "bi"],
        "score": 12,
        "source_sector_key": "data_analytics",
    }


def test_aggregate_skill_evidence_marks_high_dispersion_skills_as_generic():
    module = _load_module()

    selected_entries = [
        {
            "offer": {
                "offer_id": "business_france:1",
                "domain_tags": ["finance"],
                "skill_labels": ["excel"],
            }
        },
        {
            "offer": {
                "offer_id": "business_france:2",
                "domain_tags": ["data"],
                "skill_labels": ["excel"],
            }
        },
        {
            "offer": {
                "offer_id": "business_france:3",
                "domain_tags": ["operations"],
                "skill_labels": ["excel"],
            }
        },
    ]

    aggregated = module.aggregate_sector_skill_evidence(selected_entries)
    classified = module.classify_sector_skills(aggregated)

    assert classified["excel"]["classification"] == "GENERIC"
    assert classified["excel"]["domain_tags"] == ["data", "finance", "operations"]


def test_aggregate_skill_evidence_marks_dense_low_dispersion_skills_as_anchor():
    module = _load_module()

    selected_entries = [
        {
            "offer": {
                "offer_id": "business_france:1",
                "domain_tags": ["finance"],
                "skill_labels": ["budgeting", "sap"],
            }
        },
        {
            "offer": {
                "offer_id": "business_france:2",
                "domain_tags": ["finance"],
                "skill_labels": ["budgeting"],
            }
        },
        {
            "offer": {
                "offer_id": "business_france:3",
                "domain_tags": ["finance"],
                "skill_labels": ["budgeting"],
            }
        },
        {
            "offer": {
                "offer_id": "business_france:4",
                "domain_tags": ["finance"],
                "skill_labels": ["sap"],
            }
        },
    ]

    aggregated = module.aggregate_sector_skill_evidence(selected_entries)
    classified = module.classify_sector_skills(aggregated)

    assert classified["budgeting"]["classification"] == "ANCHOR"
    assert classified["budgeting"]["density"] == pytest.approx(0.75)


def test_allowlist_secures_validated_anchor_even_when_frequency_is_marginal():
    module = _load_module()

    selected_entries = [
        {
            "offer": {
                "offer_id": "business_france:1",
                "domain_tags": ["finance"],
                "skill_labels": ["internal control"],
            }
        },
        {
            "offer": {
                "offer_id": "business_france:2",
                "domain_tags": ["finance"],
                "skill_labels": ["budgeting"],
            }
        },
        {
            "offer": {
                "offer_id": "business_france:3",
                "domain_tags": ["finance"],
                "skill_labels": ["sap"],
            }
        },
        {
            "offer": {
                "offer_id": "business_france:4",
                "domain_tags": ["finance"],
                "skill_labels": ["forecasting"],
            }
        },
    ]

    aggregated = module.aggregate_sector_skill_evidence(selected_entries)
    classified = module.classify_sector_skills(aggregated)

    assert classified["internal control"]["classification"] == "ANCHOR"
    assert classified["internal control"]["is_allowlisted"] is True


def test_promotable_skills_exclude_evidenceless_skills():
    module = _load_module()

    classified = {
        "internal control": {
            "skill_label": "internal control",
            "classification": "ANCHOR",
            "offer_count": 1,
            "offer_ids": ["business_france:1"],
            "domain_tags": ["finance"],
            "density": 0.25,
            "domain_dispersion": 0.5,
            "evidence_count": 1,
            "is_allowlisted": True,
        },
        "ghost skill": {
            "skill_label": "ghost skill",
            "classification": "SUPPORT",
            "offer_count": 0,
            "offer_ids": [],
            "domain_tags": [],
            "density": 0.0,
            "domain_dispersion": 0.0,
            "evidence_count": 0,
            "is_allowlisted": False,
        },
        "excel": {
            "skill_label": "excel",
            "classification": "GENERIC",
            "offer_count": 3,
            "offer_ids": ["business_france:1", "business_france:2", "business_france:3"],
            "domain_tags": ["data", "finance", "operations"],
            "density": 1.0,
            "domain_dispersion": 1.0,
            "evidence_count": 3,
            "is_allowlisted": False,
        },
    }

    promotable = module.select_promotable_skill_evidence(classified)

    assert [item["skill_label"] for item in promotable] == ["internal control"]


def _make_render_selected_entries():
    return [
        {
            "offer": {
                "offer_id": "business_france:1",
                "title": "Financial Controller Analyst",
                "description": "budget control monthly reporting project delivery",
                "domain_tags": ["finance"],
                "skill_labels": ["internal control", "sap", "communication"],
            }
        },
        {
            "offer": {
                "offer_id": "business_france:2",
                "title": "Financial Controller Lead",
                "description": "budget control monthly reporting project delivery",
                "domain_tags": ["finance", "operations"],
                "skill_labels": ["financial analysis", "sap", "communication"],
            }
        },
        {
            "offer": {
                "offer_id": "business_france:3",
                "title": "Financial Controller Manager",
                "description": "project forecasting process improvement",
                "domain_tags": ["finance", "data"],
                "skill_labels": ["communication", "project coordination"],
            }
        },
        {
            "offer": {
                "offer_id": "business_france:4",
                "title": "Financial Controller Specialist",
                "description": "budget control project forecasting",
                "domain_tags": ["finance"],
                "skill_labels": ["internal control", "sql querying"],
            }
        },
    ]


def test_render_markdown_contains_all_required_sections():
    module = _load_module()

    selected_entries = _make_render_selected_entries()
    classified = module.classify_sector_skills(module.aggregate_sector_skill_evidence(selected_entries))
    artifact = module.build_archetype_render_artifact(
        sector_slug="finance_control",
        sector_type="central",
        selected_entries=selected_entries,
        classified_skill_evidence=classified,
    )

    markdown = artifact["markdown"]

    assert "## Orientation" in markdown
    assert "## Profile Summary" in markdown
    assert "## Experience Types" in markdown
    assert "## Project Types" in markdown
    assert "## Anchor Skills" in markdown
    assert "## Support Skills" in markdown
    assert "## Generic Skills To Limit" in markdown
    assert "## Tools / Technologies" in markdown
    assert "## Market Evidence" in markdown


def test_render_json_contains_coherent_structured_evidence():
    module = _load_module()

    selected_entries = _make_render_selected_entries()
    classified = module.classify_sector_skills(module.aggregate_sector_skill_evidence(selected_entries))
    artifact = module.build_archetype_render_artifact(
        sector_slug="finance_control",
        sector_type="central",
        selected_entries=selected_entries,
        classified_skill_evidence=classified,
    )

    payload = artifact["json"]

    assert payload["sector_slug"] == "finance_control"
    assert payload["sector_type"] == "central"
    assert payload["orientation"]["domain_tags"] == ["data", "finance", "operations"]
    assert payload["market_evidence"]["offer_count"] == 4
    assert payload["anchor_skills"] == [
        {
            "skill_label": "internal control",
            "classification": "ANCHOR",
            "offer_count": 2,
            "evidence_count": 2,
            "domain_tags": ["finance"],
        }
    ]
    assert payload["market_evidence"]["offer_ids"] == [
        "business_france:1",
        "business_france:2",
        "business_france:3",
        "business_france:4",
    ]


def test_missing_evidence_prevents_render_payload_creation():
    module = _load_module()

    selected_entries = [
        {
            "offer": {
                "offer_id": "business_france:1",
                "title": "Assistant",
                "description": "misc support",
                "domain_tags": ["finance"],
                "skill_labels": ["excel"],
            }
        }
    ]
    classified = module.classify_sector_skills(module.aggregate_sector_skill_evidence(selected_entries))

    with pytest.raises(ValueError, match="insufficient evidence"):
        module.build_archetype_render_artifact(
            sector_slug="finance_control",
            sector_type="central",
            selected_entries=selected_entries,
            classified_skill_evidence=classified,
        )


def test_render_payload_has_no_duplicate_skills_across_sections():
    module = _load_module()

    selected_entries = _make_render_selected_entries()
    classified = module.classify_sector_skills(module.aggregate_sector_skill_evidence(selected_entries))
    artifact = module.build_archetype_render_artifact(
        sector_slug="finance_control",
        sector_type="central",
        selected_entries=selected_entries,
        classified_skill_evidence=classified,
    )
    payload = artifact["json"]

    anchor = {item["skill_label"] for item in payload["anchor_skills"]}
    support = {item["skill_label"] for item in payload["support_skills"]}
    generic = {item["skill_label"] for item in payload["generic_skills_to_limit"]}
    tools = {item["skill_label"] for item in payload["tools_technologies"]}

    assert anchor.isdisjoint(support)
    assert anchor.isdisjoint(generic)
    assert anchor.isdisjoint(tools)
    assert support.isdisjoint(generic)
    assert support.isdisjoint(tools)
    assert generic.isdisjoint(tools)


def test_cli_quick_mode_writes_outputs_and_refuses_unproven_sectors(capsys, tmp_path):
    module = _load_module()

    exit_code = module.main(
        [
            "--mode",
            "quick",
            "--output-root",
            str(tmp_path),
        ]
    )

    assert exit_code == 0

    central_markdown = tmp_path / "central" / "finance_control.md"
    central_json = tmp_path / "central" / "finance_control.json"
    refused_hybrid = tmp_path / "hybrid" / "finance_bi.md"

    assert central_markdown.exists()
    assert central_json.exists()
    assert not refused_hybrid.exists()

    payload = json.loads(central_json.read_text())
    assert payload["sector_slug"] == "finance_control"

    captured = capsys.readouterr().out
    assert "central created: finance_control" in captured
    assert "hybrid refused:" in captured


def test_cli_auto_mode_can_select_pg_after_loading_repo_env(monkeypatch, tmp_path):
    module = _load_module()
    calls: dict[str, object] = {}

    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=postgresql://example/db\n")

    def fake_load_rows(database_url: str):
        calls["database_url"] = database_url
        return module.load_quick_mode_offer_rows()

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(module, "API_ENV_PATH", env_file)
    monkeypatch.setattr(module, "load_business_france_offer_rows_from_postgres", fake_load_rows)

    exit_code = module.main(
        [
            "--mode",
            "auto",
            "--output-root",
            str(tmp_path / "out"),
        ]
    )

    assert exit_code == 0
    assert calls["database_url"] == "postgresql://example/db"
