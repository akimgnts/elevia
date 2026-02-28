"""
Tests for inbox cluster ladder: domain_mode gating + neighbor widening + bucket ordering.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes.inbox import _ADJACENCY, MIN_STRICT


# ── Unit tests (no DB) ────────────────────────────────────────────────────────

def test_adjacency_matrix_completeness():
    """Every cluster (except OTHER) is present in adjacency matrix."""
    from profile.profile_cluster import CLUSTERS
    for c in CLUSTERS:
        assert c in _ADJACENCY, f"{c!r} missing from _ADJACENCY"


def test_adjacency_symmetric_neighbour_check():
    """DATA_IT <-> ENGINEERING_INDUSTRY are mutual neighbours."""
    assert "ENGINEERING_INDUSTRY" in _ADJACENCY["DATA_IT"]
    assert "DATA_IT" in _ADJACENCY["ENGINEERING_INDUSTRY"]


def test_other_has_no_neighbours():
    assert _ADJACENCY["OTHER"] == []


def test_min_strict_positive():
    assert MIN_STRICT > 0


# ── Integration fixtures ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def profile_demo():
    fixtures_path = Path(__file__).parent.parent / "fixtures" / "profile_demo.json"
    with open(fixtures_path) as f:
        return json.load(f)


def _post_inbox(client, profile, domain_mode="in_domain", limit=20):
    return client.post(
        "/inbox",
        params={"domain_mode": domain_mode},
        json={
            "profile_id": "test-domain-ladder",
            "profile": profile,
            "min_score": 0,
            "limit": limit,
        },
    )


# ── Integration: strict mode (in_domain / strict) ────────────────────────────

def test_inbox_domain_mode_strict_response_shape(client, profile_demo):
    resp = _post_inbox(client, profile_demo, domain_mode="in_domain")
    assert resp.status_code == 200
    data = resp.json()
    meta = data.get("meta") or {}
    items = data.get("items") or []

    if not items:
        pytest.skip("No offers returned — DB may be empty")

    profile_cluster = meta.get("profile_cluster")
    assert profile_cluster is not None

    gating = meta.get("gating_mode")
    assert gating in ("IN_DOMAIN", "STRICT_PLUS_NEIGHBORS"), f"unexpected gating_mode: {gating!r}"

    # Ladder counts present
    assert isinstance(meta.get("strict_count"), int)
    assert isinstance(meta.get("neighbor_count"), int)
    assert isinstance(meta.get("out_count"), int)


def test_inbox_strict_mode_items_have_domain_bucket(client, profile_demo):
    resp = _post_inbox(client, profile_demo, domain_mode="in_domain")
    assert resp.status_code == 200
    items = resp.json().get("items") or []
    if not items:
        pytest.skip("No items")

    for item in items:
        assert item.get("domain_bucket") in ("strict", "neighbor"), (
            f"unexpected bucket {item.get('domain_bucket')!r} in strict mode"
        )


def test_inbox_in_domain_strict_items_have_matching_cluster(client, profile_demo):
    resp = _post_inbox(client, profile_demo, domain_mode="in_domain")
    assert resp.status_code == 200
    data = resp.json()
    meta = data.get("meta") or {}
    items = data.get("items") or []
    if not items:
        pytest.skip("No items")

    gating = meta.get("gating_mode")
    profile_cluster = meta.get("profile_cluster")
    neighbor_clusters = set(_ADJACENCY.get(profile_cluster or "", []))

    for item in items:
        oc = item.get("offer_cluster")
        bucket = item.get("domain_bucket")
        if gating == "IN_DOMAIN":
            # All items must be strict
            assert bucket == "strict", f"expected strict bucket, got {bucket!r}"
            assert oc == profile_cluster
        elif gating == "STRICT_PLUS_NEIGHBORS":
            # Items can be strict or neighbor (no "out" items)
            assert bucket in ("strict", "neighbor"), f"out item found in STRICT_PLUS_NEIGHBORS: {oc!r}"
            if bucket == "strict":
                assert oc == profile_cluster
            elif bucket == "neighbor":
                assert oc in neighbor_clusters or oc == "OTHER", f"unexpected neighbor cluster: {oc!r}"


def test_inbox_strict_bucket_before_neighbor_bucket(client, profile_demo):
    """Strict items must all appear before neighbor items (bucket ordering)."""
    resp = _post_inbox(client, profile_demo, domain_mode="in_domain", limit=50)
    assert resp.status_code == 200
    items = resp.json().get("items") or []
    if not items:
        pytest.skip("No items")

    buckets = [item.get("domain_bucket") for item in items]
    # Find last "strict" and first "neighbor"
    strict_positions = [i for i, b in enumerate(buckets) if b == "strict"]
    neighbor_positions = [i for i, b in enumerate(buckets) if b == "neighbor"]

    if strict_positions and neighbor_positions:
        assert max(strict_positions) < min(neighbor_positions), (
            "Strict items must precede neighbor items in the response"
        )


# ── Integration: all mode ─────────────────────────────────────────────────────

def test_inbox_all_mode_returns_out_bucket(client, profile_demo):
    resp = _post_inbox(client, profile_demo, domain_mode="all", limit=50)
    assert resp.status_code == 200
    data = resp.json()
    meta = data.get("meta") or {}
    items = data.get("items") or []

    assert meta.get("gating_mode") == "OUT_OF_DOMAIN"
    # All items have a domain_bucket assigned
    for item in items:
        assert item.get("domain_bucket") in ("strict", "neighbor", "out")


def test_inbox_all_mode_ge_strict_mode_count(client, profile_demo):
    """domain_mode=all always returns >= items than strict mode."""
    r_strict = _post_inbox(client, profile_demo, domain_mode="in_domain", limit=50)
    r_all = _post_inbox(client, profile_demo, domain_mode="all", limit=50)
    assert r_strict.status_code == 200
    assert r_all.status_code == 200
    assert len(r_all.json().get("items", [])) >= len(r_strict.json().get("items", []))


# ── Integration: bucket ordering within buckets (score DESC) ─────────────────

def test_inbox_items_within_strict_bucket_sorted_by_score_desc(client, profile_demo):
    resp = _post_inbox(client, profile_demo, domain_mode="in_domain", limit=50)
    assert resp.status_code == 200
    items = resp.json().get("items") or []
    if len(items) < 2:
        pytest.skip("Not enough items to test ordering")

    strict_scores = [item["score"] for item in items if item.get("domain_bucket") == "strict"]
    assert strict_scores == sorted(strict_scores, reverse=True), "Strict bucket not sorted by score DESC"


# ── Integration: meta ladder counts consistent ────────────────────────────────

def test_inbox_meta_ladder_counts_consistent(client, profile_demo):
    resp = _post_inbox(client, profile_demo, domain_mode="all", limit=100)
    assert resp.status_code == 200
    data = resp.json()
    meta = data.get("meta") or {}
    items = data.get("items") or []

    strict_from_items = sum(1 for i in items if i.get("domain_bucket") == "strict")
    neighbor_from_items = sum(1 for i in items if i.get("domain_bucket") == "neighbor")
    out_from_items = sum(1 for i in items if i.get("domain_bucket") == "out")

    # Meta counts may be larger (pre-limit), but strict_count should match if limit not hit
    if len(items) < 100:  # didn't hit limit → counts match exactly
        assert meta.get("strict_count") == strict_from_items
        assert meta.get("neighbor_count") == neighbor_from_items
        assert meta.get("out_count") == out_from_items


# ── Integration: domain_mode=strict is accepted (alias for in_domain) ─────────

def test_inbox_domain_mode_strict_accepted(client, profile_demo):
    resp = _post_inbox(client, profile_demo, domain_mode="strict")
    assert resp.status_code == 200
    meta = resp.json().get("meta") or {}
    assert meta.get("gating_mode") in ("IN_DOMAIN", "STRICT_PLUS_NEIGHBORS")
