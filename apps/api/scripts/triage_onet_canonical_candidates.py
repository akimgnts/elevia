#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
API_SRC = REPO_ROOT / "apps" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from integrations.onet.repository import OnetRepository  # noqa: E402
from integrations.onet.triage.promotion_triage import REPORT_PATH, run_promotion_triage  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Triages O*NET canonical promotion candidates")
    parser.add_argument("--db", default=str(REPO_ROOT / "apps" / "api" / "data" / "db" / "onet.db"))
    parser.add_argument("--report", default=str(REPO_ROOT / REPORT_PATH))
    args = parser.parse_args()

    repo = OnetRepository(Path(args.db))
    repo.ensure_schema()
    report = run_promotion_triage(repo, report_path=Path(args.report))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
