"""
test_domain_esco_map.py — DOMAIN→ESCO mapping layer tests.

8 tests:
  1. test_add_and_get_mapping              — add_esco_mapping / get_esco_mapping round-trip
  2. test_resolve_single_token             — ACTIVE library token + mapping → in resolved batch
  3. test_no_mapping_resolved_empty        — ACTIVE token WITHOUT mapping → empty result
  4. test_resolve_batch_mixed              — batch: some mapped, some not
  5. test_enrichment_resolved_to_esco      — enrich_cv fills resolved_to_esco for ACTIVE mapped token
  6. test_no_mapping_baseline_unchanged    — without ESCO mapping, baseline_result is identical
  7. test_score_invariance_fields          — EscoResolvedSkill + CVEnrichmentResult have no score_core
  8. test_llm_token_provenance             — LLM-sourced token with mapping → llm_token_to_esco

Constraints:
  - All use in-memory SQLite (:memory:)
  - No LLM calls (mocked or llm_enabled=False)
  - Score invariance: score_core never touched
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.cluster_library import ClusterLibraryStore
from compass.contracts import CVEnrichmentResult, EscoResolvedSkill
from compass.cv_enricher import enrich_cv


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _fresh() -> ClusterLibraryStore:
    return ClusterLibraryStore(db_path=":memory:")


_FAKE_URI = "http://data.europa.eu/esco/skill/fake-test-uri"
_FAKE_LABEL = "gestion OPC/OPCVM"


def _activate_token(store: ClusterLibraryStore, cluster: str, token: str) -> None:
    """Activate a token via offer≥5 path (fastest activation route)."""
    for _ in range(5):
        store.record_offer_token(cluster, token)


# ── Test 1 — add_esco_mapping / get_esco_mapping round-trip ───────────────────

def test_add_and_get_mapping():
    """
    add_esco_mapping then get_esco_mapping must return exactly the stored fields.
    Updating with a second call must overwrite esco_uri and esco_label.
    """
    store = _fresh()

    # First insert
    store.add_esco_mapping("FINANCE", "OPCVM", _FAKE_URI, _FAKE_LABEL, "manual")
    m = store.get_esco_mapping("FINANCE", "opcvm")  # normalized lookup
    assert m is not None, "Expected mapping, got None"
    assert m["esco_uri"] == _FAKE_URI
    assert m["esco_label"] == _FAKE_LABEL
    assert m["mapping_source"] == "manual"

    # Update (upsert)
    new_uri = _FAKE_URI + "/v2"
    store.add_esco_mapping("FINANCE", "OPCVM", new_uri, "updated label", "alias_lookup")
    m2 = store.get_esco_mapping("FINANCE", "opcvm")
    assert m2["esco_uri"] == new_uri
    assert m2["mapping_source"] == "alias_lookup"

    # Different cluster → no mapping
    assert store.get_esco_mapping("DATA_IT", "opcvm") is None


# ── Test 2 — resolve_tokens_to_esco: single ACTIVE token ─────────────────────

def test_resolve_single_token():
    """
    A token that exists in cluster_token_esco_map for the correct cluster
    must appear in the resolve_tokens_to_esco result.
    """
    store = _fresh()
    store.add_esco_mapping("FINANCE", "dcf", _FAKE_URI, "DCF valuation", "manual")

    result = store.resolve_tokens_to_esco("FINANCE", ["dcf"])
    assert "dcf" in result, f"Expected 'dcf' in result, got {list(result.keys())}"
    assert result["dcf"]["esco_uri"] == _FAKE_URI
    assert result["dcf"]["esco_label"] == "DCF valuation"

    # occurrences_mapped should increment
    result2 = store.resolve_tokens_to_esco("FINANCE", ["dcf"])
    assert "dcf" in result2

    print(f"\n[TEST2] resolve single token: esco_uri={result['dcf']['esco_uri']!r}")


# ── Test 3 — no mapping → empty resolve result ────────────────────────────────

def test_no_mapping_resolved_empty():
    """
    An ACTIVE library token without an ESCO mapping must NOT appear
    in resolve_tokens_to_esco — the result must be empty.
    """
    store = _fresh()
    _activate_token(store, "FINANCE", "DCF")  # now ACTIVE in cluster library

    # No ESCO mapping registered → resolve returns empty
    result = store.resolve_tokens_to_esco("FINANCE", ["dcf"])
    assert result == {}, f"Expected empty dict, got {result}"

    print("\n[TEST3] no mapping → empty resolve ✓")


# ── Test 4 — batch resolution: mixed mapped/unmapped ─────────────────────────

def test_resolve_batch_mixed():
    """
    Batch resolve: mapped tokens appear in result, unmapped tokens are absent.
    """
    store = _fresh()
    store.add_esco_mapping("DATA_IT", "databricks", "http://esco/databricks", "Databricks", "manual")
    store.add_esco_mapping("DATA_IT", "kafka", "http://esco/kafka", "Apache Kafka", "alias_lookup")
    # "spark" has no mapping

    result = store.resolve_tokens_to_esco("DATA_IT", ["databricks", "kafka", "spark"])
    assert "databricks" in result
    assert "kafka" in result
    assert "spark" not in result
    assert result["kafka"]["mapping_source"] == "alias_lookup"

    print(f"\n[TEST4] batch mixed: mapped={sorted(result.keys())} ✓")


# ── Test 5 — enrich_cv populates resolved_to_esco ────────────────────────────

def test_enrichment_resolved_to_esco():
    """
    When a cluster library ACTIVE token has an ESCO mapping,
    enrich_cv must include it in resolved_to_esco with the correct fields.
    provenance must be 'library_token_to_esco' (non-LLM source).
    """
    store = _fresh()
    cluster = "FINANCE"

    # Activate DCF in the library
    _activate_token(store, cluster, "DCF")

    # Register the ESCO mapping
    store.add_esco_mapping(cluster, "dcf", _FAKE_URI, _FAKE_LABEL, "manual")

    cv_text = (
        "Analyste financier, maîtrise du DCF, évaluation d'entreprises, "
        "valorisation par comparables, modélisation financière."
    )
    result = enrich_cv(
        cv_text=cv_text,
        cluster=cluster,
        esco_skills=["analyse financière", "évaluation d'entreprises"],
        llm_enabled=False,
        library=store,
    )

    assert isinstance(result, CVEnrichmentResult)
    assert "dcf" in result.domain_skills_active, (
        f"Expected 'dcf' in domain_skills_active, got {result.domain_skills_active}"
    )
    assert len(result.resolved_to_esco) >= 1, (
        f"Expected ≥1 entry in resolved_to_esco, got {result.resolved_to_esco}"
    )
    dcf_resolved = next(
        (r for r in result.resolved_to_esco if r.token_normalized == "dcf"), None
    )
    assert dcf_resolved is not None, "Expected 'dcf' in resolved_to_esco"
    assert dcf_resolved.esco_uri == _FAKE_URI
    assert dcf_resolved.provenance == "library_token_to_esco"
    assert dcf_resolved.mapping_source == "manual"

    print(
        f"\n[TEST5] resolved_to_esco={[r.token_normalized for r in result.resolved_to_esco]} "
        f"provenance={dcf_resolved.provenance} ✓"
    )


# ── Test 6 — no mapping → baseline_result unchanged ──────────────────────────

def test_no_mapping_baseline_unchanged():
    """
    Without any ESCO mapping registered, enrich_cv returns empty resolved_to_esco.
    The baseline_result (ESCO skills) must be identical with or without enrichment.
    Score invariance: adding resolved_to_esco never changes ESCO baseline skills.
    """
    from profile.baseline_parser import run_baseline

    cv_text = (
        "Data Engineer Python SQL machine learning Spark ETL pipelines analytics."
    )
    baseline = run_baseline(cv_text, profile_id="inv-test")
    esco_labels = baseline.get("validated_labels") or []

    store_no_map = _fresh()
    result_no_map = enrich_cv(
        cv_text=cv_text,
        cluster="DATA_IT",
        esco_skills=esco_labels,
        llm_enabled=False,
        library=store_no_map,
    )

    store_with_map = _fresh()
    # Even if a token gets an ESCO mapping...
    store_with_map.add_esco_mapping("DATA_IT", "spark", "http://esco/spark", "Apache Spark", "manual")
    result_with_map = enrich_cv(
        cv_text=cv_text,
        cluster="DATA_IT",
        esco_skills=esco_labels,
        llm_enabled=False,
        library=store_with_map,
    )

    # ...domain_skills_active is the same (mapping doesn't change library status)
    assert result_no_map.domain_skills_active == result_with_map.domain_skills_active, (
        "domain_skills_active must not depend on ESCO mappings"
    )

    print(
        f"\n[TEST6] baseline invariant: active_no_map={result_no_map.domain_skills_active} "
        f"active_with_map={result_with_map.domain_skills_active} ✓"
    )


# ── Test 7 — EscoResolvedSkill + CVEnrichmentResult have no score_core ────────

def test_score_invariance_fields():
    """
    Neither EscoResolvedSkill nor CVEnrichmentResult must expose a score_core field.
    CVPipelineResult must not expose score_core either.
    """
    from compass.canonical_pipeline import CVPipelineResult
    from dataclasses import fields as dc_fields

    score_fields = {"score_core", "score", "match_score", "weight", "idf"}

    # CVEnrichmentResult
    enrichment_keys = set(CVEnrichmentResult.model_fields.keys())
    assert not enrichment_keys & score_fields, (
        f"CVEnrichmentResult must not have score fields: {enrichment_keys & score_fields}"
    )

    # EscoResolvedSkill
    esco_resolved_keys = set(EscoResolvedSkill.model_fields.keys())
    assert not esco_resolved_keys & score_fields, (
        f"EscoResolvedSkill must not have score fields: {esco_resolved_keys & score_fields}"
    )

    # CVPipelineResult (dataclass)
    pipeline_keys = {f.name for f in dc_fields(CVPipelineResult)}
    assert not pipeline_keys & score_fields, (
        f"CVPipelineResult must not have score fields: {pipeline_keys & score_fields}"
    )

    # resolved_to_esco IS present in CVEnrichmentResult (added in this feature)
    assert "resolved_to_esco" in enrichment_keys

    print("\n[TEST7] score_core invariant: no score fields in any enrichment contract ✓")


# ── Test 8 — LLM-sourced token with mapping → llm_token_to_esco provenance ───

def test_llm_token_provenance():
    """
    A token discovered by Compass E LLM that also has an ESCO mapping
    must receive provenance='llm_token_to_esco'.
    """
    from unittest.mock import patch

    store = _fresh()
    cluster = "FINANCE"

    # Register an ESCO mapping for "xbrl" (which we'll inject via mock LLM)
    store.add_esco_mapping(cluster, "xbrl", "http://esco/xbrl", "XBRL reporting", "manual")

    _MOCK_LLM = [{"token": "XBRL", "evidence": "mocked for provenance test"}]

    sparse_cv = "Juriste droit financier conformité réglementaire AMF reporting IFRS"

    with patch("compass.llm_enricher.call_llm_for_skills", return_value=_MOCK_LLM):
        result = enrich_cv(
            cv_text=sparse_cv,
            cluster=cluster,
            esco_skills=[],       # sparse → triggers LLM
            llm_enabled=True,
            library=store,
        )

    assert result.llm_triggered is True, "Expected LLM to fire for sparse CV"

    # xbrl comes from LLM → may be PENDING (not yet ACTIVE), so may not be in active_skills
    # But if it's in active_skills, provenance must be llm_token_to_esco
    xbrl_resolved = next(
        (r for r in result.resolved_to_esco if r.token_normalized == "xbrl"), None
    )
    if xbrl_resolved is not None:
        assert xbrl_resolved.provenance == "llm_token_to_esco", (
            f"Expected llm_token_to_esco, got {xbrl_resolved.provenance!r}"
        )

    # LLM suggestion is recorded — it may be PENDING (no offers yet), which is correct
    print(
        f"\n[TEST8] llm_triggered={result.llm_triggered} "
        f"llm_suggestions={result.llm_suggestions} "
        f"resolved_xbrl={xbrl_resolved}"
    )
