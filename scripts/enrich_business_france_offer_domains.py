#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))
_venv_site_packages = sorted((REPO_ROOT / "apps" / "api" / ".venv" / "lib").glob("python*/site-packages"))
if _venv_site_packages:
    sys.path.insert(0, str(_venv_site_packages[0]))

from api.utils.offer_domain_enrichment import classify_and_persist_business_france_offer_domains


def main() -> int:
    load_dotenv(REPO_ROOT / "apps" / "api" / ".env")
    result = classify_and_persist_business_france_offer_domains()
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("error") is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
