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
