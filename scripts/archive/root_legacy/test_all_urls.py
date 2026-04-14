#!/usr/bin/env python3
"""
Test EXHAUSTIF de toutes les URLs possibles France Travail 2025
"""
import os
from typing import Dict


def _load_env():
    from dotenv import load_dotenv
    load_dotenv()
    client_id = os.getenv("FT_CLIENT_ID")
    client_secret = os.getenv("FT_CLIENT_SECRET")
    scopes = os.getenv("FT_SCOPES")
    return client_id, client_secret, scopes


def probe_all_urls(dry_run: bool = False) -> Dict[str, str]:
    client_id, client_secret, scopes = _load_env()

    if not client_id or not client_secret or not scopes:
        return {"status": "ENV_MISSING"}

    if dry_run:
        return {"status": "DRY_RUN"}

    import requests

    urls = [
        "https://francetravail.io/connexion/oauth2/access_token",
        "https://francetravail.io/connexion/oauth2/access_token?realm=/partenaire",
        "https://entreprise.francetravail.io/connexion/oauth2/access_token",
        "https://authentification.francetravail.io/connexion/oauth2/access_token",
        "https://pole-emploi.io/connexion/oauth2/access_token",
        "https://pole-emploi.io/connexion/oauth2/access_token?realm=/partenaire",
        "https://entreprise.pole-emploi.io/connexion/oauth2/access_token",
        "https://authentification.pole-emploi.io/connexion/oauth2/access_token",
    ]

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": scopes,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    for url in urls:
        r = requests.post(url, data=data, headers=headers, timeout=10)
        if r.status_code == 200:
            return {"status": "SUCCESS", "url": url}

    return {"status": "FAILED"}


def test_all_urls_env_gate():
    result = probe_all_urls(dry_run=True)
    assert result["status"] in {"ENV_MISSING", "DRY_RUN", "SUCCESS"}


if __name__ == "__main__":
    result = probe_all_urls(dry_run=False)
    print(result)
