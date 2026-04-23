#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import requests


DEFAULT_PANEL = [
    "CV CDI MOUSTAPHA LO DATA.pdf",
    "CV - Nawel KADI 2026.pdf",
    "Akim_Guentas_Resume.pdf",
    "CV Mathilde CEVAK.pdf",
    "CV WECKER.pdf",
]


def deep_get(data: dict[str, Any], *path: str, default: Any = None) -> Any:
    cur: Any = data
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def pick_first_existing(data: dict[str, Any], paths: list[tuple[str, ...]], default: Any = None) -> Any:
    for path in paths:
        value = deep_get(data, *path, default=None)
        if value is not None:
            return value
    return default


def normalize_skill_label(item: Any) -> str | None:
    if isinstance(item, str):
        label = item.strip()
        return label or None
    if isinstance(item, dict):
        for key in ("label", "name", "skill", "raw", "value", "text"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def to_signal_lines(items: Iterable[Any], limit: int = 8) -> list[str]:
    labels: list[str] = []
    for item in items:
        label = normalize_skill_label(item)
        if label and label not in labels:
            labels.append(label)
        if len(labels) >= limit:
            break
    return labels


def summarize_parse(parse_json: dict[str, Any]) -> dict[str, Any]:
    canonical_skills = ensure_list(parse_json.get("canonical_skills"))
    validated_items = ensure_list(parse_json.get("validated_items"))
    profile = parse_json.get("profile") or {}
    skills_uri = ensure_list(profile.get("skills_uri") or parse_json.get("skills_uri"))
    experiences = pick_first_existing(
        parse_json,
        [
            ("profile", "career_profile", "experiences"),
            ("career_profile", "experiences"),
            ("profile", "experiences"),
            ("experiences",),
        ],
        default=[],
    )

    return {
        "canonical_skills_count": parse_json.get("canonical_skills_count", len(canonical_skills)),
        "validated_items_count": len(validated_items),
        "skills_uri_count": len(skills_uri),
        "experiences_count": len(ensure_list(experiences)),
        "canonical_skills_sample": to_signal_lines(canonical_skills, limit=10),
        "validated_items_sample": to_signal_lines(validated_items, limit=10),
        "skills_uri_sample": skills_uri[:10],
    }


def build_inbox_payload(
    parse_json: dict[str, Any],
    default_profile_id: str,
    *,
    min_score: int = 0,
    limit: int = 24,
    explain: bool = True,
) -> dict[str, Any]:
    profile = parse_json.get("profile") or {}
    profile_id = str(profile.get("id") or parse_json.get("profile_id") or default_profile_id)
    return {
        "profile_id": profile_id,
        "profile": profile,
        "min_score": min_score,
        "limit": limit,
        "explain": explain,
    }


@dataclass
class OfferMetrics:
    offer_id: str
    title: str | None
    score: float | int | None
    matched_core_count: int
    missing_core_count: int
    matched_full_count: int
    missing_full_count: int
    matched_core: list[str]
    missing_core: list[str]
    matched_full: list[str]
    missing_full: list[str]
    rank: int


@dataclass
class CvResult:
    cv_file: str
    parse_summary: dict[str, Any]
    offers_count: int
    top_offers: list[OfferMetrics]


def extract_inbox_items(inbox_json: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(inbox_json, list):
        return [item for item in inbox_json if isinstance(item, dict)]
    for key in ("items", "offers", "results", "data"):
        value = inbox_json.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _extract_explain_labels(items: Any) -> list[str]:
    return [label for label in (normalize_skill_label(item) for item in ensure_list(items)) if label]


def extract_offer_metrics(items: list[dict[str, Any]], top_k: int) -> list[OfferMetrics]:
    offers: list[OfferMetrics] = []
    for rank, item in enumerate(items[:top_k], start=1):
        explain = item.get("explain") or item.get("matching_explain") or {}
        matched_core = _extract_explain_labels(explain.get("matched_core"))
        missing_core = _extract_explain_labels(explain.get("missing_core"))
        matched_full = _extract_explain_labels(explain.get("matched_full"))
        missing_full = _extract_explain_labels(explain.get("missing_full"))
        offers.append(
            OfferMetrics(
                offer_id=str(item.get("offer_id") or item.get("id") or f"rank_{rank}"),
                title=item.get("title") or deep_get(item, "offer", "title"),
                score=item.get("score"),
                matched_core_count=len(matched_core),
                missing_core_count=len(missing_core),
                matched_full_count=len(matched_full),
                missing_full_count=len(missing_full),
                matched_core=matched_core,
                missing_core=missing_core,
                matched_full=matched_full,
                missing_full=missing_full,
                rank=rank,
            )
        )
    return offers


def parse_cv(api_base: str, cv_path: Path, timeout: int) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/profile/parse-file"
    mime = mimetypes.guess_type(cv_path.name)[0] or "application/pdf"
    with cv_path.open("rb") as handle:
        response = requests.post(url, files={"file": (cv_path.name, handle, mime)}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def run_inbox(
    api_base: str,
    inbox_payload: dict[str, Any],
    timeout: int,
    page_size: int,
    domain_mode: str,
) -> dict[str, Any]:
    url = (
        f"{api_base.rstrip('/')}/inbox"
        f"?domain_mode={domain_mode}&page=1&page_size={page_size}&sort=score_desc"
    )
    response = requests.post(url, json=inbox_payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def resolve_panel(cv_dir: Path, panel: list[str] | None) -> tuple[list[Path], list[str]]:
    if panel is None:
        candidates = sorted(
            path for path in cv_dir.iterdir() if path.is_file() and path.suffix.lower() in {".pdf", ".doc", ".docx"}
        )
        return candidates, []

    files: list[Path] = []
    missing: list[str] = []
    for name in panel:
        path = cv_dir / name
        if path.exists():
            files.append(path)
        else:
            missing.append(name)
    return files, missing


def run_panel(
    api_base: str,
    cv_dir: Path,
    panel: list[str] | None,
    out_json: Path,
    timeout: int,
    top_k: int,
    page_size: int,
    domain_mode: str,
) -> dict[str, Any]:
    cv_files, missing_files = resolve_panel(cv_dir, panel)
    results: list[CvResult] = []

    for cv_file in cv_files:
        print(f"--- {cv_file.name}")
        parse_json = parse_cv(api_base, cv_file, timeout)
        parse_summary = summarize_parse(parse_json)
        inbox_payload = build_inbox_payload(
            parse_json,
            default_profile_id=cv_file.stem,
            min_score=0,
            limit=page_size,
            explain=True,
        )
        inbox_json = run_inbox(api_base, inbox_payload, timeout, page_size, domain_mode)
        inbox_items = extract_inbox_items(inbox_json)
        top_offers = extract_offer_metrics(inbox_items, top_k=top_k)
        results.append(
            CvResult(
                cv_file=cv_file.name,
                parse_summary=parse_summary,
                offers_count=len(inbox_items),
                top_offers=top_offers,
            )
        )
        print(
            f"offers={len(inbox_items)} "
            f"skills_uri={parse_summary['skills_uri_count']} "
            f"canonical={parse_summary['canonical_skills_count']}"
        )

    payload = {
        "api_base": api_base,
        "cv_dir": str(cv_dir),
        "domain_mode": domain_mode,
        "top_k": top_k,
        "page_size": page_size,
        "missing_files": missing_files,
        "results": [
            {
                "cv_file": result.cv_file,
                "parse_summary": result.parse_summary,
                "offers_count": result.offers_count,
                "top_offers": [asdict(offer) for offer in result.top_offers],
            }
            for result in results
        ],
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run backend CV panel tests against /profile/parse-file and /inbox")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="Base URL of the API")
    parser.add_argument("--cv-dir", default="/Users/akimguentas/Downloads/cvtest", help="Directory containing CVs")
    parser.add_argument(
        "--out-json",
        default="baseline/panel_backend_run/latest.json",
        help="Where to save the JSON report",
    )
    parser.add_argument("--timeout", type=int, default=120, help="Request timeout in seconds")
    parser.add_argument("--top-k", type=int, default=3, help="How many top offers to keep")
    parser.add_argument("--page-size", type=int, default=24, help="Inbox page size and payload limit")
    parser.add_argument(
        "--domain-mode",
        default="all",
        choices=["all", "in_domain", "strict"],
        help="Inbox domain mode",
    )
    parser.add_argument(
        "--all-cvs",
        action="store_true",
        help="Use all readable CVs in the directory instead of the fixed default panel",
    )
    args = parser.parse_args()

    payload = run_panel(
        api_base=args.api_base,
        cv_dir=Path(args.cv_dir),
        panel=None if args.all_cvs else DEFAULT_PANEL,
        out_json=Path(args.out_json),
        timeout=args.timeout,
        top_k=args.top_k,
        page_size=args.page_size,
        domain_mode=args.domain_mode,
    )
    print(f"\nSaved report to: {args.out_json}")
    print(f"CV tested: {len(payload['results'])}")
    if payload["missing_files"]:
        print(f"Missing files: {payload['missing_files']}")


if __name__ == "__main__":
    main()
