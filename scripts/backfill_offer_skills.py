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

from api.utils.offer_skills_pg import backfill_offer_skills


def _load_env() -> None:
    env_path = REPO_ROOT / "apps" / "api" / ".env"
    cfg = dotenv_values(env_path)
    for key, value in cfg.items():
        if isinstance(value, str) and value and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill canonical offer skills into PostgreSQL offer_skills.")
    parser.add_argument("--source", default="business_france")
    parser.add_argument("--clean-table", default="clean_offers")
    parser.add_argument("--offer-skills-table", default="offer_skills")
    parser.add_argument("--enrichment-version", default="offer_skills_v2")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=15,
        help="Max offers per AI fallback call (default 15).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Upper bound on offers scanned (useful for bounded live validation).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run everything (incl. AI fallback) but rollback the transaction.",
    )
    args = parser.parse_args()

    _load_env()
    result = backfill_offer_skills(
        clean_table=args.clean_table,
        offer_skills_table=args.offer_skills_table,
        enrichment_version=args.enrichment_version,
        source=args.source,
        fallback_batch_size=args.batch_size,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
