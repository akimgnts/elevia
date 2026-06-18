from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "scripts" / "export_skillmap_snapshot.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("export_skillmap_snapshot", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"unable to load module spec for {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_export_metadata_tracks_source_and_counts():
    module = _load_module()

    metadata = module.build_export_metadata(
        source="skillmap_snapshot",
        version="v1",
        total_source_rows=903,
        exported_rows=400,
    )

    assert metadata["source"] == "skillmap_snapshot"
    assert metadata["version"] == "v1"
    assert metadata["total_source_rows"] == 903
    assert metadata["exported_rows"] == 400
    assert metadata["generated_at"]


def test_build_offer_export_item_keeps_domain_confidence_and_top_skills():
    module = _load_module()

    item = module.build_offer_export_item(
        {
            "offer_id": "242560",
            "external_id": "242560",
            "title": "Data Scientist",
            "company": "Example",
            "country": "FRANCE",
            "domain": "data",
            "domain_confidence": 0.9,
            "contract_type": "VIE",
            "published_at": "2026-04-24T00:00:00Z",
            "source": "business_france",
            "skills": ["python", "sql", "dashboards"],
        }
    )

    assert item["offer_id"] == "242560"
    assert item["domain"] == "data"
    assert item["domain_confidence"] == 0.9
    assert item["top_skills"] == ["python", "sql", "dashboards"]
    assert item["skill_count"] == 3


def test_build_skills_export_includes_sample_offer_minimum_shape_and_related_skills():
    module = _load_module()

    offers = [
        {
            "offer_id": "1",
            "title": "Financial Controller",
            "company": "A",
            "domain": "finance",
            "country": "FRANCE",
            "skills": ["financial analysis", "sap", "budgeting"],
        },
        {
            "offer_id": "2",
            "title": "FP&A Analyst",
            "company": "B",
            "domain": "finance",
            "country": "GERMANY",
            "skills": ["financial analysis", "sap", "forecasting"],
        },
    ]

    items = module.build_skills_export(
        offers,
        max_skills=50,
        generic_skill_labels={"sap"},
    )

    financial_analysis = next(item for item in items if item["label"] == "financial analysis")
    assert financial_analysis["frequency"] == 2
    assert financial_analysis["domains"] == ["finance"]
    assert financial_analysis["sample_offers"][0] == {
        "offer_id": "1",
        "title": "Financial Controller",
        "company": "A",
        "domain": "finance",
    }
    assert all(related["label"] != "sap" for related in financial_analysis["related_skills"])


def test_build_synthetic_items_adds_synthetic_flag_and_evidence_refs():
    module = _load_module()

    workflows = module.build_workflows_export(
        offers=[
            {
                "offer_id": "1",
                "domain": "finance",
                "title": "Financial Controller",
                "top_skills": ["financial analysis", "budgeting"],
            }
        ],
        domains=["finance"],
        top_skills=["financial analysis"],
    )

    assert workflows
    assert workflows[0]["synthetic"] is True
    assert workflows[0]["evidence_refs"]


def test_build_skills_export_can_read_exported_offer_shape_with_top_skills_only():
    module = _load_module()

    offers = [
        {
            "offer_id": "1",
            "title": "Financial Controller",
            "company": "A",
            "domain": "finance",
            "top_skills": ["financial analysis", "budgeting"],
        },
        {
            "offer_id": "2",
            "title": "FP&A Analyst",
            "company": "B",
            "domain": "finance",
            "top_skills": ["financial analysis", "forecasting"],
        },
    ]

    items = module.build_skills_export(
        offers,
        max_skills=50,
        generic_skill_labels=set(),
    )

    financial_analysis = next(item for item in items if item["label"] == "financial analysis")
    assert financial_analysis["frequency"] == 2
