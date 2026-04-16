#!/usr/bin/env python3
"""Phase 2 Block 1 batch report for document understanding comparison metrics."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "apps" / "api" / "src"
DEFAULT_INPUT_DIR = Path("/Users/akimguentas/Downloads/cvtest")
DEFAULT_OUTPUT_JSON = ROOT / "apps" / "api" / "data" / "eval" / "document_understanding_phase2_block1_report.json"
DEFAULT_OUTPUT_MD = ROOT / "apps" / "api" / "data" / "eval" / "document_understanding_phase2_block1_report.md"

sys.path.insert(0, str(SRC))

from compass.pipeline.contracts import ParseFilePipelineRequest  # noqa: E402
from compass.pipeline.profile_parse_pipeline import build_parse_file_response_payload  # noqa: E402


def _content_type_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".txt":
        return "text/plain"
    return "application/octet-stream"


def _iter_cv_files(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        return []
    return sorted(
        path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() in {".pdf", ".txt"}
    )


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _comparison_label(metrics: dict[str, Any]) -> str:
    identity_legacy = bool(metrics.get("identity_detected_legacy"))
    identity_understanding = bool(metrics.get("identity_detected_understanding"))
    experience_legacy = _to_int(metrics.get("experience_count_legacy"))
    experience_understanding = _to_int(metrics.get("experience_count_understanding"))
    suspicious_merges = _to_int(metrics.get("suspicious_merges_count"))

    identity_improved = identity_understanding and not identity_legacy
    identity_degraded = identity_legacy and not identity_understanding
    experience_improved = experience_understanding > experience_legacy
    experience_degraded = experience_understanding < experience_legacy or (
        experience_understanding == 0 and experience_legacy > 0
    )

    if (identity_improved and experience_degraded) or (identity_degraded and experience_improved):
        return "mixed"
    if identity_improved or (experience_improved and suspicious_merges == 0):
        return "better"
    if identity_degraded or (experience_degraded and experience_understanding == 0 and experience_legacy > 0):
        return "worse"
    return "equal"


def _comparison_reason(metrics: dict[str, Any], label: str) -> str:
    identity_legacy = bool(metrics.get("identity_detected_legacy"))
    identity_understanding = bool(metrics.get("identity_detected_understanding"))
    experience_legacy = _to_int(metrics.get("experience_count_legacy"))
    experience_understanding = _to_int(metrics.get("experience_count_understanding"))
    suspicious_merges = _to_int(metrics.get("suspicious_merges_count"))

    if label == "mixed":
        return (
            f"identity={identity_legacy}->{identity_understanding}, "
            f"experiences={experience_legacy}->{experience_understanding}"
        )
    if label == "better":
        if identity_understanding and not identity_legacy:
            return "identity improved"
        if experience_understanding > experience_legacy and suspicious_merges == 0:
            return "experience count improved without suspicious merges"
    if label == "worse":
        if identity_legacy and not identity_understanding:
            return "identity lost"
        if experience_understanding == 0 and experience_legacy > 0:
            return "understanding detected no experiences while legacy had some"
    return "no strict gain or loss on the comparison axes"


def _extract_metrics(profile: dict[str, Any]) -> dict[str, Any]:
    document_understanding = profile.get("document_understanding")
    if not isinstance(document_understanding, dict):
        return {}
    diagnostics = document_understanding.get("parsing_diagnostics")
    if not isinstance(diagnostics, dict):
        return {}
    metrics = diagnostics.get("comparison_metrics")
    return metrics if isinstance(metrics, dict) else {}


def _summarize_case(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    metrics = _extract_metrics(profile)
    if not metrics:
        return {
            "file": path.name,
            "path": str(path),
            "status": "error",
            "error": "missing_comparison_metrics",
        }
    label = _comparison_label(metrics)
    return {
        "file": path.name,
        "path": str(path),
        "status": "ok",
        "comparison_label": label,
        "comparison_reason": _comparison_reason(metrics, label),
        "comparison_metrics": metrics,
    }


def _aggregate_results(cases: Iterable[dict[str, Any]]) -> dict[str, Any]:
    case_list = list(cases)
    parsed_cases = [case for case in case_list if case.get("status") == "ok"]
    label_counts = Counter(str(case.get("comparison_label") or "") for case in parsed_cases)
    label_counts.pop("", None)
    return {
        "count": len(case_list),
        "parsed_count": len(parsed_cases),
        "error_count": len(case_list) - len(parsed_cases),
        "label_counts": {
            "better": label_counts.get("better", 0),
            "equal": label_counts.get("equal", 0),
            "worse": label_counts.get("worse", 0),
            "mixed": label_counts.get("mixed", 0),
        },
    }


def _run_real_pipeline(path: Path) -> dict[str, Any]:
    request = ParseFilePipelineRequest(
        request_id=f"doc-understanding-phase2:{path.name}",
        raw_filename=path.name,
        content_type=_content_type_for_path(path),
        file_bytes=path.read_bytes(),
        enrich_llm=0,
    )
    return build_parse_file_response_payload(request)


def _build_report(input_dir: Path) -> dict[str, Any]:
    files = _iter_cv_files(input_dir)
    cases: list[dict[str, Any]] = []
    for path in files:
        try:
            payload = _run_real_pipeline(path)
            cases.append(_summarize_case(path, payload))
        except Exception as exc:
            cases.append(
                {
                    "file": path.name,
                    "path": str(path),
                    "status": "error",
                    "error": type(exc).__name__,
                    "error_detail": str(exc),
                }
            )
    return {
        "input": {
            "directory": str(input_dir),
            "llm_enabled": False,
            "deterministic": True,
            "file_count": len(files),
        },
        "cases": cases,
        "aggregate": _aggregate_results(cases),
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Document Understanding Phase 2 Block 1 Report", ""]
    lines.append(f"- Directory: `{report['input']['directory']}`")
    lines.append(f"- File count: `{report['input']['file_count']}`")
    lines.append(f"- Parsed count: `{report['aggregate']['parsed_count']}`")
    lines.append(f"- Error count: `{report['aggregate']['error_count']}`")
    lines.append("")
    lines.append("## Aggregate counts")
    for label, count in report["aggregate"]["label_counts"].items():
        lines.append(f"- {label}: `{count}`")
    lines.append("")
    lines.append("## Per CV")
    for case in report["cases"]:
        lines.append(f"- `{case['file']}`: `{case['status']}`")
        if case["status"] == "ok":
            lines.append(
                f"  - label: `{case['comparison_label']}` | reason: `{case['comparison_reason']}`"
            )
            metrics = case.get("comparison_metrics") or {}
            lines.append(
                "  - metrics: "
                f"identity_legacy={metrics.get('identity_detected_legacy')}, "
                f"identity_understanding={metrics.get('identity_detected_understanding')}, "
                f"experiences_legacy={metrics.get('experience_count_legacy')}, "
                f"experiences_understanding={metrics.get('experience_count_understanding')}, "
                f"projects_understanding={metrics.get('project_count_understanding')}, "
                f"suspicious_merges={metrics.get('suspicious_merges_count')}, "
                f"orphans={metrics.get('orphan_lines_count')}, "
                f"invalid_headers={metrics.get('invalid_experience_headers_count')}"
            )
        else:
            lines.append(f"  - error: `{case.get('error')}`")
            if case.get("error_detail"):
                lines.append(f"  - detail: `{case['error_detail']}`")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory containing CV files to evaluate.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_OUTPUT_JSON,
        help="Path to write the JSON report.",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=DEFAULT_OUTPUT_MD,
        help="Path to write the Markdown report.",
    )
    args = parser.parse_args(argv)

    os.environ.setdefault("ELEVIA_DEV_TOOLS", "0")
    os.environ.setdefault("OPENAI_API_KEY", "")

    report = _build_report(args.input_dir)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.output_md.write_text(_markdown_report(report), encoding="utf-8")

    print(json.dumps(report["aggregate"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
