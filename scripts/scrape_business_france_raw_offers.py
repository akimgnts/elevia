#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from api.utils.business_france_raw_scraper import scrape_business_france_raw_offers


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape Business France offers into raw_offers")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of offers to fetch")
    parser.add_argument("--batch-size", type=int, default=100, help="Search page size")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Fetch only, do not write raw_offers")
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parents[1] / "apps" / "api" / ".env")
    result = scrape_business_france_raw_offers(
        limit=args.limit,
        batch_size=args.batch_size,
        timeout=args.timeout,
        dry_run=args.dry_run,
    )
    print(
        json.dumps(
            {
                "fetched": result.fetched,
                "persisted": result.persisted,
                "total_count": result.total_count,
                "error": result.error,
                "dry_run": args.dry_run,
            },
            ensure_ascii=False,
        )
    )
    return 0 if result.error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
