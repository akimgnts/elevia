"""
test_analyze_dev_mode.py — Dev-only Analyze pipeline debug payload.

Ensures:
  - analyze_dev is absent when DEV tools are off
  - analyze_dev is present when DEV tools are on
  - counters keys exist (signal-first)
"""
from __future__ import annotations

import io
import os
from unittest.mock import patch

from fastapi.testclient import TestClient


_TECH_CV = (
    "Python SQL data analysis machine learning ETL "
    "data visualization Tableau Power BI"
)


def _post_txt(client: TestClient, text: str):
    return client.post(
        "/profile/parse-file",
        files={"file": ("cv.txt", io.BytesIO(text.encode("utf-8")), "text/plain")},
    )


def test_analyze_dev_off_absent():
    from api.main import app

    with patch.dict(os.environ, {"ELEVIA_DEV_TOOLS": "0", "ELEVIA_DEV": "0"}):
        client = TestClient(app)
        resp = _post_txt(client, _TECH_CV)

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    body = resp.json()
    assert "analyze_dev" not in body, "analyze_dev must be absent when DEV tools are OFF"


def test_analyze_dev_on_present():
    from api.main import app

    with patch.dict(os.environ, {"ELEVIA_DEV_TOOLS": "1"}):
        client = TestClient(app)
        resp = _post_txt(client, _TECH_CV)

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
    body = resp.json()
    assert "analyze_dev" in body, "analyze_dev must be present when DEV tools are ON"
    counters = body["analyze_dev"].get("counters", {})
    for key in (
        "raw_count",
        "tight_count",
        "canonical_count",
        "unresolved_count",
        "expanded_count",
        "promoted_uri_count",
        "near_match_count",
    ):
        assert key in counters, f"Missing counter {key} in analyze_dev.counters"
