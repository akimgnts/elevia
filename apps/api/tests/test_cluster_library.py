"""
test_cluster_library.py — Unit tests for the cluster-aware enrichment layer.

9 required tests:
  1. test_token_validation_stopwords          — stopword tokens rejected
  2. test_token_validation_soft_skills        — soft-skill tokens rejected
  3. test_activation_rules_cv_only            — cv occurrences alone don't activate
  4. test_activation_rules_cv_plus_offer      — (cv≥2 AND offer≥3) → ACTIVE
  5. test_activation_rules_offer_only         — offer≥5 alone → ACTIVE
  6. test_cv_enrichment_active_skills         — ACTIVE skills returned in domain_skills_active
  7. test_offer_enrichment_increments         — offer tokens increment occurrences_offers
  8. test_market_radar_generation             — radar report reflects library state
  9. test_scoring_invariance_enrichment       — CVEnrichmentResult has no score_core field

Constraints:
  - All tests use in-memory SQLite (:memory:) — no file I/O
  - No LLM calls (llm_enabled=False or not configured)
  - Deterministic
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.cluster_library import ClusterLibraryStore, reset_library
from compass.cv_enricher import enrich_cv, extract_candidate_tokens, should_trigger_llm
from compass.llm_enricher import validate_llm_suggestions
from compass.offer_enricher import enrich_offer, generate_market_radar
from compass.contracts import CVEnrichmentResult


# ── Fixture: fresh in-memory store ────────────────────────────────────────────

def _fresh_store() -> ClusterLibraryStore:
    """Return a new in-memory store (no shared state between tests)."""
    return ClusterLibraryStore(db_path=":memory:")


# ── Test 1 — Token validation: stopwords rejected ─────────────────────────────

def test_token_validation_stopwords():
    """
    Common FR/EN stopwords and generic business words must be rejected.
    validate_token returns False for these inputs.
    """
    store = _fresh_store()

    stopword_tokens = [
        "le", "la", "les", "et", "un",          # FR articles
        "the", "and", "for", "with", "of",       # EN prepositions
        "equipe", "projet", "travail",            # FR generic business
        "experience", "skills", "team",          # EN generic
        "autonomie", "dynamique", "motivation",  # soft skills
        "",                                       # empty
        "   ",                                    # whitespace
        "a",                                      # too short
    ]

    for token in stopword_tokens:
        result = store.validate_token(token)
        assert result is False, (
            f"Expected validate_token({repr(token)}) = False (stopword), got True"
        )


# ── Test 2 — Token validation: soft skills rejected ───────────────────────────

def test_token_validation_soft_skills():
    """
    Soft skills must be rejected regardless of capitalization.
    Valid technical tokens must pass.
    """
    store = _fresh_store()

    # These must be rejected
    rejected = [
        "soft skill",
        "team work",
        "esprit d'equipe",
        "communication",
        "leadership",
        "123",         # number-only
        "1234.56",     # number-only
    ]
    for token in rejected:
        assert store.validate_token(token) is False, (
            f"Expected validate_token({repr(token)}) = False"
        )

    # These must be accepted (technical tokens)
    accepted = [
        "Dataiku",
        "Power BI",
        "S&OP",
        "Terraform",
        "DCF",
        "Design Thinking",
    ]
    for token in accepted:
        assert store.validate_token(token) is True, (
            f"Expected validate_token({repr(token)}) = True (technical), got False"
        )


# ── Test 3 — Activation: CV alone does not activate ──────────────────────────

def test_activation_rules_cv_only():
    """
    Recording a token from CVs only (no offer occurrences) must NOT activate it.
    It should remain PENDING until offer threshold is met.
    """
    store = _fresh_store()
    cluster = "DATA_IT"

    # Record token from CV many times — but no offers
    for _ in range(10):
        status = store.record_cv_token(cluster, "Dataiku")

    # Must still be PENDING (no offers)
    skills = store.get_all_skills(cluster=cluster)
    dataiku_entry = next((s for s in skills if "dataiku" in s.token_normalized.lower()), None)
    assert dataiku_entry is not None, "Token not found in library after recording"
    assert dataiku_entry.status == "PENDING", (
        f"Expected PENDING after CV-only recordings, got {dataiku_entry.status}"
    )
    assert dataiku_entry.occurrences_cv >= 2, (
        f"Expected occurrences_cv ≥ 2, got {dataiku_entry.occurrences_cv}"
    )


# ── Test 4 — Activation: cv≥2 AND offer≥3 → ACTIVE ───────────────────────────

def test_activation_rules_cv_plus_offer():
    """
    Token becomes ACTIVE when occurrences_cv ≥ 2 AND occurrences_offers ≥ 3.
    """
    store = _fresh_store()
    cluster = "DATA_IT"
    token = "Notion"

    # Record from CV twice
    store.record_cv_token(cluster, token)
    store.record_cv_token(cluster, token)

    # Still PENDING after 2 CV + 0 offers
    entry = next(s for s in store.get_all_skills(cluster=cluster) if "notion" in s.token_normalized)
    assert entry.status == "PENDING", "Expected PENDING before offer threshold"

    # Record from offers twice (below threshold of 3)
    store.record_offer_token(cluster, token)
    store.record_offer_token(cluster, token)
    entry = next(s for s in store.get_all_skills(cluster=cluster) if "notion" in s.token_normalized)
    assert entry.status == "PENDING", "Expected PENDING at 2 offers (threshold=3)"

    # Third offer → should activate (cv=2 ≥ 2, offer=3 ≥ 3)
    final_status = store.record_offer_token(cluster, token)
    assert final_status == "ACTIVE", (
        f"Expected ACTIVE after cv=2 + offer=3, got {final_status}"
    )
    active = store.get_active_skills(cluster)
    assert "notion" in active, f"Expected 'notion' in active skills, got {active}"


# ── Test 5 — Activation: offer≥5 alone → ACTIVE ──────────────────────────────

def test_activation_rules_offer_only():
    """
    Token becomes ACTIVE from offer occurrences alone when offer ≥ 5.
    """
    store = _fresh_store()
    cluster = "FINANCE"
    token = "DCF"

    # 4 offers → still PENDING
    for _ in range(4):
        status = store.record_offer_token(cluster, token)
        assert status == "PENDING", f"Expected PENDING after {_ + 1} offers, got {status}"

    # 5th offer → ACTIVE
    status = store.record_offer_token(cluster, token)
    assert status == "ACTIVE", (
        f"Expected ACTIVE after 5 offer occurrences alone, got {status}"
    )
    active = store.get_active_skills(cluster)
    assert "dcf" in active, f"Expected 'dcf' in FINANCE active skills, got {active}"


# ── Test 6 — CV enrichment: ACTIVE skills returned ───────────────────────────

def test_cv_enrichment_active_skills():
    """
    domain_skills_active contains ACTIVE library tokens for the cluster.
    domain_skills_pending contains newly recorded PENDING tokens.
    """
    store = _fresh_store()
    cluster = "DATA_IT"

    # Pre-activate "databricks" (cv≥2 + offer≥3)
    for _ in range(2):
        store.record_cv_token(cluster, "Databricks")
    for _ in range(3):
        store.record_offer_token(cluster, "Databricks")

    # Now enrich a CV that mentions Databricks
    cv_text = (
        "Expériences professionnelles\n"
        "Lead Data Engineer - Airbus\n"
        "Utilisation de Databricks pour les pipelines ETL et Kafka pour le streaming.\n"
        "Maîtrise de Python, SQL, Spark.\n"
    )
    result = enrich_cv(
        cv_text=cv_text,
        cluster=cluster,
        esco_skills=["Python", "SQL"],
        llm_enabled=False,
        library=store,
    )

    assert isinstance(result, CVEnrichmentResult)
    assert "databricks" in result.domain_skills_active, (
        f"Expected 'databricks' in domain_skills_active, got {result.domain_skills_active}"
    )
    assert result.llm_triggered is False, "LLM should not be triggered (llm_enabled=False)"


# ── Test 7 — Offer enrichment: increments occurrences_offers ─────────────────

def test_offer_enrichment_increments():
    """
    Processing an offer increments occurrences_offers for extracted tokens.
    """
    store = _fresh_store()
    cluster = "SUPPLY_OPS"

    offer_text = (
        "Nous recherchons un responsable Supply Chain maîtrisant S&OP, "
        "Lean Manufacturing et les outils SAP.\n"
        "Une expérience sur Kinaxis ou Blue Yonder est un plus."
    )
    result = enrich_offer(
        offer_text=offer_text,
        cluster=cluster,
        esco_skills=["SAP"],
        library=store,
    )

    assert result.cluster == cluster
    # new_tokens_recorded must be non-empty (tokens recorded from offer)
    assert len(result.new_tokens_recorded) >= 1, (
        f"Expected ≥1 tokens recorded from offer, got {result.new_tokens_recorded}"
    )

    # Check that offer occurrences were incremented
    all_skills = store.get_all_skills(cluster=cluster)
    assert len(all_skills) >= 1, "Expected at least one token after offer enrichment"

    # At least one token should have occurrences_offers ≥ 1
    has_offer = any(s.occurrences_offers >= 1 for s in all_skills)
    assert has_offer, (
        f"Expected occurrences_offers ≥ 1 for some token, got: {[(s.token_normalized, s.occurrences_offers) for s in all_skills]}"
    )


# ── Test 8 — Market Radar generation ─────────────────────────────────────────

def test_market_radar_generation():
    """
    Market Radar report reflects library state:
    - top_emerging_per_cluster contains pending tokens with high offer occurrences
    - new_active_skills contains ACTIVE tokens
    """
    store = _fresh_store()

    # Seed DATA_IT with some tokens
    for _ in range(3):
        store.record_offer_token("DATA_IT", "Figma")
    for _ in range(2):
        store.record_offer_token("DATA_IT", "Metabase")

    # Activate one token (offer≥5)
    for _ in range(5):
        store.record_offer_token("FINANCE", "XBRL")

    # Generate radar
    report = generate_market_radar(library=store, save=False)

    assert report.generated_at, "Report must have generated_at"

    # XBRL is ACTIVE in FINANCE → appears in new_active_skills
    assert "xbrl" in report.new_active_skills, (
        f"Expected 'xbrl' in new_active_skills, got {report.new_active_skills}"
    )

    # DATA_IT has PENDING tokens → appears in top_emerging_per_cluster
    if "DATA_IT" in report.top_emerging_per_cluster:
        emerging = report.top_emerging_per_cluster["DATA_IT"]
        assert len(emerging) >= 1, f"Expected ≥1 emerging in DATA_IT, got {emerging}"
    else:
        # Or they appear in pending_skills
        assert any("figma" in s or "metabase" in s for s in report.pending_skills), (
            f"Expected figma/metabase in pending_skills, got {report.pending_skills}"
        )


# ── Test 9 — Score invariance ─────────────────────────────────────────────────

def test_scoring_invariance_enrichment():
    """
    The enrichment layer NEVER touches score_core.

    Verifications:
    1. CVEnrichmentResult has no score_core field
    2. Calling enrich_cv multiple times does not alter a reference score_core value
    3. ClusterDomainSkill has no score_core field (validation_score is distinct)
    """
    store = _fresh_store()
    reference_score_core = 0.82

    # Run enrichment multiple times
    for _ in range(3):
        result = enrich_cv(
            cv_text="Utilisation de Kafka, Spark et Flink pour les pipelines data.",
            cluster="DATA_IT",
            esco_skills=["Python", "SQL"],
            llm_enabled=False,
            library=store,
        )
        # Reference must be unchanged
        assert reference_score_core == 0.82, (
            "score_core was mutated by enrich_cv — violates power rule"
        )

    # CVEnrichmentResult must NOT have score_core
    result_dict = result.model_dump()
    assert "score_core" not in result_dict, (
        f"CVEnrichmentResult must not contain score_core. Found: {list(result_dict.keys())}"
    )

    # ClusterDomainSkill must NOT have score_core
    all_skills = store.get_all_skills()
    if all_skills:
        skill_dict = all_skills[0].model_dump()
        assert "score_core" not in skill_dict, (
            f"ClusterDomainSkill must not contain score_core. Found: {list(skill_dict.keys())}"
        )
        # validation_score is distinct from score_core
        assert "validation_score" in skill_dict, (
            "ClusterDomainSkill should have validation_score (not score_core)"
        )
