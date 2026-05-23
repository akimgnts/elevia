from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import sys
from typing import Any

from dotenv import dotenv_values
from fastapi.testclient import TestClient


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[1]
API_SRC = REPO_ROOT / "apps" / "api" / "src"
API_APP = REPO_ROOT / "apps" / "api"
if str(API_SRC) not in sys.path:
    sys.path.insert(0, str(API_SRC))
if str(API_APP) not in sys.path:
    sys.path.insert(0, str(API_APP))
_venv_site_packages = sorted((REPO_ROOT / "apps" / "api" / ".venv" / "lib").glob("python*/site-packages"))
if _venv_site_packages:
    sys.path.insert(0, str(_venv_site_packages[0]))

DEFAULT_ARCHETYPE_DIR = REPO_ROOT / "docs" / "ai" / "runtime_calibration" / "archetype_cvs" / "central"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "docs" / "ai" / "runtime_calibration" / "latest_archetype_replay.md"
app: Any | None = None


def load_archetype_json_files(input_dir: Path | str = DEFAULT_ARCHETYPE_DIR) -> list[dict[str, object]]:
    root = Path(input_dir)
    payloads: list[dict[str, object]] = []
    for path in sorted(root.glob("*.json")):
        payloads.append(json.loads(path.read_text()))
    return payloads


def extract_runtime_skill_labels(payload: dict[str, object]) -> list[str]:
    labels: list[str] = []
    for section_name in ("anchor_skills", "support_skills", "tools_technologies"):
        for item in payload.get(section_name, []):
            skill_label = str(item.get("skill_label") or "").strip()
            if skill_label:
                labels.append(skill_label)
    return labels


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def build_runtime_profile_from_archetype(payload: dict[str, object]) -> dict[str, object]:
    sector_slug = str(payload["sector_slug"])
    profile_name = f"archetype:{sector_slug}"
    skill_labels = extract_runtime_skill_labels(payload)
    deduplicated_skills = _dedupe_preserve_order(skill_labels)
    profile_summary = [
        str(item.get("label") or "").strip()
        for item in payload.get("profile_summary", [])
        if str(item.get("label") or "").strip()
    ]
    return {
        "profile_id": profile_name,
        "profile_name": profile_name,
        "sector_slug": sector_slug,
        "orientation": payload.get("orientation", {}),
        "profile_summary": profile_summary,
        "skill_labels": skill_labels,
        "skills": deduplicated_skills,
        "matching_skills": deduplicated_skills,
    }


def load_env() -> None:
    env_path = REPO_ROOT / "apps" / "api" / ".env"
    if not env_path.exists():
        return
    for key, value in dotenv_values(env_path).items():
        if value is not None and key not in os.environ:
            os.environ[key] = value


def _get_app() -> Any:
    global app
    if app is None:
        app = importlib.import_module("api.main").app
    return app


def replay_single_archetype(archetype_payload: dict[str, object], *, limit: int = 10) -> dict[str, object]:
    runtime_profile = build_runtime_profile_from_archetype(archetype_payload)
    with TestClient(_get_app()) as client:
        inbox_response = client.post(
            "/inbox",
            json={
                "profile_id": runtime_profile["profile_id"],
                "profile": runtime_profile,
                "limit": limit,
                "min_score": 0,
            },
        )
        if inbox_response.status_code != 200:
            raise RuntimeError(f"/inbox failed: {inbox_response.status_code} {inbox_response.text}")
        inbox_payload = inbox_response.json()
    return {
        "sector_slug": runtime_profile["sector_slug"],
        "profile_id": runtime_profile["profile_id"],
        "items": list(inbox_payload.get("items") or []),
    }


def summarize_archetype_top_items(
    *,
    archetype_payload: dict[str, object],
    items: list[dict[str, object]],
    verdict: str = "pending",
) -> dict[str, object]:
    return {
        "sector_slug": str(archetype_payload.get("sector_slug") or ""),
        "verdict": verdict,
        "items": [
            {
                "offer_id": item.get("offer_id"),
                "title": item.get("title"),
                "score": item.get("score"),
            }
            for item in items[:10]
        ],
    }


def render_archetype_markdown_report(summaries: list[dict[str, object]]) -> str:
    lines = ["# Archetype Replay Report", ""]
    for summary in summaries:
        lines.append(f"## {summary['sector_slug']}")
        lines.append(f"- Verdict: `{summary.get('verdict', 'pending')}`")
        lines.append("")
        lines.append("### Observed")
        if summary.get("items"):
            for item in summary["items"]:
                lines.append(f"- `{item.get('score')}` - {item.get('title')}")
        else:
            lines.append("- None")
        lines.append("")
        lines.append("### Interpreted")
        lines.append("- pending")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def run_archetype_replay(
    *,
    input_dir: Path | str = DEFAULT_ARCHETYPE_DIR,
    output_path: Path | str = DEFAULT_OUTPUT_PATH,
    limit: int = 10,
) -> dict[str, object]:
    load_env()
    archetypes = load_archetype_json_files(input_dir)
    results = [replay_single_archetype(payload, limit=limit) for payload in archetypes]
    summaries = [
        summarize_archetype_top_items(archetype_payload=payload, items=result["items"])
        for payload, result in zip(archetypes, results, strict=False)
    ]
    report = render_archetype_markdown_report(summaries)
    output_file = Path(output_path)
    output_file.write_text(report, encoding="utf-8")
    return {
        "input_dir": str(Path(input_dir)),
        "output_path": str(output_file),
        "archetype_slugs": [str(payload.get("sector_slug") or "") for payload in archetypes],
        "report": report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default=str(DEFAULT_ARCHETYPE_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)

    result = run_archetype_replay(
        input_dir=args.input_dir,
        output_path=args.output,
        limit=args.limit,
    )
    print(f"Wrote {result['output_path']}")
    print(f"Replayed archetypes: {', '.join(result['archetype_slugs'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
