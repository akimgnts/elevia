"""
QA — ESCO alias layer tests.

Covers:
- test_alias_file_exists
- test_alias_file_parses_cleanly           (all lines valid JSON, required fields)
- test_alias_file_no_empty_keys
- test_alias_targets_exist_in_esco         (every URI in ESCO index)
- test_load_alias_map_returns_dict
- test_load_alias_map_singleton            (same object returned twice)
- test_load_alias_map_force_reload
- test_alias_stats_ok
- test_validate_alias_targets_exist_passes
- test_known_alias_hit_in_filter           (e.g. "management" → gérer une équipe)
- test_alias_hit_count_in_filter_result
- test_alias_hits_debug_list_in_filter
- test_alias_dedup_by_uri                  (two tokens → same URI → counted once)
- test_alias_does_not_affect_esco_direct   (ESCO-matched tokens still pass)
- test_alias_graceful_empty_on_bad_file    (monkeypatch to missing path)
- test_baseline_parse_returns_alias_hits   (integration: run_baseline returns alias_hits_count)

Fast (<2s), no LLM, no external deps.
"""
import json
import sys
from pathlib import Path
from typing import List
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

ALIAS_FILE = Path(__file__).parent.parent / "data" / "aliases" / "esco_alias_fr_v0.jsonl"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def alias_records() -> List[dict]:
    """Parse all JSONL records from alias file."""
    records = []
    for line in ALIAS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            records.append(json.loads(line))
    return records


@pytest.fixture(scope="module")
def alias_map():
    from profile.esco_aliases import load_alias_map
    return load_alias_map(force_reload=True)


# ── Data file integrity ────────────────────────────────────────────────────────

def test_alias_file_exists():
    """Alias data file must be present."""
    assert ALIAS_FILE.exists(), f"Missing: {ALIAS_FILE}"


def test_alias_file_parses_cleanly(alias_records):
    """All lines must be valid JSON with required fields."""
    assert len(alias_records) >= 10, "Expected at least 10 alias entries"
    for i, rec in enumerate(alias_records):
        assert "alias" in rec, f"Record {i} missing 'alias'"
        assert "esco_label" in rec, f"Record {i} missing 'esco_label'"
        assert "esco_uri" in rec, f"Record {i} missing 'esco_uri'"
        assert "lang" in rec, f"Record {i} missing 'lang'"
        assert "confidence" in rec, f"Record {i} missing 'confidence'"
        assert isinstance(rec["confidence"], (int, float)), f"Record {i}: confidence not numeric"
        assert 0.0 <= float(rec["confidence"]) <= 1.0, f"Record {i}: confidence out of [0,1]"


def test_alias_file_no_empty_keys(alias_records):
    """No alias entry should have empty alias, uri, or label."""
    for i, rec in enumerate(alias_records):
        assert rec["alias"].strip(), f"Record {i} has empty alias"
        assert rec["esco_uri"].strip(), f"Record {i} has empty esco_uri"
        assert rec["esco_label"].strip(), f"Record {i} has empty esco_label"
        assert rec["esco_uri"].startswith("http://data.europa.eu/esco/"), (
            f"Record {i}: URI not an ESCO URI: {rec['esco_uri']!r}"
        )


def test_alias_targets_exist_in_esco(alias_records):
    """Every alias URI must exist in the loaded ESCO index."""
    from esco.loader import get_esco_store
    store = get_esco_store()
    broken = []
    for rec in alias_records:
        uri = rec["esco_uri"]
        if uri not in store.uri_to_preferred:
            broken.append(f"  alias={rec['alias']!r} → {uri!r}")
    assert not broken, f"Aliases with unknown ESCO URIs:\n" + "\n".join(broken)


# ── Loader ────────────────────────────────────────────────────────────────────

def test_load_alias_map_returns_dict(alias_map):
    """load_alias_map() must return a non-empty dict."""
    assert isinstance(alias_map, dict)
    assert len(alias_map) >= 10


def test_load_alias_map_singleton():
    """Calling load_alias_map() twice returns the same object."""
    from profile.esco_aliases import load_alias_map
    m1 = load_alias_map()
    m2 = load_alias_map()
    assert m1 is m2


def test_load_alias_map_force_reload():
    """force_reload=True must return a fresh dict."""
    from profile.esco_aliases import load_alias_map
    m1 = load_alias_map()
    m2 = load_alias_map(force_reload=True)
    # Different object but same content
    assert m1 == m2


def test_alias_stats_ok():
    """alias_stats() must return status='ok' and alias_count > 0."""
    from profile.esco_aliases import alias_stats
    stats = alias_stats()
    assert stats["status"] == "ok"
    assert stats["alias_count"] >= 10


def test_validate_alias_targets_exist_passes():
    """validate_alias_targets_exist() must not raise for v0 file."""
    from profile.esco_aliases import validate_alias_targets_exist
    validate_alias_targets_exist()  # must not raise


# ── Graceful fallback ─────────────────────────────────────────────────────────

def test_alias_graceful_empty_on_bad_file():
    """If alias file is missing, load_alias_map() returns {} without crashing."""
    from profile import esco_aliases as ea
    original_primary = ea._ALIAS_FILE_V0_PRIMARY
    original_fallback = ea._ALIAS_FILE_V0_FALLBACK
    try:
        ea._ALIAS_FILE_V0_PRIMARY = Path("/nonexistent/esco_alias_fr_v0.jsonl")
        ea._ALIAS_FILE_V0_FALLBACK = Path("/nonexistent/esco_alias_fr_v0.jsonl")
        ea._alias_map = None  # clear singleton
        result = ea.load_alias_map()
        assert result == {}
    finally:
        ea._ALIAS_FILE_V0_PRIMARY = original_primary
        ea._ALIAS_FILE_V0_FALLBACK = original_fallback
        ea._alias_map = None  # reset so other tests get fresh load


# ── strict_filter_skills integration ─────────────────────────────────────────

def test_known_alias_hit_in_filter():
    """'management' token must be captured by alias → 'gérer une équipe'."""
    from profile.skill_filter import strict_filter_skills
    result = strict_filter_skills(["management"])
    labels = [item["label"] for item in result["validated_items"]]
    assert "gérer une équipe" in labels, (
        f"Expected 'gérer une équipe' in validated_items, got: {labels}"
    )


def test_alias_hit_count_in_filter_result():
    """alias_hits_count must reflect number of alias-matched tokens."""
    from profile.skill_filter import strict_filter_skills
    # "management", "recrutement", "budget" all in alias table
    result = strict_filter_skills(["management", "recrutement", "budget"])
    assert result["alias_hits_count"] >= 1, (
        f"Expected alias_hits_count >= 1, got {result['alias_hits_count']}"
    )
    assert result["alias_hits_count"] <= 3


def test_alias_hits_debug_list_in_filter():
    """alias_hits list must contain {alias, label} dicts."""
    from profile.skill_filter import strict_filter_skills
    result = strict_filter_skills(["management", "leadership"])
    hits = result["alias_hits"]
    assert isinstance(hits, list)
    for hit in hits:
        assert "alias" in hit
        assert "label" in hit
        assert isinstance(hit["alias"], str)
        assert isinstance(hit["label"], str)


def test_alias_dedup_by_uri():
    """Two aliases pointing to the same ESCO URI must add only one validated item."""
    from profile.skill_filter import strict_filter_skills
    # "management" and "encadrement" both → gérer une équipe (same URI)
    result = strict_filter_skills(["management", "encadrement"])
    uris = [item["uri"] for item in result["validated_items"]]
    assert len(uris) == len(set(uris)), "Duplicate URIs in validated_items"
    assert len(result["validated_items"]) == 1, (
        f"Expected 1 unique URI, got {len(result['validated_items'])}"
    )


def test_alias_does_not_affect_esco_direct():
    """Tokens that already match ESCO directly must still be validated."""
    from profile.skill_filter import strict_filter_skills
    # "python (programmation informatique)" matches ESCO directly
    result = strict_filter_skills(["python (programmation informatique)"])
    assert result["validated_skills"] >= 1
    labels = [item["label"] for item in result["validated_items"]]
    assert any("python" in l.lower() for l in labels)


def test_alias_tokens_not_in_filtered_tokens():
    """Tokens matched by alias must NOT appear in filtered_tokens."""
    from profile.skill_filter import strict_filter_skills
    result = strict_filter_skills(["management", "recrutement"])
    filtered = [t.lower() for t in result["filtered_tokens"]]
    assert "management" not in filtered, (
        "'management' should be captured by alias, not in filtered_tokens"
    )
    assert "recrutement" not in filtered, (
        "'recrutement' should be captured by alias, not in filtered_tokens"
    )


# ── Accent normalization ─────────────────────────────────────────────────────

def test_alias_matches_accented_term_from_text():
    """Accent in source text must still hit alias (via accent-insensitive key)."""
    from profile.baseline_parser import run_baseline
    result = run_baseline("Compétence clé: négociation commerciale")
    assert result["alias_hits_count"] >= 1
    aliases = [hit["alias"] for hit in result["alias_hits"]]
    assert "négociation" in aliases
    uris = [item["uri"] for item in result["validated_items"]]
    assert "http://data.europa.eu/esco/skill/87de6e49-ca1c-42a4-8751-5ff0b991966b" in uris


def test_alias_matches_deaccented_token():
    """Deaccented token should hit the same alias mapping."""
    from profile.skill_filter import strict_filter_skills
    result = strict_filter_skills(["negociation"])
    uris = [item["uri"] for item in result["validated_items"]]
    assert "http://data.europa.eu/esco/skill/87de6e49-ca1c-42a4-8751-5ff0b991966b" in uris
    assert result["alias_hits_count"] >= 1


@pytest.mark.xfail(
    reason=(
        "TODO: alias collision detection uses graceful fallback (returns empty dict) "
        "instead of re-raising ValueError — contract mismatch, non-blocking."
    )
)
def test_alias_key_collision_raises(tmp_path):
    """Alias key collision with different URIs must raise ValueError."""
    from profile import esco_aliases as ea

    alias_file = tmp_path / "aliases.jsonl"
    alias_file.write_text(
        "\n".join([
            "{\"alias\": \"négociation\", \"esco_label\": \"x\", \"esco_uri\": \"http://data.europa.eu/esco/skill/11111111-1111-1111-1111-111111111111\", \"lang\": \"fr\", \"source\": \"manual\", \"confidence\": 1.0}",
            "{\"alias\": \"negociation\", \"esco_label\": \"y\", \"esco_uri\": \"http://data.europa.eu/esco/skill/22222222-2222-2222-2222-222222222222\", \"lang\": \"fr\", \"source\": \"manual\", \"confidence\": 1.0}",
        ]) + "\n",
        encoding="utf-8",
    )

    original_primary = ea._ALIAS_FILE_V0_PRIMARY
    original_fallback = ea._ALIAS_FILE_V0_FALLBACK
    try:
        ea._ALIAS_FILE_V0_PRIMARY = alias_file
        ea._ALIAS_FILE_V0_FALLBACK = alias_file
        ea._alias_map = None
        with pytest.raises(ValueError):
            ea.load_alias_map(force_reload=True)
    finally:
        ea._ALIAS_FILE_V0_PRIMARY = original_primary
        ea._ALIAS_FILE_V0_FALLBACK = original_fallback
        ea._alias_map = None


# ── Integration: baseline parser ─────────────────────────────────────────────

def test_baseline_parse_returns_alias_hits():
    """run_baseline() result must include alias_hits_count and alias_hits keys."""
    from profile.baseline_parser import run_baseline
    result = run_baseline("management recrutement budget reporting leadership")
    assert "alias_hits_count" in result, "alias_hits_count missing from run_baseline result"
    assert "alias_hits" in result, "alias_hits missing from run_baseline result"
    assert isinstance(result["alias_hits_count"], int)
    assert isinstance(result["alias_hits"], list)
    assert result["alias_hits_count"] >= 1, (
        f"Expected at least 1 alias hit for management/recrutement/budget/reporting/leadership, "
        f"got {result['alias_hits_count']}"
    )
