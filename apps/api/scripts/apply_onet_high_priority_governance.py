#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
API_SRC = REPO_ROOT / "apps" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from compass.canonical.master_store import reset_master_canonical_store  # noqa: E402
from integrations.onet.governance.high_priority_decisions import apply_high_priority_governance  # noqa: E402
from integrations.onet.repository import OnetRepository  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Applies governed decisions to O*NET high-priority canonical candidates")
    parser.add_argument("--db", default=str(REPO_ROOT / "apps" / "api" / "data" / "db" / "onet.db"))
    args = parser.parse_args()

    repo = OnetRepository(Path(args.db))
    repo.ensure_schema()
    summary = apply_high_priority_governance(repo)
    reset_master_canonical_store()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
