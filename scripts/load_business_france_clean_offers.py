#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from api.utils.clean_offers_pg import load_business_france_raw_into_clean


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / "apps" / "api" / ".env")
    result = load_business_france_raw_into_clean()
    print(json.dumps({
        "attempted": result.attempted,
        "persisted": result.persisted,
        "error": result.error,
    }, ensure_ascii=False))
    return 0 if result.error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
