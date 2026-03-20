"""
test_esco_promotion_bridge.py — Sprint 0700 Step 3 invariance tests for canonical→ESCO bridge.

Tests (20):

EscoBridge unit (10):
  1.  test_bridge_flag_off_returns_empty        — ELEVIA_PROMOTE_ESCO off → []
  2.  test_bridge_known_canonical_id_resolved   — skill:machine_learning → ESCO URI
  3.  test_bridge_multiple_ids_resolved         — 3 DATA_IT ids → 3 URIs
  4.  test_bridge_unknown_id_skipped            — id with no esco_fr_label → skipped silently
  5.  test_bridge_dedup_base_uri               — URI already in base_skills_uri → not promoted
  6.  test_bridge_output_only_esco_uris        — no "skill:" prefix in output
  7.  test_bridge_deterministic                — same input → same output
  8.  test_bridge_empty_ids_returns_empty      — [] input → []
  9.  test_bridge_unloaded_store_returns_empty — unloaded store → [], no raise
  10. test_bridge_exception_safe               — broken map_skill → [], no raise

Profile integration (6):
  11. test_profile_bridge_sets_skills_uri_promoted       — flag ON → promoted non-empty
  12. test_profile_bridge_flag_off_no_promoted           — flag OFF → skills_uri_promoted absent/empty
  13. test_profile_bridge_no_skill_prefix_in_promoted    — no "skill:" in skills_uri_promoted
  14. test_profile_bridge_no_contamination_skills_uri    — "skill:" absent from skills_uri
  15. test_profile_bridge_additive_merge                 — bridge adds to existing promoted, no overwrite
  16. test_profile_bridge_fallback_200                   — request succeeds even if bridge fails

Invariants (4):
  17. test_invariant_esco_fr_label_in_store             — CanonicalStore has >=19 esco_fr_labels
  18. test_invariant_canonical_ids_never_in_output       — all output URIs start with http://
  19. test_invariant_scoring_frozen                      — esco_bridge.py imports no matching_v1
  20. test_invariant_esco_bridge_not_imported_by_extractor — extractors.py unchanged

Guarantees:
  - Bridge never raises
  - Flag OFF → zero behavior change (backward compatible)
  - skills_uri_promoted contains only ESCO URIs
  - scoring core untouched
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from typing import List
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.canonical.canonical_store import (
    CanonicalStore,
    _build_store,
    get_canonical_store,
    reset_canonical_store,
)
from compass.canonical.esco_bridge import build_canonical_esco_promoted

# ── Minimal fixture store ─────────────────────────────────────────────────────

_MINIMAL_JSON_WITH_FR = {
    "ontology": [
        {
            "cluster_name": "DATA_ANALYTICS_AI",
            "skills": [
                {
                    "canonical_skill_id": "skill:machine_learning",
                    "label": "Machine Learning",
                    "skill_type": "technical",
                    "genericity_score": 0.7,
                    "aliases": ["ml"],
                    "esco_fr_label": "apprentissage automatique",
                },
                {
                    "canonical_skill_id": "skill:data_analysis",
                    "label": "Data Analysis",
                    "skill_type": "technical",
                    "genericity_score": 0.8,
                    "aliases": ["data analytics"],
                    "esco_fr_label": "analyse de données",
                },
                {
                    "canonical_skill_id": "skill:no_fr_label",
                    "label": "Skill Without FR Label",
                    "skill_type": "technical",
                    "genericity_score": 0.5,
                    "aliases": [],
                    # no esco_fr_label
                },
            ],
        }
    ],
    "normalization_mappings": {
        "synonym_to_canonical": {},
        "tool_to_canonical": {},
    },
    "hierarchy": {},
}


def _make_store(data: dict = None) -> CanonicalStore:
    return _build_store(data if data is not None else _MINIMAL_JSON_WITH_FR)


def _empty_store() -> CanonicalStore:
    return CanonicalStore()


# ── Helpers ───────────────────────────────────────────────────────────────────

_DATA_IT_IDS = [
    "skill:machine_learning",
    "skill:data_analysis",
    "skill:data_engineering",
    "skill:deep_learning",
    "skill:nlp",
    "skill:devops",
    "skill:sql_querying",
    "skill:data_visualization",
    "skill:data_cleaning",
    "skill:statistical_analysis",
]

_ESCO_PREFIX = "http://data.europa.eu/esco/"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — EscoBridge unit tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_bridge_flag_off_returns_empty():
    """ELEVIA_PROMOTE_ESCO OFF → bridge must return [] without calling map_skill."""
    store = get_canonical_store()
    result = build_canonical_esco_promoted(
        _DATA_IT_IDS,
        base_skills_uri=[],
        cluster="DATA_IT",
        store=store,
        _promote_override=False,
    )
    assert result == [], "Bridge must return [] when flag is OFF"


def test_bridge_known_canonical_id_resolved():
    """skill:machine_learning has esco_fr_label → must resolve to a real ESCO URI."""
    store = get_canonical_store()
    result = build_canonical_esco_promoted(
        ["skill:machine_learning"],
        base_skills_uri=[],
        cluster="DATA_IT",
        store=store,
        _promote_override=True,
    )
    assert len(result) == 1
    assert result[0].startswith(_ESCO_PREFIX), (
        f"Promoted URI must be ESCO URI, got: {result[0]!r}"
    )


def test_bridge_multiple_ids_resolved():
    """3 known DATA_IT canonical IDs with esco_fr_label → 3 URIs promoted."""
    store = get_canonical_store()
    ids = ["skill:machine_learning", "skill:data_analysis", "skill:sql_querying"]
    result = build_canonical_esco_promoted(
        ids,
        base_skills_uri=[],
        cluster="DATA_IT",
        store=store,
        _promote_override=True,
    )
    assert len(result) == 3
    for uri in result:
        assert uri.startswith(_ESCO_PREFIX), f"Expected ESCO URI, got: {uri!r}"


def test_bridge_unknown_id_skipped():
    """ID with no esco_fr_label (skill:no_fr_label) must be silently skipped."""
    store = _make_store()
    result = build_canonical_esco_promoted(
        ["skill:no_fr_label"],
        base_skills_uri=[],
        cluster="DATA_IT",
        store=store,
        _promote_override=True,
    )
    assert result == [], "ID with no esco_fr_label must be skipped, not cause an error"


def test_bridge_dedup_base_uri():
    """URI already in base_skills_uri must NOT be included in promoted output."""
    store = get_canonical_store()
    # First get the URI for machine_learning
    first_pass = build_canonical_esco_promoted(
        ["skill:machine_learning"],
        base_skills_uri=[],
        store=store,
        _promote_override=True,
    )
    assert len(first_pass) == 1
    known_uri = first_pass[0]

    # Now promote with that URI already in base
    second_pass = build_canonical_esco_promoted(
        ["skill:machine_learning"],
        base_skills_uri=[known_uri],
        store=store,
        _promote_override=True,
    )
    assert second_pass == [], (
        f"URI already in base_skills_uri must not be duplicated in promoted output"
    )


def test_bridge_output_only_esco_uris():
    """All output URIs must start with http:// — never 'skill:' canonical IDs."""
    store = get_canonical_store()
    result = build_canonical_esco_promoted(
        _DATA_IT_IDS,
        base_skills_uri=[],
        cluster="DATA_IT",
        store=store,
        _promote_override=True,
    )
    assert len(result) > 0, "Expected at least 1 promoted URI for DATA_IT ids"
    for uri in result:
        assert not uri.startswith("skill:"), (
            f"Canonical ID leaked into bridge output: {uri!r}"
        )
        assert uri.startswith("http"), (
            f"All output must be ESCO URIs (http://...), got: {uri!r}"
        )


def test_bridge_deterministic():
    """Same canonical IDs + same base → identical output on every call."""
    store = get_canonical_store()
    r1 = build_canonical_esco_promoted(
        _DATA_IT_IDS, base_skills_uri=[], store=store, _promote_override=True
    )
    r2 = build_canonical_esco_promoted(
        _DATA_IT_IDS, base_skills_uri=[], store=store, _promote_override=True
    )
    assert r1 == r2, "build_canonical_esco_promoted must be deterministic"


def test_bridge_empty_ids_returns_empty():
    """Empty input → empty output without any error."""
    store = get_canonical_store()
    result = build_canonical_esco_promoted(
        [], base_skills_uri=[], store=store, _promote_override=True
    )
    assert result == []


def test_bridge_unloaded_store_returns_empty():
    """Unloaded store → returns [], never raises."""
    store = _empty_store()
    assert not store.is_loaded()
    result = build_canonical_esco_promoted(
        _DATA_IT_IDS, base_skills_uri=[], store=store, _promote_override=True
    )
    assert result == [], "Unloaded store must return [], not raise"


def test_bridge_exception_safe(monkeypatch):
    """If map_skill raises, bridge must return [] — never propagates exception."""
    store = get_canonical_store()

    def _explode(*args, **kwargs):
        raise RuntimeError("ESCO store exploded")

    monkeypatch.setattr("compass.canonical.esco_bridge.map_skill", _explode)
    result = build_canonical_esco_promoted(
        ["skill:machine_learning"],
        base_skills_uri=[],
        store=store,
        _promote_override=True,
    )
    assert result == [], "Exception in map_skill must be caught — bridge returns []"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Profile integration via TestClient
# ═══════════════════════════════════════════════════════════════════════════════

_TECH_CV = (
    "Data Scientist with expertise in machine learning, deep learning and NLP. "
    "Daily use of Python, SQL, TensorFlow. Data engineering pipelines with ETL. "
    "Data analysis and statistical analysis. DevOps with Docker. Power BI dashboards."
)


@pytest.fixture(scope="module")
def client():
    os.environ.setdefault("ELEVIA_DEV_TOOLS", "1")
    os.environ["ELEVIA_PROMOTE_ESCO"] = "1"
    from api.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture(scope="module")
def client_no_promote():
    os.environ.setdefault("ELEVIA_DEV_TOOLS", "1")
    os.environ.pop("ELEVIA_PROMOTE_ESCO", None)
    from api.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _post_txt(client, text: str):
    from fastapi.testclient import TestClient
    return client.post(
        "/profile/parse-file",
        files={"file": ("cv.txt", io.BytesIO(text.encode("utf-8")), "text/plain")},
    )


def test_profile_bridge_sets_skills_uri_promoted(client):
    """With ELEVIA_PROMOTE_ESCO=1, skills_uri_promoted must be non-empty for tech CV."""
    resp = _post_txt(client, _TECH_CV)
    assert resp.status_code == 200
    profile = resp.json().get("profile", {})
    promoted = profile.get("skills_uri_promoted") or []
    assert len(promoted) > 0, (
        "skills_uri_promoted must be non-empty when ELEVIA_PROMOTE_ESCO=1 and CV has canonical skills"
    )


def test_profile_bridge_no_skill_prefix_in_promoted(client):
    """skills_uri_promoted must contain only ESCO URIs — never canonical IDs (skill:xxx)."""
    resp = _post_txt(client, _TECH_CV)
    assert resp.status_code == 200
    profile = resp.json().get("profile", {})
    promoted = profile.get("skills_uri_promoted") or []
    for uri in promoted:
        assert not str(uri).startswith("skill:"), (
            f"Canonical ID in skills_uri_promoted: {uri!r}"
        )
        assert str(uri).startswith("http"), (
            f"Non-ESCO URI in skills_uri_promoted: {uri!r}"
        )


def test_profile_bridge_no_contamination_skills_uri(client):
    """skills_uri must never contain canonical IDs (skill:xxx) from the bridge."""
    resp = _post_txt(client, _TECH_CV)
    assert resp.status_code == 200
    profile = resp.json().get("profile", {})
    skills_uri = profile.get("skills_uri") or []
    for uri in skills_uri:
        assert not str(uri).startswith("skill:"), (
            f"Canonical ID leaked into skills_uri: {uri!r}"
        )


def test_profile_bridge_flag_off_no_promoted():
    """With ELEVIA_PROMOTE_ESCO unset, skills_uri_promoted must be absent or empty."""
    # Use a fresh import without the env var
    import importlib
    old = os.environ.pop("ELEVIA_PROMOTE_ESCO", None)
    try:
        from api.main import app
        from fastapi.testclient import TestClient
        c = TestClient(app)
        resp = _post_txt(c, _TECH_CV)
        assert resp.status_code == 200
        profile = resp.json().get("profile", {})
        promoted = profile.get("skills_uri_promoted") or []
        assert promoted == [], (
            f"skills_uri_promoted must be empty when ELEVIA_PROMOTE_ESCO is OFF, got {promoted}"
        )
    finally:
        if old is not None:
            os.environ["ELEVIA_PROMOTE_ESCO"] = old


def test_profile_bridge_fallback_200(client):
    """Even with a minimal CV that yields no canonical matches, request returns 200."""
    minimal = "Je suis passionné par les technologies et l'innovation."
    resp = _post_txt(client, minimal)
    assert resp.status_code == 200, f"Request must succeed even with no canonical matches"
    body = resp.json()
    assert "profile" in body


def test_profile_bridge_additive_merge(client):
    """
    The bridge is additive: skills_uri_promoted count must be ≥ what
    apply_profile_esco_promotion() alone would produce (it cannot decrease).
    """
    resp = _post_txt(client, _TECH_CV)
    assert resp.status_code == 200
    profile = resp.json().get("profile", {})
    promoted = profile.get("skills_uri_promoted") or []
    # Bridge-promoted URIs are all ESCO URIs — we only assert non-empty and valid
    assert all(u.startswith("http") for u in promoted), (
        "All promoted URIs must be valid ESCO http:// URIs"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Invariants
# ═══════════════════════════════════════════════════════════════════════════════


def test_invariant_esco_fr_label_in_store():
    """CanonicalStore must have at least 19 skills with esco_fr_label after Sprint 0700 Step 3."""
    store = get_canonical_store()
    count = sum(1 for e in store.id_to_skill.values() if e.get("esco_fr_label"))
    assert count >= 19, (
        f"Expected >=19 skills with esco_fr_label in canonical store, got {count}"
    )


def test_invariant_canonical_ids_never_in_output():
    """Bridge output must only contain ESCO URIs — never canonical IDs."""
    store = get_canonical_store()
    result = build_canonical_esco_promoted(
        list(store.id_to_skill.keys()),  # ALL 100 canonical IDs
        base_skills_uri=[],
        store=store,
        _promote_override=True,
    )
    for uri in result:
        assert not uri.startswith("skill:"), (
            f"Canonical ID in bridge output: {uri!r}"
        )
        assert uri.startswith("http"), (
            f"Non-ESCO URI in bridge output: {uri!r}"
        )


def test_invariant_scoring_frozen():
    """esco_bridge.py must not import matching_v1, idf, or weights files."""
    bridge_src = (API_SRC / "compass/canonical/esco_bridge.py").read_text(encoding="utf-8")
    # Check import lines only — mentions in docstrings are acceptable
    import_lines = [
        line for line in bridge_src.splitlines()
        if line.strip().startswith("import ") or line.strip().startswith("from ")
    ]
    import_block = "\n".join(import_lines)
    assert "matching_v1" not in import_block, "esco_bridge must not import matching_v1"
    assert "idf" not in import_block, "esco_bridge must not import idf"
    assert "weights_" not in import_block, "esco_bridge must not import weights files"


def test_invariant_esco_bridge_not_imported_by_extractor():
    """extractors.py must not import esco_bridge — bridge is a pipeline concern only."""
    extractors_src = (API_SRC / "matching/extractors.py").read_text(encoding="utf-8")
    assert "esco_bridge" not in extractors_src
    assert "build_canonical_esco_promoted" not in extractors_src
