"""Optional France Travail env gate test (skips if missing vars)."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from fetchers.client_ft import FranceTravailClient  # noqa: E402


@pytest.mark.ft_optional
def test_ft_client_init_env_gate():
    required = ["CLIENT_ID", "CLIENT_SECRET", "TOKEN_URL"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        pytest.skip(f"Missing env vars for FT API: {', '.join(missing)}")

    client = FranceTravailClient()
    assert client.base_url
