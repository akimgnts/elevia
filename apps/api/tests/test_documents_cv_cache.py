"""
test_documents_cv_cache.py — Cache set/get + key determinism.

Tests:
  - make_cache_key: same inputs → same key (deterministic)
  - make_cache_key: different inputs → different key
  - cache_set → cache_get round-trip
  - cache_get miss → None
  - cache_set idempotent (second write → same result)
  - cache_set with large payload (no crash)
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure src on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from documents.cache import make_cache_key, cache_get, cache_set


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path):
    """Redirect DB_PATH to a temp file for isolation."""
    db = tmp_path / "test_cache.db"
    with patch("documents.cache._DB_PATH", db):
        yield db


# ── make_cache_key ────────────────────────────────────────────────────────────

def test_cache_key_deterministic():
    """Same inputs always produce the same key."""
    k1 = make_cache_key("fp1234", "BF-100", "cv_v1")
    k2 = make_cache_key("fp1234", "BF-100", "cv_v1")
    assert k1 == k2


def test_cache_key_different_inputs():
    """Different inputs produce different keys."""
    k1 = make_cache_key("fp1234", "BF-100", "cv_v1")
    k2 = make_cache_key("fp1234", "BF-200", "cv_v1")
    k3 = make_cache_key("fp9999", "BF-100", "cv_v1")
    k4 = make_cache_key("fp1234", "BF-100", "cv_v2")
    assert len({k1, k2, k3, k4}) == 4


def test_cache_key_format():
    """Cache key is 40 hex characters."""
    k = make_cache_key("abc", "BF-1", "cv_v1")
    assert len(k) == 40
    assert all(c in "0123456789abcdef" for c in k)


# ── cache_get / cache_set ─────────────────────────────────────────────────────

def test_cache_miss(tmp_db):
    """cache_get on unknown key → None."""
    result = cache_get("nonexistent_key_xyz")
    assert result is None


def test_cache_set_get_roundtrip(tmp_db):
    """cache_set then cache_get returns same payload."""
    payload = {
        "summary": "Test summary",
        "keywords_injected": ["python", "sql"],
        "experience_blocks": [],
        "ats_notes": {"matched_keywords": ["python"], "missing_keywords": [], "ats_score_estimate": 50},
        "meta": {
            "offer_id": "BF-test",
            "profile_fingerprint": "fp_test",
            "prompt_version": "cv_v1",
            "cache_hit": False,
            "fallback_used": True,
        },
    }
    key = make_cache_key("fp_test", "BF-test", "cv_v1")

    ok = cache_set(
        key=key,
        doc_type="cv_v1",
        offer_id="BF-test",
        profile_fingerprint="fp_test",
        prompt_version="cv_v1",
        payload=payload,
    )
    assert ok is True

    retrieved = cache_get(key)
    assert retrieved is not None
    assert retrieved["summary"] == "Test summary"
    assert retrieved["keywords_injected"] == ["python", "sql"]


def test_cache_set_idempotent(tmp_db):
    """Writing the same key twice doesn't raise and returns the last value."""
    payload_v1 = {"summary": "v1", "keywords_injected": [], "experience_blocks": [],
                  "ats_notes": {"matched_keywords": [], "missing_keywords": [], "ats_score_estimate": 0},
                  "meta": {"offer_id": "X", "profile_fingerprint": "fp", "prompt_version": "cv_v1",
                           "cache_hit": False, "fallback_used": False}}
    payload_v2 = {**payload_v1, "summary": "v2"}
    key = make_cache_key("fp", "X", "cv_v1")

    cache_set(key=key, doc_type="cv_v1", offer_id="X",
              profile_fingerprint="fp", prompt_version="cv_v1", payload=payload_v1)
    cache_set(key=key, doc_type="cv_v1", offer_id="X",
              profile_fingerprint="fp", prompt_version="cv_v1", payload=payload_v2)

    result = cache_get(key)
    assert result["summary"] == "v2"


def test_cache_set_large_payload(tmp_db):
    """Large payload (10KB) stores and retrieves correctly."""
    big_summary = "x" * 500
    payload = {
        "summary": big_summary,
        "keywords_injected": [f"kw{i}" for i in range(12)],
        "experience_blocks": [],
        "ats_notes": {"matched_keywords": [], "missing_keywords": [], "ats_score_estimate": 0},
        "meta": {"offer_id": "BIG", "profile_fingerprint": "fp_big",
                 "prompt_version": "cv_v1", "cache_hit": False, "fallback_used": False},
    }
    key = make_cache_key("fp_big", "BIG", "cv_v1")
    cache_set(key=key, doc_type="cv_v1", offer_id="BIG",
              profile_fingerprint="fp_big", prompt_version="cv_v1", payload=payload)
    result = cache_get(key)
    assert result["summary"] == big_summary
