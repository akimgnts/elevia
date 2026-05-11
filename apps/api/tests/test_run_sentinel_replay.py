from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SRC_ROOT = REPO_ROOT / "src"
PROJECT_ROOT = REPO_ROOT.parent.parent
sys.path.insert(0, str(SRC_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_sentinel_replay


def test_load_sentinel_panel_reads_ids(tmp_path):
    panel_path = tmp_path / "sentinel_panel.json"
    panel_path.write_text(
        json.dumps(
            {
                "version": "v1",
                "sentinels": [
                    {"id": "nawel", "cv_path": "/tmp/nawel.pdf", "expected_orientation": "hr_ops"},
                    {"id": "ania", "cv_path": "/tmp/ania.pdf", "expected_orientation": "finance_compliance"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    panel = run_sentinel_replay.load_sentinel_panel(panel_path)

    assert [item["id"] for item in panel] == ["nawel", "ania"]


def test_load_sentinel_panel_inherits_panel_cv_root_env_when_override_is_empty(tmp_path):
    panel_path = tmp_path / "sentinel_panel.json"
    panel_path.write_text(
        json.dumps(
            {
                "version": "v1",
                "cv_root_env": "PANEL_ROOT",
                "sentinels": [
                    {"id": "nawel", "cv_relative_path": "nawel.pdf", "cv_root_env": ""},
                    {"id": "ania", "cv_relative_path": "ania.pdf"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    panel = run_sentinel_replay.load_sentinel_panel(panel_path)

    assert panel[0]["cv_root_env"] == "PANEL_ROOT"
    assert panel[1]["cv_root_env"] == "PANEL_ROOT"


def test_resolve_cv_path_uses_sentinel_override_over_panel_default(tmp_path):
    panel_path = tmp_path / "sentinel_panel.json"
    panel_path.write_text(
        json.dumps(
            {
                "version": "v1",
                "cv_root_env": "PANEL_ROOT",
                "sentinels": [
                    {
                        "id": "nawel",
                        "cv_relative_path": "nested/nawel.pdf",
                        "cv_root_env": "SENTINEL_ROOT",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    panel = run_sentinel_replay.load_sentinel_panel(panel_path)

    expected_root = tmp_path / "sentinel-root"
    monkey_env = {"PANEL_ROOT": str(tmp_path / "panel-root"), "SENTINEL_ROOT": str(expected_root)}
    original = {key: run_sentinel_replay.os.environ.get(key) for key in monkey_env}
    try:
        run_sentinel_replay.os.environ.update(monkey_env)
        resolved = run_sentinel_replay._resolve_cv_path(panel[0])
    finally:
        for key, value in original.items():
            if value is None:
                run_sentinel_replay.os.environ.pop(key, None)
            else:
                run_sentinel_replay.os.environ[key] = value

    assert resolved == expected_root / "nested/nawel.pdf"


def test_resolve_cv_path_falls_back_to_default_env_name(tmp_path):
    sentinel = {"id": "nawel", "cv_relative_path": "nawel.pdf"}
    expected_root = tmp_path / "default-root"
    original = run_sentinel_replay.os.environ.get("ELEVIA_SENTINEL_CV_ROOT")
    try:
        run_sentinel_replay.os.environ["ELEVIA_SENTINEL_CV_ROOT"] = str(expected_root)
        resolved = run_sentinel_replay._resolve_cv_path(sentinel)
    finally:
        if original is None:
            run_sentinel_replay.os.environ.pop("ELEVIA_SENTINEL_CV_ROOT", None)
        else:
            run_sentinel_replay.os.environ["ELEVIA_SENTINEL_CV_ROOT"] = original

    assert resolved == expected_root / "nawel.pdf"


def test_summarize_top_items_counts_verdict_buckets():
    summary = run_sentinel_replay.summarize_top_items(
        sentinel={"id": "nawel"},
        items=[
            {"title": "Recruiter", "score": 100},
            {"title": "Talent Acquisition", "score": 95},
            {"title": "Plant Engineer", "score": 70},
        ],
        human_verdict="discutable",
        notes=["third offer is out of domain"],
    )

    assert summary["sentinel_id"] == "nawel"
    assert summary["top_count"] == 3
    assert summary["human_verdict"] == "discutable"
    assert summary["notes"] == ["third offer is out of domain"]


def test_render_markdown_report_includes_verdict_and_titles():
    report = run_sentinel_replay.render_markdown_report(
        [
            {
                "sentinel_id": "ania",
                "human_verdict": "mauvais",
                "top_count": 2,
                "items": [
                    {"title": "Privacy Analyst", "score": 66},
                    {"title": "Junior Business Controller", "score": 65},
                ],
                "notes": ["finance still drifts to policy"],
            }
        ]
    )

    assert "# Sentinel Replay Report" in report
    assert "ania" in report
    assert "mauvais" in report
    assert "Privacy Analyst" in report


def test_replay_single_sentinel_uses_existing_runtime_flow(monkeypatch, tmp_path):
    pdf_path = tmp_path / "nawel.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = json.dumps(payload)

        def json(self):
            return self._payload

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, path, **kwargs):
            if path == "/profile/parse-file":
                return FakeResponse(
                    200,
                    {
                        "profile_id": "profile-123",
                        "extraction_source": "structured_ai",
                        "profile": {"career_profile": {"role_detected": "hr_ops"}},
                    },
                )
            if path == "/inbox":
                return FakeResponse(
                    200,
                    {
                        "items": [
                            {"offer_id": "1", "title": "Recruiter", "score": 100},
                            {"offer_id": "2", "title": "Process Engineer", "score": 70},
                        ]
                    },
                )
            raise AssertionError(path)

    monkeypatch.setattr(run_sentinel_replay, "TestClient", lambda app: FakeClient())
    monkeypatch.setattr(run_sentinel_replay, "app", object())

    result = run_sentinel_replay.replay_single_sentinel(
        {
            "id": "nawel",
            "display_name": "Nawel",
            "cv_path": str(pdf_path),
        }
    )

    assert result["sentinel_id"] == "nawel"
    assert result["profile_id"] == "profile-123"
    assert result["extraction_source"] == "structured_ai"
    assert len(result["items"]) == 2
