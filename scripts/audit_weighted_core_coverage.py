#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

from dotenv import dotenv_values
import psycopg

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_cv_panel_backend import DEFAULT_PANEL, parse_cv

from api.utils.inbox_catalog import load_catalog_offers
from matching.extractors import extract_profile
from matching.matching_v1 import MatchingEngine
from compass.canonical.weighted_store import get_weighted_store, resolve_weighted_skill


DEFAULT_API_BASE = "http://127.0.0.1:8000"
DEFAULT_CV_DIR = "/Users/akimguentas/Downloads/cvtest"
DEFAULT_TOP_N = 10
DEFAULT_JSON_PATH = "baseline/weighted_coverage_audit/latest.json"
DEFAULT_SUMMARY_PATH = "baseline/weighted_coverage_audit/summary.md"
SOURCE = "business_france"

EXCLUDED_LABELS = {
    "anglais",
    "english",
    "francais",
    "français",
    "french",
    "communication",
    "organisation",
    "teamwork",
    "business",
    "data",
    "support",
    "project",
    "management",
    "talent",
    "acquisition",
    "client",
    "process",
    "operations",
}


def normalize_label(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def is_excluded_candidate_label(label: str | None) -> bool:
    return normalize_label(label) in EXCLUDED_LABELS


def build_offer_label_to_uri(offer: dict[str, Any]) -> dict[str, str]:
    label_to_uri: dict[str, str] = {}
    for entry in offer.get("skills_display") or []:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label") or "").strip()
        uri = str(entry.get("uri") or "").strip()
        if label and uri and label not in label_to_uri:
            label_to_uri[label] = uri
    return label_to_uri


def extract_candidate_entries(
    *,
    cv_file: str,
    domain_tag: str | None,
    offer: dict[str, Any],
    match_debug: dict[str, Any],
    resolver: Callable[[str, str | None], Any],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    skills_debug = match_debug.get("skills") if isinstance(match_debug, dict) else {}
    if not isinstance(skills_debug, dict):
        return [], []

    label_to_uri = build_offer_label_to_uri(offer)
    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    offer_cluster = offer.get("offer_cluster")
    offer_id = str(offer.get("id") or offer.get("offer_id") or "")
    offer_title = str(offer.get("title") or "")
    domain_value = str(domain_tag or "unknown")

    for bucket in ("matched_secondary", "matched_context"):
        for raw_label in skills_debug.get(bucket) or []:
            label = str(raw_label or "").strip()
            if not label:
                continue
            if is_excluded_candidate_label(label):
                excluded.append({"domain_tag": domain_value, "label": label, "bucket": bucket})
                continue

            resolved = resolver(label, offer_cluster)
            importance = getattr(resolved, "importance_level", None)
            canonical_id = getattr(resolved, "canonical_id", None)
            if importance and str(importance).upper() == "CORE":
                continue

            candidates.append(
                {
                    "domain_tag": domain_value,
                    "label": label,
                    "uri": label_to_uri.get(label),
                    "bucket": bucket,
                    "resolved": bool(canonical_id),
                    "canonical_id": canonical_id,
                    "importance_level": importance,
                    "cv": cv_file,
                    "offer_id": offer_id,
                    "offer_title": offer_title,
                }
            )
    return candidates, excluded


def aggregate_candidates(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str | None, bool, str | None, str | None], dict[str, Any]] = {}

    for entry in entries:
        key = (
            entry["domain_tag"],
            entry["label"],
            entry.get("uri"),
            bool(entry.get("resolved")),
            entry.get("canonical_id"),
            entry.get("importance_level"),
        )
        current = grouped.get(key)
        if current is None:
            current = {
                "label": entry["label"],
                "uri": entry.get("uri"),
                "frequency": 0,
                "resolved": bool(entry.get("resolved")),
                "canonical_id": entry.get("canonical_id"),
                "importance_level": entry.get("importance_level"),
                "bucket_counts": Counter(),
                "examples": [],
            }
            grouped[key] = current
        current["frequency"] += 1
        current["bucket_counts"][entry["bucket"]] += 1
        current["examples"].append(
            {
                "cv": entry["cv"],
                "offer_id": entry["offer_id"],
                "offer_title": entry["offer_title"],
            }
        )

    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (domain_tag, _label, _uri, _resolved, _canonical_id, _importance), item in grouped.items():
        item["bucket_counts"] = dict(sorted(item["bucket_counts"].items()))
        item["examples"] = item["examples"][:5]
        by_domain[domain_tag].append(item)

    return {
        domain: sorted(items, key=lambda item: (-item["frequency"], item["label"]))
        for domain, items in sorted(by_domain.items())
    }


def build_json_report(
    *,
    cv_count: int,
    offers_analyzed: int,
    domains: dict[str, list[dict[str, Any]]],
    excluded_notes: list[str],
) -> dict[str, Any]:
    candidate_count = sum(len(items) for items in domains.values())
    return {
        "summary": {
            "cv_count": cv_count,
            "offers_analyzed": offers_analyzed,
            "candidate_count": candidate_count,
        },
        "domains": domains,
        "excluded_notes": excluded_notes,
    }


def render_markdown_summary(report: dict[str, Any], excluded_counter: Counter[str]) -> str:
    domains = report.get("domains") or {}
    all_items: list[tuple[str, dict[str, Any]]] = []
    domain_totals: list[tuple[str, int]] = []
    for domain, items in domains.items():
        domain_total = sum(int(item["frequency"]) for item in items)
        domain_totals.append((domain, domain_total))
        for item in items:
            all_items.append((domain, item))

    all_items.sort(key=lambda pair: (-int(pair[1]["frequency"]), pair[0], pair[1]["label"]))
    domain_totals.sort(key=lambda pair: (-pair[1], pair[0]))

    lines = [
        "# Weighted CORE Coverage Audit",
        "",
        f"- CV analyzed: {report['summary']['cv_count']}",
        f"- Offers analyzed: {report['summary']['offers_analyzed']}",
        f"- Candidate count: {report['summary']['candidate_count']}",
        "",
        "## Top 10 Global Candidates",
    ]
    for domain, item in all_items[:10]:
        lines.append(
            f"- `{item['label']}` | domain=`{domain}` | freq={item['frequency']} | "
            f"resolved={str(item['resolved']).lower()} | importance={item['importance_level']}"
        )

    lines.extend(["", "## Domains Most Affected"])
    for domain, total in domain_totals:
        lines.append(f"- `{domain}`: {total}")

    lines.extend(["", "## Top Missing CORE Candidates By Domain"])
    for domain, items in domains.items():
        lines.append(f"### {domain}")
        for item in items[:10]:
            lines.append(
                f"- `{item['label']}` | freq={item['frequency']} | "
                f"resolved={str(item['resolved']).lower()} | importance={item['importance_level']}"
            )
        lines.append("")

    lines.append("## Notes On Obvious False Positives")
    if not excluded_counter:
        lines.append("- none")
    else:
        for label, count in excluded_counter.most_common(10):
            lines.append(f"- excluded `{label}` x {count}")
    lines.append("")
    return "\n".join(lines)


def _load_runtime_env() -> None:
    cfg = dotenv_values("apps/api/.env")
    for key, value in cfg.items():
        if isinstance(value, str) and value and key not in os.environ:
            os.environ[key] = value


def _database_url() -> str:
    _load_runtime_env()
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def fetch_active_business_france_domain_map() -> dict[str, str]:
    query = """
        SELECT c.external_id, COALESCE(e.domain_tag, 'unknown')
        FROM clean_offers c
        LEFT JOIN offer_domain_enrichment e
          ON e.source = c.source AND e.external_id = c.external_id
        WHERE c.source = %s
          AND COALESCE(c.is_active, TRUE) = TRUE
    """
    with psycopg.connect(_database_url(), connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (SOURCE,))
            return {str(external_id): str(domain_tag or "unknown") for external_id, domain_tag in cur.fetchall()}


def select_active_business_france_catalog(active_domain_map: dict[str, str]) -> list[dict[str, Any]]:
    offers = load_catalog_offers()
    active_ids = set(active_domain_map)
    selected: list[dict[str, Any]] = []
    for offer in offers:
        offer_id = str(offer.get("id") or "")
        if offer.get("source") != SOURCE or offer_id not in active_ids:
            continue
        cloned = dict(offer)
        cloned["domain_tag"] = active_domain_map[offer_id]
        selected.append(cloned)
    return selected


def score_top_offers_for_cv(
    *,
    api_base: str,
    cv_path: Path,
    timeout: int,
    top_n: int,
    offers: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[tuple[Any, dict[str, Any]]]]:
    parse_json = parse_cv(api_base, cv_path, timeout)
    profile = parse_json.get("profile") or {}
    extracted = extract_profile(profile)
    engine = MatchingEngine(offers)
    scored = [(engine.score_offer(extracted, offer), offer) for offer in offers]
    scored.sort(key=lambda pair: (-float(pair[0].score), str(pair[0].offer_id)))
    return parse_json, scored[:top_n]


def run_audit(
    *,
    api_base: str,
    cv_dir: Path,
    panel: list[str],
    top_n: int,
    timeout: int,
) -> tuple[dict[str, Any], str]:
    _load_runtime_env()
    domain_map = fetch_active_business_france_domain_map()
    offers = select_active_business_france_catalog(domain_map)
    store = get_weighted_store()

    def resolver(label: str, offer_cluster: str | None):
        return resolve_weighted_skill(
            label,
            offer_cluster,
            store=store,
            clamp_min=0.5,
            clamp_max=1.5,
        )

    candidates: list[dict[str, Any]] = []
    excluded_counter: Counter[str] = Counter()
    offers_analyzed = 0

    for cv_name in panel:
        cv_path = cv_dir / cv_name
        if not cv_path.exists():
            continue
        _parse_json, top_results = score_top_offers_for_cv(
            api_base=api_base,
            cv_path=cv_path,
            timeout=timeout,
            top_n=top_n,
            offers=offers,
        )
        offers_analyzed += len(top_results)
        for result, offer in top_results:
            match_debug = result.match_debug or {}
            new_candidates, excluded = extract_candidate_entries(
                cv_file=cv_name,
                domain_tag=offer.get("domain_tag"),
                offer=offer,
                match_debug=match_debug,
                resolver=resolver,
            )
            candidates.extend(new_candidates)
            for item in excluded:
                excluded_counter[item["label"]] += 1

    domains = aggregate_candidates(candidates)
    excluded_notes = [label for label, _count in excluded_counter.most_common(20)]
    report = build_json_report(
        cv_count=len(panel),
        offers_analyzed=offers_analyzed,
        domains=domains,
        excluded_notes=excluded_notes,
    )
    summary = render_markdown_summary(report, excluded_counter)
    return report, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit weighted CORE coverage gaps from real CV/offer matches.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--cv-dir", default=DEFAULT_CV_DIR)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--out-json", default=DEFAULT_JSON_PATH)
    parser.add_argument("--out-md", default=DEFAULT_SUMMARY_PATH)
    args = parser.parse_args()

    report, summary = run_audit(
        api_base=args.api_base,
        cv_dir=Path(args.cv_dir),
        panel=list(DEFAULT_PANEL),
        top_n=args.top_n,
        timeout=args.timeout,
    )

    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(summary, encoding="utf-8")

    print(
        json.dumps(
            {
                "cv_count": report["summary"]["cv_count"],
                "offers_analyzed": report["summary"]["offers_analyzed"],
                "candidate_count": report["summary"]["candidate_count"],
                "out_json": str(out_json),
                "out_md": str(out_md),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
