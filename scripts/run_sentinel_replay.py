#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from fastapi.testclient import TestClient

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
API_SRC = REPO_ROOT / "apps" / "api" / "src"
API_APP = REPO_ROOT / "apps" / "api"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))
if str(API_APP) not in sys.path:
    sys.path.insert(0, str(API_APP))
_venv_site_packages = sorted((REPO_ROOT / "apps" / "api" / ".venv" / "lib").glob("python*/site-packages"))
if _venv_site_packages:
    sys.path.insert(0, str(_venv_site_packages[0]))


DEFAULT_PANEL_PATH = Path("docs/ai/runtime_calibration/sentinel_panel.json")
DEFAULT_OUTPUT_PATH = Path("docs/ai/runtime_calibration/latest_sentinel_replay.md")
app: Any | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env() -> None:
    env_path = REPO_ROOT / "apps" / "api" / ".env"
    if not env_path.exists():
        return
    for key, value in dotenv_values(env_path).items():
        if value is not None and key not in os.environ:
            os.environ[key] = value


def load_sentinel_panel(panel_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(panel_path.read_text(encoding="utf-8"))
    sentinels = payload.get("sentinels") or []
    if not isinstance(sentinels, list):
        raise ValueError("sentinel_panel.json must contain a list under 'sentinels'")
    panel_cv_root_env = str(payload.get("cv_root_env") or "").strip()
    normalized: list[dict[str, Any]] = []
    for item in sentinels:
        if not isinstance(item, dict):
            raise ValueError("Each sentinel entry must be an object")
        sentinel = dict(item)
        sentinel_cv_root_env = str(sentinel.get("cv_root_env") or "").strip()
        if sentinel_cv_root_env:
            sentinel["cv_root_env"] = sentinel_cv_root_env
        elif panel_cv_root_env:
            sentinel["cv_root_env"] = panel_cv_root_env
        normalized.append(sentinel)
    return normalized


def _get_app() -> Any:
    global app
    if app is None:
        app = importlib.import_module("api.main").app
    return app


def _resolve_cv_path(sentinel: dict[str, Any]) -> Path:
    legacy_cv_path = str(sentinel.get("cv_path") or "").strip()
    if legacy_cv_path:
        return Path(legacy_cv_path).expanduser()

    cv_relative_path = str(sentinel.get("cv_relative_path") or "").strip()
    if not cv_relative_path:
        raise FileNotFoundError("Missing CV path: expected cv_path or cv_relative_path")

    root_env_name = str(sentinel.get("cv_root_env") or "").strip() or "ELEVIA_SENTINEL_CV_ROOT"
    cv_root = str(os.getenv(root_env_name) or "").strip()
    if not cv_root:
        raise FileNotFoundError(f"Missing CV root env: {root_env_name}")
    return Path(cv_root).expanduser() / cv_relative_path


def replay_single_sentinel(sentinel: dict[str, Any], *, limit: int = 10) -> dict[str, Any]:
    cv_path = _resolve_cv_path(sentinel)
    if not cv_path.exists():
        raise FileNotFoundError(f"Missing CV file: {cv_path}")

    with TestClient(_get_app()) as client:
        with cv_path.open("rb") as fh:
            parse_response = client.post(
                "/profile/parse-file",
                files={"file": (cv_path.name, fh, "application/pdf")},
            )
        if parse_response.status_code != 200:
            raise RuntimeError(f"/profile/parse-file failed: {parse_response.status_code} {parse_response.text}")
        parse_payload = parse_response.json()
        profile_id = str(parse_payload.get("profile_id") or "").strip()
        if not profile_id:
            raise RuntimeError("parse-file response missing profile_id")

        inbox_response = client.post(
            "/inbox",
            json={
                "profile_id": profile_id,
                "profile": {},
                "limit": limit,
                "min_score": 0,
            },
        )
        if inbox_response.status_code != 200:
            raise RuntimeError(f"/inbox failed: {inbox_response.status_code} {inbox_response.text}")
        inbox_payload = inbox_response.json()

    return {
        "sentinel_id": str(sentinel.get("id") or ""),
        "display_name": str(sentinel.get("display_name") or sentinel.get("id") or ""),
        "profile_id": profile_id,
        "extraction_source": parse_payload.get("extraction_source"),
        "role_detected": ((parse_payload.get("profile") or {}).get("career_profile") or {}).get("role_detected"),
        "items": list(inbox_payload.get("items") or []),
        "replayed_at": _utc_now(),
    }


def summarize_top_items(
    *,
    sentinel: dict[str, Any],
    items: list[dict[str, Any]],
    human_verdict: str = "pending",
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "sentinel_id": str(sentinel.get("id") or ""),
        "display_name": str(sentinel.get("display_name") or sentinel.get("id") or ""),
        "human_verdict": human_verdict,
        "top_count": len(items),
        "notes": list(notes or []),
        "items": [
            {
                "offer_id": item.get("offer_id"),
                "title": item.get("title"),
                "score": item.get("score"),
            }
            for item in items
        ],
    }


def render_markdown_report(summaries: list[dict[str, Any]]) -> str:
    lines = ["# Sentinel Replay Report", "", f"Generated: {_utc_now()}", ""]
    for summary in summaries:
        lines.append(f"## {summary['sentinel_id']}")
        lines.append(f"- Verdict: `{summary['human_verdict']}`")
        lines.append(f"- Top items: `{summary['top_count']}`")
        if summary.get("notes"):
            lines.append(f"- Notes: {'; '.join(summary['notes'])}")
        lines.append("")
        for item in summary.get("items", []):
            lines.append(f"- `{item.get('score')}` - {item.get('title')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", default=str(DEFAULT_PANEL_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    load_env()
    panel = load_sentinel_panel(Path(args.panel))
    active_panel = [item for item in panel if item.get("active", True)]
    results = [replay_single_sentinel(item, limit=args.limit) for item in active_panel]
    summaries = [
        summarize_top_items(sentinel=item, items=result["items"])
        for item, result in zip(active_panel, results, strict=False)
    ]
    report = render_markdown_report(summaries)
    Path(args.output).write_text(report, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
