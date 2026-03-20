#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from integrations.onet.config import OnetConfig
from integrations.onet.jobs.sync_runner import OnetSyncRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="O*NET v2 batch sync")
    parser.add_argument(
        "--resource",
        required=True,
        choices=["discovery", "table-info", "table-rows", "sprint-core", "sprint-tech"],
        help="Resource flow to execute",
    )
    parser.add_argument("--table", help="Database table id for table-info/table-rows")
    parser.add_argument("--max-pages", type=int, help="Limit paginated row fetches for smoke runs")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = OnetConfig.from_env()
    runner = OnetSyncRunner(config)

    if args.resource == "discovery":
        run_id = runner.run_discovery()
    elif args.resource == "table-info":
        if not args.table:
            parser.error("--table is required for --resource table-info")
        run_id = runner.run_table_info(args.table)
    elif args.resource == "table-rows":
        if not args.table:
            parser.error("--table is required for --resource table-rows")
        run_id = runner.run_table_rows(args.table, max_pages=args.max_pages)
    elif args.resource == "sprint-core":
        run_id = runner.run_sprint_core(include_tech=False)
    elif args.resource == "sprint-tech":
        run_id = runner.run_sprint_core(include_tech=True)
    else:
        parser.error(f"Unsupported resource: {args.resource}")
        return 2

    print(json.dumps({"status": "ok", "run_id": run_id}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
