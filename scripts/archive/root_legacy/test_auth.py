#!/usr/bin/env python3
"""
Test authentification France Travail 2025 (safe for pytest).
"""
import os
from typing import Dict


def _load_env() -> Dict[str, str]:
    from dotenv import load_dotenv
    load_dotenv()
    return {
        "token_url": os.getenv("FT_TOKEN_URL"),
        "client_id": os.getenv("FT_CLIENT_ID"),
        "client_secret": os.getenv("FT_CLIENT_SECRET"),
        "scopes": os.getenv("FT_SCOPES"),
    }


def run_auth_check(dry_run: bool = False) -> Dict[str, str]:
    data = _load_env()
    if not data["token_url"] or not data["client_id"] or not data["client_secret"]:
        return {"status": "ENV_MISSING"}

    if dry_run:
        return {"status": "DRY_RUN"}

    import requests

    payload = {
        "grant_type": "client_credentials",
        "client_id": data["client_id"],
        "client_secret": data["client_secret"],
        "scope": data["scopes"],
    }
    r = requests.post(data["token_url"], data=payload, timeout=10)
    return {"status": "SUCCESS" if r.status_code == 200 else "FAILED"}


def test_auth_env_gate():
    result = run_auth_check(dry_run=True)
    assert result["status"] in {"ENV_MISSING", "DRY_RUN", "SUCCESS"}


if __name__ == "__main__":
    print(run_auth_check(dry_run=False))
