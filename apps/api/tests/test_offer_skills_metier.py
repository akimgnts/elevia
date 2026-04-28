"""Tests for offer_skills_metier (v3 domain-aware extraction).

Covers strict validation rules: evidence requirement, skill_type whitelist,
CORE_METIER without evidence rejection, dedup, max-skills cap, and the
build/persist contract.

No network: AI calls are stubbed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT / "src"))

from api.utils.offer_skills_metier import (  # noqa: E402
    DropReason,
    ENRICHMENT_VERSION_METIER,
    SOURCE_METHOD_METIER,
    build_metier_rows,
    slugify_to_canonical_id,
    validate_skill_entries,
)


SAMPLE_TITLE = "Data Analyst V.I.E"
SAMPLE_DESCRIPTION = (
    "Build SQL queries on the customer warehouse. Develop Tableau dashboards. "
    "Maintain data quality reports. International environment."
)


def test_slugify_namespaced():
    assert slugify_to_canonical_id("SQL Querying") == "metier:sql_querying"
    assert slugify_to_canonical_id("Lead Qualification") == "metier:lead_qualification"
    assert slugify_to_canonical_id("") == ""
    assert slugify_to_canonical_id("   ") == ""


def test_validate_keeps_well_formed_entries():
    entries = [
        {"label": "SQL querying", "skill_type": "CORE_METIER", "evidence": "Build SQL queries", "confidence": 0.9},
        {"label": "Tableau", "skill_type": "TOOL", "evidence": "Develop Tableau dashboards", "confidence": 0.95},
    ]
    kept, dropped = validate_skill_entries(entries, title=SAMPLE_TITLE, description=SAMPLE_DESCRIPTION)
    assert len(kept) == 2
    assert dropped == []
    assert kept[0]["canonical_id"] == "metier:sql_querying"
    assert kept[0]["importance_level"] == "CORE"
    assert kept[1]["importance_level"] == "SECONDARY"


def test_validate_rejects_core_metier_without_evidence():
    entries = [
        {"label": "data modeling", "skill_type": "CORE_METIER", "evidence": "", "confidence": 0.8},
    ]
    kept, dropped = validate_skill_entries(entries, title=SAMPLE_TITLE, description=SAMPLE_DESCRIPTION)
    assert kept == []
    assert dropped[0]["reason"] == DropReason.CORE_METIER_WITHOUT_EVIDENCE


def test_validate_rejects_evidence_not_in_offer():
    entries = [
        {"label": "machine learning", "skill_type": "CORE_METIER", "evidence": "train models on TensorFlow", "confidence": 0.9},
    ]
    kept, dropped = validate_skill_entries(entries, title=SAMPLE_TITLE, description=SAMPLE_DESCRIPTION)
    assert kept == []
    assert dropped[0]["reason"] == DropReason.EVIDENCE_NOT_IN_OFFER


def test_validate_rejects_invalid_skill_type():
    entries = [
        {"label": "SQL", "skill_type": "OTHER", "evidence": "Build SQL queries", "confidence": 0.9},
    ]
    kept, dropped = validate_skill_entries(entries, title=SAMPLE_TITLE, description=SAMPLE_DESCRIPTION)
    assert kept == []
    assert dropped[0]["reason"] == DropReason.INVALID_TYPE


def test_validate_drops_duplicates():
    entries = [
        {"label": "SQL querying", "skill_type": "CORE_METIER", "evidence": "Build SQL queries", "confidence": 0.9},
        {"label": "SQL Querying", "skill_type": "CORE_METIER", "evidence": "Build SQL queries", "confidence": 0.8},
    ]
    kept, dropped = validate_skill_entries(entries, title=SAMPLE_TITLE, description=SAMPLE_DESCRIPTION)
    assert len(kept) == 1
    assert any(d["reason"] == DropReason.DUPLICATE for d in dropped)


def test_validate_caps_at_max_skills():
    entries = [
        {"label": f"skill {i}", "skill_type": "TOOL", "evidence": "Tableau", "confidence": 0.5}
        for i in range(8)
    ]
    kept, dropped = validate_skill_entries(entries, title=SAMPLE_TITLE, description=SAMPLE_DESCRIPTION)
    # All entries share the same evidence; dedup also kicks in via canonical_id slugs.
    # The MAX cap test is more useful with distinct slugs.
    distinct_entries = [
        {"label": f"skill alpha {i}", "skill_type": "TOOL", "evidence": "Tableau", "confidence": 0.5}
        for i in range(8)
    ]
    kept2, dropped2 = validate_skill_entries(distinct_entries, title=SAMPLE_TITLE, description=SAMPLE_DESCRIPTION)
    assert len(kept2) == 5
    assert any(d["reason"] == DropReason.EXCEEDS_LIMIT for d in dropped2)


def test_validate_handles_malformed_input():
    entries = [
        None,  # type: ignore[list-item]
        {"label": "", "skill_type": "TOOL", "evidence": "Tableau", "confidence": 0.5},
        {"skill_type": "TOOL", "evidence": "SQL queries", "confidence": 0.5},  # no label
        "not-a-dict",  # type: ignore[list-item]
    ]
    kept, dropped = validate_skill_entries(entries, title=SAMPLE_TITLE, description=SAMPLE_DESCRIPTION)
    assert kept == []
    assert len(dropped) == 4


def test_validate_evidence_match_is_case_insensitive():
    entries = [
        {"label": "SQL querying", "skill_type": "CORE_METIER", "evidence": "BUILD SQL QUERIES", "confidence": 0.9},
    ]
    kept, _ = validate_skill_entries(entries, title=SAMPLE_TITLE, description=SAMPLE_DESCRIPTION)
    assert len(kept) == 1


def test_build_metier_rows_with_stub_caller():
    def fake_caller(*, title, description, domain_tag):
        return {
            "skills": [
                {"label": "SQL querying", "skill_type": "CORE_METIER", "evidence": "Build SQL queries", "confidence": 0.9},
                {"label": "Tableau", "skill_type": "TOOL", "evidence": "Develop Tableau dashboards", "confidence": 0.95},
                {"label": "compliance", "skill_type": "NOISE", "evidence": "data quality reports", "confidence": 0.4},
            ]
        }

    rows, audit = build_metier_rows(
        offer_id=42,
        source="business_france",
        external_id="bf_42",
        title=SAMPLE_TITLE,
        description=SAMPLE_DESCRIPTION,
        domain_tag="data",
        ai_caller=fake_caller,
        content_hash="abc123",
    )
    assert len(rows) == 3
    assert rows[0]["enrichment_version"] == ENRICHMENT_VERSION_METIER
    assert rows[0]["source_method"] == SOURCE_METHOD_METIER
    assert {r["skill_type"] for r in rows} == {"CORE_METIER", "TOOL", "NOISE"}
    # Importance mapping: only CORE_METIER -> CORE
    assert [r["importance_level"] for r in rows if r["skill_type"] == "CORE_METIER"] == ["CORE"]
    assert all(r["importance_level"] == "SECONDARY" for r in rows if r["skill_type"] != "CORE_METIER")
    assert audit["kept_count"] == 3
    assert audit["dropped_count"] == 0
    assert audit["error"] is None


def test_build_metier_rows_handles_caller_error():
    def boom(*, title, description, domain_tag):
        raise RuntimeError("api down")

    rows, audit = build_metier_rows(
        offer_id=1,
        source="business_france",
        external_id="bf_1",
        title=SAMPLE_TITLE,
        description=SAMPLE_DESCRIPTION,
        domain_tag="data",
        ai_caller=boom,
    )
    assert rows == []
    assert audit["error"] and "api down" in audit["error"]


def test_build_metier_rows_drops_invalid_entries_silently():
    def fake_caller(*, title, description, domain_tag):
        return {
            "skills": [
                {"label": "data modeling", "skill_type": "CORE_METIER", "evidence": "", "confidence": 0.9},  # rejected
                {"label": "Tableau", "skill_type": "TOOL", "evidence": "Develop Tableau dashboards", "confidence": 0.9},
            ]
        }

    rows, audit = build_metier_rows(
        offer_id=7,
        source="business_france",
        external_id="bf_7",
        title=SAMPLE_TITLE,
        description=SAMPLE_DESCRIPTION,
        domain_tag="data",
        ai_caller=fake_caller,
    )
    assert len(rows) == 1
    assert rows[0]["skill_type"] == "TOOL"
    assert audit["dropped_count"] == 1
    assert audit["dropped"][0]["reason"] == DropReason.CORE_METIER_WITHOUT_EVIDENCE


def test_build_metier_rows_handles_empty_response():
    def empty(*, title, description, domain_tag):
        return {"skills": []}

    rows, audit = build_metier_rows(
        offer_id=9,
        source="business_france",
        external_id="bf_9",
        title=SAMPLE_TITLE,
        description=SAMPLE_DESCRIPTION,
        domain_tag="hr",
        ai_caller=empty,
    )
    assert rows == []
    assert audit["error"] is None
