#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

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

from api.utils.domain_taxonomy_discovery import (
    DISCOVERY_BATCH_SIZE_ENV,
    build_markdown_report,
    consolidate_discovered_domains,
    run_classification_with_checkpoint,
    run_discovery_with_checkpoint,
    save_json,
    save_text,
    stratified_offer_sample,
)


def _load_env() -> None:
    env_path = REPO_ROOT / "apps" / "api" / ".env"
    cfg = dotenv_values(env_path)
    for key, value in cfg.items():
        if isinstance(value, str) and value and key not in os.environ:
            os.environ[key] = value


def _load_active_business_france_offers():
    import psycopg

    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL not set")
    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c.external_id,
                    c.title,
                    c.description,
                    c.country,
                    COALESCE(e.domain_tag, 'unknown') AS current_domain
                FROM clean_offers c
                LEFT JOIN offer_domain_enrichment e
                  ON e.source = c.source
                 AND e.external_id = c.external_id
                WHERE c.source = 'business_france'
                  AND c.is_active = TRUE
                ORDER BY c.external_id
                """
            )
            rows = cur.fetchall()
    return [
        {
            "external_id": str(external_id),
            "title": str(title or ""),
            "description": str(description or ""),
            "country": str(country or "unknown"),
            "current_domain": str(current_domain or "unknown"),
        }
        for external_id, title, description, country, current_domain in rows
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Artifact-only AI domain taxonomy discovery.")
    parser.add_argument("--discovery-size", type=int, default=200)
    parser.add_argument("--validation-size", type=int, default=250)
    parser.add_argument("--batch-size", type=int, default=int(os.getenv(DISCOVERY_BATCH_SIZE_ENV, "20")))
    parser.add_argument("--out-dir", default="baseline/domain_taxonomy_discovery")
    parser.add_argument("--report-path", default="docs/ai/reports/domain_taxonomy_discovery_v1.md")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse existing checkpoint files; skip offers already processed in a prior run.",
    )
    parser.add_argument(
        "--checkpoint-path",
        default=None,
        help="Directory to read/write per-phase checkpoint JSON files (default: <out-dir>/_checkpoints).",
    )
    args = parser.parse_args()

    _load_env()
    offers = _load_active_business_france_offers()
    discovery_sample = stratified_offer_sample(offers, sample_size=args.discovery_size)
    discovery_ids = {item["external_id"] for item in discovery_sample}
    validation_pool = [item for item in offers if item["external_id"] not in discovery_ids]
    validation_sample = stratified_offer_sample(validation_pool, sample_size=args.validation_size)

    out_dir = Path(args.out_dir)
    checkpoint_dir = Path(args.checkpoint_path) if args.checkpoint_path else (out_dir / "_checkpoints")
    discovery_checkpoint = checkpoint_dir / "discovery.json"
    classification_checkpoint = checkpoint_dir / "classification.json"

    def _emit_progress(event):
        print(json.dumps({"progress": event}, ensure_ascii=False), flush=True)

    discoveries = run_discovery_with_checkpoint(
        discovery_sample,
        batch_size=args.batch_size,
        checkpoint_path=discovery_checkpoint,
        resume=args.resume,
        progress_fn=_emit_progress,
    )

    consolidated = consolidate_discovered_domains(discoveries)
    closed_domain_list = list(consolidated.get("closed_domain_list_v1") or [])
    if "other" not in closed_domain_list:
        closed_domain_list.append("other")
    consolidated["closed_domain_list_v1"] = closed_domain_list

    classifications = run_classification_with_checkpoint(
        validation_sample,
        closed_domain_list=closed_domain_list,
        batch_size=args.batch_size,
        checkpoint_path=classification_checkpoint,
        resume=args.resume,
        progress_fn=_emit_progress,
    )

    discovery_raw = {
        "sample_size": len(discovery_sample),
        "offers": discovery_sample,
        "discoveries": discoveries,
    }
    classification_validation_v1 = {
        "sample_size": len(validation_sample),
        "offers": validation_sample,
        "classifications": classifications,
    }
    markdown = build_markdown_report(
        discovery_sample=discovery_sample,
        discoveries=discoveries,
        consolidated=consolidated,
        validation_sample=validation_sample,
        classifications=classifications,
    )

    save_json(out_dir / "discovery_raw.json", discovery_raw)
    save_json(out_dir / "consolidated_v1.json", consolidated)
    save_json(out_dir / "classification_validation_v1.json", classification_validation_v1)
    save_text(args.report_path, markdown)

    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "report_path": args.report_path,
                "active_offers": len(offers),
                "discovery_sample_size": len(discovery_sample),
                "validation_sample_size": len(validation_sample),
                "closed_domain_count": len(closed_domain_list),
                "discovery_checkpoint": str(discovery_checkpoint),
                "classification_checkpoint": str(classification_checkpoint),
                "resume": bool(args.resume),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
