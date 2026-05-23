from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "scripts" / "run_archetype_replay.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_archetype_replay", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"unable to load module spec for {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_archetype_dir_points_to_central_json_artifacts():
    module = _load_module()

    assert module.DEFAULT_ARCHETYPE_DIR == (
        REPO_ROOT / "docs" / "ai" / "runtime_calibration" / "archetype_cvs" / "central"
    )


def test_default_output_path_points_to_latest_archetype_replay_report():
    module = _load_module()

    assert module.DEFAULT_OUTPUT_PATH == (
        REPO_ROOT / "docs" / "ai" / "runtime_calibration" / "latest_archetype_replay.md"
    )


def test_loader_reads_json_files_only_and_ignores_markdown(tmp_path):
    module = _load_module()

    (tmp_path / "finance_control.json").write_text(json.dumps({"sector_slug": "finance_control"}))
    (tmp_path / "finance_control.md").write_text("# ignored")
    (tmp_path / "hr_recruitment.json").write_text(json.dumps({"sector_slug": "hr_recruitment"}))

    payloads = module.load_archetype_json_files(tmp_path)

    assert payloads == [
        {"sector_slug": "finance_control"},
        {"sector_slug": "hr_recruitment"},
    ]


def test_extract_runtime_skill_labels_uses_only_anchor_support_and_tools():
    module = _load_module()

    payload = {
        "sector_slug": "finance_control",
        "anchor_skills": [
            {"skill_label": "internal control"},
            {"skill_label": "financial analysis"},
        ],
        "support_skills": [
            {"skill_label": "stakeholder communication"},
        ],
        "tools_technologies": [
            {"skill_label": "sap"},
            {"skill_label": "sql querying"},
        ],
        "generic_skills_to_limit": [
            {"skill_label": "excel"},
        ],
    }

    labels = module.extract_runtime_skill_labels(payload)

    assert labels == [
        "internal control",
        "financial analysis",
        "stakeholder communication",
        "sap",
        "sql querying",
    ]


def test_build_runtime_profile_from_archetype_uses_only_allowed_sections():
    module = _load_module()

    payload = {
        "sector_slug": "finance_control",
        "orientation": {
            "domain_tags": ["finance", "operations"],
            "offer_count": 12,
        },
        "profile_summary": [
            {"label": "financial", "evidence_count": 8},
            {"label": "controller", "evidence_count": 8},
        ],
        "anchor_skills": [
            {"skill_label": "internal control"},
        ],
        "support_skills": [
            {"skill_label": "stakeholder communication"},
        ],
        "tools_technologies": [
            {"skill_label": "sap"},
        ],
        "education": ["ignored"],
        "certifications": ["ignored"],
        "years_experience": 7,
        "employment_history": ["ignored"],
    }

    runtime_profile = module.build_runtime_profile_from_archetype(payload)

    assert runtime_profile == {
        "profile_id": "archetype:finance_control",
        "profile_name": "archetype:finance_control",
        "sector_slug": "finance_control",
        "orientation": {
            "domain_tags": ["finance", "operations"],
            "offer_count": 12,
        },
        "profile_summary": ["financial", "controller"],
        "skill_labels": [
            "internal control",
            "stakeholder communication",
            "sap",
        ],
        "skills": [
            "internal control",
            "stakeholder communication",
            "sap",
        ],
        "matching_skills": [
            "internal control",
            "stakeholder communication",
            "sap",
        ],
    }
    assert "education" not in runtime_profile
    assert "certifications" not in runtime_profile
    assert "years_experience" not in runtime_profile
    assert "employment_history" not in runtime_profile


def test_build_runtime_profile_from_archetype_emits_deduplicated_runtime_skill_fields():
    module = _load_module()

    payload = {
        "sector_slug": "finance_control",
        "orientation": {
            "domain_tags": ["finance", "operations"],
            "offer_count": 12,
        },
        "profile_summary": [
            {"label": "financial", "evidence_count": 8},
        ],
        "anchor_skills": [
            {"skill_label": "internal control"},
            {"skill_label": "sap"},
        ],
        "support_skills": [
            {"skill_label": "sap"},
            {"skill_label": "stakeholder communication"},
        ],
        "tools_technologies": [
            {"skill_label": "sap"},
            {"skill_label": "sql querying"},
        ],
        "generic_skills_to_limit": [
            {"skill_label": "excel"},
        ],
        "education": ["ignored"],
    }

    runtime_profile = module.build_runtime_profile_from_archetype(payload)

    assert runtime_profile["skill_labels"] == [
        "internal control",
        "sap",
        "sap",
        "stakeholder communication",
        "sap",
        "sql querying",
    ]
    assert runtime_profile["skills"] == [
        "internal control",
        "sap",
        "stakeholder communication",
        "sql querying",
    ]
    assert runtime_profile["matching_skills"] == runtime_profile["skills"]
    assert "excel" not in runtime_profile["skills"]
    assert "education" not in runtime_profile


def test_summarize_archetype_top_items_defaults_verdict_to_pending():
    module = _load_module()

    summary = module.summarize_archetype_top_items(
        archetype_payload={"sector_slug": "finance_control"},
        items=[
            {"title": "Financial Controller", "score": 88, "offer_id": "bf-1"},
            {"title": "FP&A Analyst", "score": 84, "offer_id": "bf-2"},
        ],
    )

    assert summary["sector_slug"] == "finance_control"
    assert summary["verdict"] == "pending"
    assert summary["items"] == [
        {"offer_id": "bf-1", "title": "Financial Controller", "score": 88},
        {"offer_id": "bf-2", "title": "FP&A Analyst", "score": 84},
    ]


def test_render_archetype_markdown_report_has_one_section_per_slug_and_distinct_observed_interpreted():
    module = _load_module()

    report = module.render_archetype_markdown_report(
        [
            {
                "sector_slug": "finance_control",
                "verdict": "pending",
                "items": [
                    {"offer_id": "bf-1", "title": "Financial Controller", "score": 88},
                    {"offer_id": "bf-2", "title": "FP&A Analyst", "score": 84},
                ],
            },
            {
                "sector_slug": "hr_recruitment",
                "verdict": "pending",
                "items": [
                    {"offer_id": "bf-3", "title": "Talent Acquisition Specialist", "score": 81},
                ],
            },
        ]
    )

    assert "## finance_control" in report
    assert "## hr_recruitment" in report
    assert "### Observed" in report
    assert "### Interpreted" in report
    assert "- Verdict: `pending`" in report
    assert "- `88` - Financial Controller" in report
    assert "- `81` - Talent Acquisition Specialist" in report


def test_cli_main_writes_central_only_report(tmp_path, monkeypatch):
    module = _load_module()
    output_path = tmp_path / "latest_archetype_replay.md"
    central_payloads = [
        {"sector_slug": "finance_control"},
        {"sector_slug": "hr_recruitment"},
    ]

    monkeypatch.setattr(module, "load_env", lambda: None)
    monkeypatch.setattr(module, "load_archetype_json_files", lambda input_dir=None: list(central_payloads))
    monkeypatch.setattr(
        module,
        "replay_single_archetype",
        lambda payload, limit=10: {
            "sector_slug": payload["sector_slug"],
            "items": [
                {
                    "offer_id": f"{payload['sector_slug']}-1",
                    "title": f"{payload['sector_slug']} title",
                    "score": 77,
                }
            ],
        },
    )

    exit_code = module.main(["--output", str(output_path), "--limit", "5"])

    assert exit_code == 0
    report = output_path.read_text(encoding="utf-8")
    assert "## finance_control" in report
    assert "## hr_recruitment" in report
    assert "hybrid" not in report.lower()
