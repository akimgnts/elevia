"""
test_context_fit_specificity.py — Context layer hardening tests.

Covers:
1. primary_role_type is not MIXED/UNKNOWN when there is clear evidence
2. stakeholder_signal = MEDIUM for "marketing/SAV/communication" phrasing
3. fit_summary uniqueness across a set of 5 distinct offers
4. overlap_tools detects SQL/Python/Excel etc. when present in both sides
5. evidence spans <= 20 words (regression)
6. responsibilities extracted from action-verb sentences (non-bulleted text)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from context.extractors import (
    extract_context_fit,
    extract_offer_context,
    extract_profile_context,
)


# ── 1. primary_role_type — not MIXED when evidence is unambiguous ─────────────

def test_primary_role_type_bi_when_only_reporting_keywords():
    """BI-only description → primary_role_type = BI_REPORTING (not MIXED)."""
    desc = "Construire des tableaux de bord Power BI, reporting hebdomadaire, dashboard KPI."
    ctx = extract_offer_context("offer-bi", desc)
    assert ctx.primary_role_type == "BI_REPORTING", (
        f"Expected BI_REPORTING, got {ctx.primary_role_type}"
    )


def test_primary_role_type_data_eng_when_only_pipeline_keywords():
    """Pipeline-only description → primary_role_type = DATA_ENGINEERING."""
    desc = "Développer des pipelines ETL, intégrer Airflow, construire un data warehouse avec dbt."
    ctx = extract_offer_context("offer-de", desc)
    assert ctx.primary_role_type == "DATA_ENGINEERING", (
        f"Expected DATA_ENGINEERING, got {ctx.primary_role_type}"
    )


def test_primary_role_type_never_unknown_when_there_is_evidence():
    """If any keyword hits, primary_role_type must not be UNKNOWN."""
    desc = "Produire des analyses statistiques et des rapports analytiques."
    ctx = extract_offer_context("offer-ana", desc)
    assert ctx.primary_role_type != "UNKNOWN"


def test_primary_role_type_reason_is_set_when_evidence_present():
    """role_type_reason must be a non-empty string when primary_role_type != UNKNOWN."""
    desc = "Reporting BI, tableaux de bord Power BI, SQL."
    ctx = extract_offer_context("offer-r", desc)
    if ctx.primary_role_type != "UNKNOWN":
        assert ctx.role_type_reason is not None
        assert len(ctx.role_type_reason) > 0
        assert len(ctx.role_type_reason) <= 120


# ── 2. stakeholder_signal expansion ──────────────────────────────────────────

def test_stakeholder_medium_for_internal_collaboration_keywords():
    """CV text mentioning 'interfaces avec équipes marketing, SAV' → MEDIUM."""
    cv_text = (
        "Data analyst avec interfaces avec équipes marketing, SAV, communication. "
        "Maîtrise Python et SQL."
    )
    ctx = extract_profile_context("p-stk", cv_text_cleaned=cv_text)
    assert ctx.experience_signals.stakeholder_signal == "MEDIUM", (
        f"Expected MEDIUM, got {ctx.experience_signals.stakeholder_signal}"
    )


def test_stakeholder_high_for_direction_keyword():
    """'direction' → HIGH."""
    cv_text = "Reporting pour la direction générale et les métiers."
    ctx = extract_profile_context("p-high", cv_text_cleaned=cv_text)
    assert ctx.experience_signals.stakeholder_signal == "HIGH"


def test_stakeholder_medium_for_coordination_keyword():
    """'coordination' → at least MEDIUM."""
    cv_text = "Coordination avec les équipes internes et support."
    ctx = extract_profile_context("p-coord", cv_text_cleaned=cv_text)
    assert ctx.experience_signals.stakeholder_signal in {"MEDIUM", "HIGH"}


# ── 3. fit_summary uniqueness across 5 distinct offer types ──────────────────

def _make_profile_ctx():
    cv_text = (
        "Analyste de données, maîtrise Python, SQL, Power BI, Excel. "
        "Interfaces avec équipes marketing et communication. Autonomie élevée."
    )
    return extract_profile_context("p-uniq", cv_text_cleaned=cv_text)


def test_fit_summary_unique_across_five_offers():
    """At least 4 distinct fit_summary strings across 5 different offer types."""
    descs = {
        "o1": "Reporting BI, Power BI, tableaux de bord KPI pour la direction.",
        "o2": "Développer des pipelines ETL avec Python, Airflow et dbt.",
        "o3": "Product analytics, funnels de conversion, A/B tests, Tableau.",
        "o4": "Analyse des opérations supply chain, Excel, SQL, forecasting.",
        "o5": "Business Intelligence, Looker, SQL, reporting mensuel pour métiers.",
    }
    prof_ctx = _make_profile_ctx()
    summaries = set()
    for oid, desc in descs.items():
        octx = extract_offer_context(oid, desc)
        fit = extract_context_fit(prof_ctx, octx, matched_skills=["SQL"], missing_skills=[])
        if fit.fit_summary:
            summaries.add(fit.fit_summary)

    assert len(summaries) >= 4, (
        f"Expected >= 4 unique fit_summary strings, got {len(summaries)}: {summaries}"
    )


# ── 4. overlap_tools uses profile_tools_signals (not dominant_strengths) ─────

def test_overlap_tools_detected_from_profile_cv_tools():
    """SQL in both offer description and profile CV → appears in why_it_fits."""
    cv_text = "Expert SQL et Python, reporting Power BI."
    prof_ctx = extract_profile_context("p-ovlp", cv_text_cleaned=cv_text)
    # Profile tools extracted from CV text
    assert "SQL" in prof_ctx.profile_tools_signals, (
        f"Expected SQL in profile_tools_signals, got: {prof_ctx.profile_tools_signals}"
    )

    offer_desc = "Analyser les données SQL, construire des rapports Excel."
    octx = extract_offer_context("o-ovlp", offer_desc)
    assert "SQL" in octx.tools_stack_signals

    fit = extract_context_fit(prof_ctx, octx, matched_skills=["SQL"], missing_skills=[])
    overlap_mentions = [b for b in fit.why_it_fits if "SQL" in b or "Outils communs" in b]
    assert overlap_mentions, (
        f"Expected SQL overlap in why_it_fits, got: {fit.why_it_fits}"
    )


def test_overlap_tools_empty_when_no_shared_tools():
    """If offer uses only Golang/Kubernetes and profile has SQL/Python, no overlap."""
    cv_text = "Expert SQL, Python, Power BI."
    prof_ctx = extract_profile_context("p-nolvp", cv_text_cleaned=cv_text)

    offer_desc = "Développer des microservices Golang, déploiement Kubernetes, CI/CD."
    octx = extract_offer_context("o-nolvp", offer_desc)

    fit = extract_context_fit(prof_ctx, octx, matched_skills=[], missing_skills=[])
    outils_bullets = [b for b in fit.why_it_fits if "Outils communs" in b]
    assert not outils_bullets, (
        f"Expected no 'Outils communs' bullet for Golang offer, got: {fit.why_it_fits}"
    )


# ── 5. Evidence spans <= 20 words (regression) ───────────────────────────────

def test_evidence_spans_capped_at_20_words_offer():
    """All OfferContext evidence spans must be <= 20 words."""
    desc = (
        "Mission principale: analyser les données de vente pour la direction commerciale. "
        "Construire des tableaux de bord Power BI. SQL, Python, Tableau requis. "
        "Autonomie élevée attendue. Anglais courant requis."
    )
    ctx = extract_offer_context("o-span", desc)
    for span in ctx.evidence_spans:
        assert len(span.span.split()) <= 20, (
            f"Span too long ({len(span.span.split())} words): {span.span!r}"
        )


def test_evidence_spans_capped_at_20_words_profile():
    """All ProfileContext evidence spans must be <= 20 words."""
    cv_text = (
        "Analyste de données spécialisé en reporting BI et normalisation de données. "
        "Maîtrise Python, SQL, Power BI, Excel, Tableau. "
        "Interfaces avec équipes marketing, SAV et communication. Bac+5."
    )
    ctx = extract_profile_context("p-span", cv_text_cleaned=cv_text)
    for span in ctx.evidence_spans:
        assert len(span.span.split()) <= 20, (
            f"Span too long ({len(span.span.split())} words): {span.span!r}"
        )


# ── 6. Responsibilities extracted from action-verb sentences ─────────────────

def test_responsibilities_extracted_from_non_bulleted_action_sentences():
    """When no bullets, action-verb sentences are used as responsibilities."""
    desc = (
        "Analyser les données de performance commerciale chaque semaine. "
        "Construire les tableaux de bord pour la direction. "
        "Automatiser les extractions de données via Python."
    )
    ctx = extract_offer_context("o-resp", desc)
    assert len(ctx.responsibilities) >= 2, (
        f"Expected >= 2 responsibilities from action sentences, got: {ctx.responsibilities}"
    )
    # needs_clarification should NOT complain about responsibilities
    resp_flags = [q for q in ctx.needs_clarification if "responsabilités" in q.lower()]
    assert not resp_flags, (
        f"Expected no 'responsabilités' clarification flag, got: {ctx.needs_clarification}"
    )
