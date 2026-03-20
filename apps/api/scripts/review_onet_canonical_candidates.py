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


def main() -> int:
    parser = argparse.ArgumentParser(description="Review O*NET canonical promotion candidates")
    parser.add_argument("--db", default=str(REPO_ROOT / "apps" / "api" / "data" / "db" / "onet.db"))
    parser.add_argument("--review-status", choices=["pending", "approved", "rejected"], default=None)
    parser.add_argument(
        "--tier",
        choices=["high_priority", "reviewable", "rejected_noise", "deferred_long_tail"],
        default=None,
    )
    parser.add_argument("--top", type=int, default=None)
    parser.add_argument("--external-skill-id", default=None)
    parser.add_argument("--set-status", choices=["approved", "rejected"], default=None)
    args = parser.parse_args()

    repo = OnetRepository(Path(args.db))
    repo.ensure_schema()

    if args.external_skill_id and args.set_status:
        repo.set_canonical_promotion_review_status(args.external_skill_id, review_status=args.set_status)

    rows = [
        dict(row)
        for row in repo.list_canonical_promotion_candidates(
            review_status=args.review_status,
            promotion_tier=args.tier,
            top=args.top,
        )
    ]
    if args.external_skill_id:
        rows = [row for row in rows if row["external_skill_id"] == args.external_skill_id]
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
