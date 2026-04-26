#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))
_venv_site_packages = sorted((REPO_ROOT / "apps" / "api" / ".venv" / "lib").glob("python*/site-packages"))
if _venv_site_packages:
    sys.path.insert(0, str(_venv_site_packages[0]))

from api.utils.inbox_catalog import load_catalog_offers
from api.routes.inbox import _extract_profile_intelligence_payload, _score_offers
from matching import MatchingEngine
from matching.extractors import extract_profile
from offer.generic_skill_stats import get_offer_count, load_generic_skill_table


DEFAULT_PANEL = {
    "Akim_Guentas_Resume.pdf": "data",
    "CV CDI MOUSTAPHA LO DATA.pdf": "data",
    "CV - Nawel KADI 2026.pdf": "hr",
    "CV Mathilde CEVAK.pdf": "sales",
    "CV WECKER.pdf": "engineering",
}


def parse_cv(api_base: str, cv_path: Path, timeout: int) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/profile/parse-file"
    mime = mimetypes.guess_type(cv_path.name)[0] or "application/pdf"
    with cv_path.open("rb") as handle:
        response = requests.post(url, files={"file": (cv_path.name, handle, mime)}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def load_active_business_france_domain_map() -> dict[str, str]:
    import psycopg

    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT e.external_id, e.domain_tag
                FROM offer_domain_enrichment e
                JOIN clean_offers c
                  ON c.source = e.source AND c.external_id = e.external_id
                WHERE e.source = 'business_france'
                  AND c.source = 'business_france'
                  AND COALESCE(c.is_active, TRUE) = TRUE
                """
            )
            return {str(external_id): str(domain_tag) for external_id, domain_tag in cur.fetchall()}


def filter_catalog_by_offer_ids(catalog: list[dict[str, Any]], allowed_ids: set[str]) -> list[dict[str, Any]]:
    return [
        offer
        for offer in catalog
        if str(offer.get("id") or "") in allowed_ids and offer.get("source") == "business_france"
    ]


def build_domain_distribution(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        counts[str(item.get("domain_tag") or "unknown")] += 1
    return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def score_catalog(
    catalog: list[dict[str, Any]],
    *,
    profile_payload: dict[str, Any],
    limit: int,
    domain_map: dict[str, str],
) -> list[dict[str, Any]]:
    engine = MatchingEngine(offers=catalog)
    extracted = extract_profile(profile_payload)
    profile_intelligence = _extract_profile_intelligence_payload(profile_payload)
    items, _explain_debug, _source_map, _offer_lookup, _offer_intelligence_map, _gate_rejections = _score_offers(
        catalog,
        decided_ids=set(),
        engine=engine,
        extracted=extracted,
        profile_payload=profile_payload,
        profile_intelligence=profile_intelligence,
        explain_enabled=True,
        min_score=0,
        freq_table=load_generic_skill_table(),
        offer_count=get_offer_count(),
    )
    ranked = sorted(items, key=lambda item: (-item.score, -(item.signal_score or 0.0), item.offer_id))
    rows: list[dict[str, Any]] = []
    for rank, item in enumerate(ranked[:limit], start=1):
        explanation = item.explanation.model_dump() if item.explanation else {}
        rows.append(
            {
                "rank": rank,
                "offer_id": item.offer_id,
                "title": item.title,
                "company": item.company,
                "domain_tag": domain_map.get(str(item.offer_id), "unknown"),
                "score": item.score,
                "matched_core": [entry.get("label") for entry in explanation.get("matched_core", []) if entry.get("label")],
                "missing_core": [entry.get("label") for entry in explanation.get("missing_core", []) if entry.get("label")],
            }
        )
    return rows


def run_experiment(
    *,
    api_base: str,
    cv_dir: Path,
    top_k: int,
    timeout: int,
    panel: dict[str, str],
) -> dict[str, Any]:
    catalog = load_catalog_offers()
    domain_map = load_active_business_france_domain_map()
    active_ids = set(domain_map)
    baseline_catalog = filter_catalog_by_offer_ids(catalog, active_ids)

    results: list[dict[str, Any]] = []
    for cv_name, expected_domain in panel.items():
        cv_path = cv_dir / cv_name
        parse_json = parse_cv(api_base, cv_path, timeout)
        profile_payload = parse_json.get("profile") or {}
        baseline_rows = score_catalog(
            baseline_catalog,
            profile_payload=profile_payload,
            limit=top_k,
            domain_map=domain_map,
        )
        filtered_ids = {offer_id for offer_id, domain_tag in domain_map.items() if domain_tag == expected_domain}
        filtered_catalog = filter_catalog_by_offer_ids(catalog, filtered_ids)
        filtered_rows = score_catalog(
            filtered_catalog,
            profile_payload=profile_payload,
            limit=top_k,
            domain_map=domain_map,
        )

        results.append(
            {
                "cv_file": cv_name,
                "expected_domain": expected_domain,
                "baseline": {
                    "top_offers": baseline_rows,
                    "top_domain_distribution": build_domain_distribution(baseline_rows),
                },
                "domain_filter": {
                    "top_offers": filtered_rows,
                    "top_domain_distribution": build_domain_distribution(filtered_rows),
                },
            }
        )

    return {
        "api_base": api_base,
        "cv_dir": str(cv_dir),
        "top_k": top_k,
        "panel": panel,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit domain filtering against current BF matching.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--cv-dir", default="/Users/akimguentas/Downloads/cvtest")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--out-json", default="baseline/domain_filter_audit/latest.json")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / "apps" / "api" / ".env")
    payload = run_experiment(
        api_base=args.api_base,
        cv_dir=Path(args.cv_dir),
        top_k=args.top_k,
        timeout=args.timeout,
        panel=DEFAULT_PANEL,
    )
    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out_json": str(out_path), "cv_count": len(payload["results"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
