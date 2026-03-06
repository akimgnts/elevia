"""
test_esco_promotion_scaffold.py — Sprint 6 Step 1 invariance tests.

Tests (9):
  1. test_flag_off_no_promoted    — flag OFF, no promoted field → frozenset(base)
  2. test_flag_off_with_promoted  — flag OFF, promoted present → frozenset(base) unchanged
  3. test_flag_on_promoted_empty  — flag ON, promoted=[] → frozenset(base) unchanged
  4. test_flag_on_promoted_absent — flag ON, key missing → frozenset(base) unchanged
  5. test_flag_on_adds_promoted   — flag ON + non-empty promoted → union
  6. test_flag_on_no_duplication  — promoted URIs already in base not duplicated
  7. test_flag_on_intra_promoted_dedup — promoted list itself has dupes → deduped
  8. test_get_promote_trace       — trace dict has required keys + correct counts
  9. test_frozen_files_untouched  — matching_v1.py / idf.py not modified by Step 1

Invariant guarantee:
  build_effective_skills_uri(base, profile, _promote_override=False)
  == frozenset(base)  for all inputs
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass.profile.profile_effective_skills import (
    build_effective_skills_uri,
    get_promote_trace,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

BASE = [
    "http://data.europa.eu/esco/skill/a1",
    "http://data.europa.eu/esco/skill/b2",
    "compass:skill:DATA_IT:python",
]

PROMOTED = [
    "http://data.europa.eu/esco/skill/c3",
    "http://data.europa.eu/esco/skill/d4",
]


# ── Test 1: flag OFF, no promoted field ───────────────────────────────────────


def test_flag_off_no_promoted():
    profile = {"skills_uri": BASE}
    result = build_effective_skills_uri(BASE, profile, _promote_override=False)
    assert result == frozenset(BASE), "Flag OFF must return frozenset(base_list) unchanged"
    assert isinstance(result, frozenset)


# ── Test 2: flag OFF, promoted present — must be ignored ──────────────────────


def test_flag_off_with_promoted():
    profile = {"skills_uri": BASE, "skills_uri_promoted": PROMOTED}
    result = build_effective_skills_uri(BASE, profile, _promote_override=False)
    assert result == frozenset(BASE), (
        "Flag OFF must ignore skills_uri_promoted entirely"
    )
    for uri in PROMOTED:
        assert uri not in result, f"Promoted URI {uri} must not appear when flag OFF"


# ── Test 3: flag ON, promoted empty list ──────────────────────────────────────


def test_flag_on_promoted_empty():
    profile = {"skills_uri": BASE, "skills_uri_promoted": []}
    result = build_effective_skills_uri(BASE, profile, _promote_override=True)
    assert result == frozenset(BASE), "Flag ON + empty promoted → still frozenset(base)"


# ── Test 4: flag ON, promoted key absent ──────────────────────────────────────


def test_flag_on_promoted_absent():
    profile = {"skills_uri": BASE}  # no skills_uri_promoted key
    result = build_effective_skills_uri(BASE, profile, _promote_override=True)
    assert result == frozenset(BASE), "Flag ON + missing key → still frozenset(base)"


# ── Test 5: flag ON + non-empty promoted → union ─────────────────────────────


def test_flag_on_adds_promoted():
    profile = {"skills_uri": BASE, "skills_uri_promoted": PROMOTED}
    result = build_effective_skills_uri(BASE, profile, _promote_override=True)
    expected = frozenset(BASE) | frozenset(PROMOTED)
    assert result == expected, (
        f"Flag ON must produce union.\nExpected: {expected}\nGot: {result}"
    )
    assert len(result) == len(BASE) + len(PROMOTED)


# ── Test 6: no duplication of URIs already in base ───────────────────────────


def test_flag_on_no_duplication():
    overlap = BASE[0]  # URI already in base
    profile = {
        "skills_uri": BASE,
        "skills_uri_promoted": [overlap, PROMOTED[0]],
    }
    result = build_effective_skills_uri(BASE, profile, _promote_override=True)
    uri_list = list(result)
    assert uri_list.count(overlap) == 1, (
        f"Overlap URI {overlap} must appear exactly once in effective set"
    )
    assert len(result) == len(BASE) + 1, (
        "Effective set must be base + 1 new promoted URI (overlap excluded)"
    )


# ── Test 7: intra-promoted deduplication ─────────────────────────────────────


def test_flag_on_intra_promoted_dedup():
    dup_promoted = [PROMOTED[0], PROMOTED[0], PROMOTED[1]]  # PROMOTED[0] appears twice
    profile = {"skills_uri": BASE, "skills_uri_promoted": dup_promoted}
    result = build_effective_skills_uri(BASE, profile, _promote_override=True)
    result_list = list(result)
    assert result_list.count(PROMOTED[0]) == 1, (
        "Duplicate within promoted list must be deduplicated"
    )
    assert len(result) == len(BASE) + 2  # only 2 unique promoted URIs added


# ── Test 8: get_promote_trace structure ──────────────────────────────────────


def test_get_promote_trace_structure():
    profile = {"skills_uri": BASE, "skills_uri_promoted": PROMOTED}
    trace = get_promote_trace(BASE, profile, _promote_override=True)
    assert "promote_enabled" in trace
    assert "promoted_count" in trace
    assert "effective_count" in trace
    assert "added_count" in trace
    assert trace["promote_enabled"] is True
    assert trace["promoted_count"] == len(PROMOTED)
    assert trace["added_count"] == len(PROMOTED)
    assert trace["effective_count"] == len(BASE) + len(PROMOTED)


def test_get_promote_trace_flag_off():
    profile = {"skills_uri": BASE, "skills_uri_promoted": PROMOTED}
    trace = get_promote_trace(BASE, profile, _promote_override=False)
    assert trace["promote_enabled"] is False
    assert trace["added_count"] == 0
    assert trace["effective_count"] == len(BASE)


# ── Test 9: frozen files untouched ───────────────────────────────────────────


def test_frozen_files_untouched():
    """
    Structural safeguard: Sprint 6 Step 1 must not modify frozen scoring files.
    We verify by importing them and checking that the promotion helper is NOT
    imported at module level from within them (which would couple the files).
    """
    frozen_paths = [
        REPO_ROOT / "src" / "matching" / "matching_v1.py",
        REPO_ROOT / "src" / "matching" / "idf.py",
    ]
    for path in frozen_paths:
        assert path.exists(), f"Frozen file missing: {path}"
        content = path.read_text(encoding="utf-8")
        assert "profile_effective_skills" not in content, (
            f"Frozen file {path.name} must NOT import profile_effective_skills"
        )
        assert "skills_uri_promoted" not in content, (
            f"Frozen file {path.name} must NOT reference skills_uri_promoted"
        )
        assert "ELEVIA_PROMOTE_ESCO" not in content, (
            f"Frozen file {path.name} must NOT read ELEVIA_PROMOTE_ESCO"
        )


# ── Test 10: malformed input safety ──────────────────────────────────────────


def test_malformed_profile_none():
    """None profile must not raise — returns frozenset(base)."""
    result = build_effective_skills_uri(BASE, None, _promote_override=True)  # type: ignore[arg-type]
    assert result == frozenset(BASE)


def test_malformed_profile_wrong_type():
    """Non-dict profile must not raise."""
    for bad in ("string", 42, [], False):
        result = build_effective_skills_uri(BASE, bad, _promote_override=True)  # type: ignore[arg-type]
        assert result == frozenset(BASE), f"Wrong-type profile {type(bad)} must fall back to frozenset(base)"


def test_malformed_promoted_wrong_type():
    """Non-list skills_uri_promoted must be silently ignored."""
    for bad_value in ("http://esco/x", 42, {"uri": "x"}, True):
        profile = {"skills_uri_promoted": bad_value}
        result = build_effective_skills_uri(BASE, profile, _promote_override=True)
        assert result == frozenset(BASE), (
            f"Non-list promoted value {type(bad_value)} must fall back to frozenset(base)"
        )


def test_malformed_promoted_mixed_types():
    """Promoted list with non-string entries — only strings processed."""
    profile = {
        "skills_uri_promoted": [
            None,
            42,
            {"uri": "http://esco/x"},
            "http://data.europa.eu/esco/skill/valid",
            "",        # empty string — skipped
            "  ",      # whitespace-only — skipped
        ]
    }
    result = build_effective_skills_uri(BASE, profile, _promote_override=True)
    assert "http://data.europa.eu/esco/skill/valid" in result
    assert len(result) == len(BASE) + 1  # only the one valid non-empty string added


def test_malformed_base_list_none():
    """None base_list must not raise."""
    result = build_effective_skills_uri(None, {}, _promote_override=False)  # type: ignore[arg-type]
    assert result == frozenset()


# ── Test 11: OBS trace not wired into normal API response path ────────────────


def test_obs_trace_not_in_endpoint_sources():
    """
    Structural: get_promote_trace must not be imported or called from any
    endpoint or route file (it is for debug/explain mode only).
    Ensures the OBS trace never silently changes the API contract.
    """
    route_dirs = [
        REPO_ROOT / "src" / "api" / "routes",
        REPO_ROOT / "src" / "api" / "utils",
    ]
    for route_dir in route_dirs:
        if not route_dir.exists():
            continue
        for py_file in route_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            assert "get_promote_trace" not in content, (
                f"{py_file.name} must not call get_promote_trace() in normal response path. "
                "Wire it only under an explicit debug/explain mode check."
            )


# ── Integration: extract_profile respects the flag ───────────────────────────


def test_extract_profile_flag_off_identical(monkeypatch):
    """
    Full stack: extract_profile() with flag OFF produces the same skills_uri
    as it did before Sprint 6 (baseline frozenset from profile["skills_uri"]).
    """
    monkeypatch.delenv("ELEVIA_PROMOTE_ESCO", raising=False)

    from matching.extractors import extract_profile

    profile = {
        "id": "test-001",
        "skills": ["Python", "SQL"],
        "skills_uri": [
            "http://data.europa.eu/esco/skill/a1",
            "http://data.europa.eu/esco/skill/b2",
        ],
        "skills_uri_promoted": [
            "http://data.europa.eu/esco/skill/c3",  # would be added if flag ON
        ],
    }
    extracted = extract_profile(profile)
    assert "http://data.europa.eu/esco/skill/c3" not in extracted.skills_uri, (
        "Flag OFF: promoted URI must NOT appear in extracted.skills_uri"
    )
    assert frozenset([
        "http://data.europa.eu/esco/skill/a1",
        "http://data.europa.eu/esco/skill/b2",
    ]) == extracted.skills_uri


def test_extract_profile_flag_on_union(monkeypatch):
    """
    Full stack: extract_profile() with flag ON adds promoted URIs to skills_uri.
    """
    monkeypatch.setenv("ELEVIA_PROMOTE_ESCO", "1")

    from matching.extractors import extract_profile

    profile = {
        "id": "test-002",
        "skills": ["Python"],
        "skills_uri": [
            "http://data.europa.eu/esco/skill/a1",
        ],
        "skills_uri_promoted": [
            "http://data.europa.eu/esco/skill/c3",
            "http://data.europa.eu/esco/skill/d4",
        ],
    }
    extracted = extract_profile(profile)
    assert "http://data.europa.eu/esco/skill/c3" in extracted.skills_uri, (
        "Flag ON: promoted URI must appear in extracted.skills_uri"
    )
    assert "http://data.europa.eu/esco/skill/d4" in extracted.skills_uri
    assert "http://data.europa.eu/esco/skill/a1" in extracted.skills_uri
    assert len(extracted.skills_uri) == 3
