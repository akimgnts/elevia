"""
test_context_profile_fallback.py — Lock signals for context layer hardening.

Covers:
A) ProfileContext.profile_tools_signals populated from profile.skills when cv_text absent.
B) Stakeholder friction NOT triggered when has_cv_text=False; clarifying question used instead.
C) OfferContext responsibilities_count >= 1 for any non-empty description.
D) primary_role_type = DATA_ENGINEERING for normalisation/csv/python description (fixture_003).
E) fit_summary distinct count >= 4 across 5 diverse offer types.
F) fit_summary for UNKNOWN primary_role_type uses contextual fallback (not ESCO count).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from context.extractors import (
    extract_context_fit,
    extract_offer_context,
    extract_profile_context,
)


# ── A) ProfileContext tools fallback from profile.skills (no cv_text) ─────────

def test_profile_tools_from_skills_list_when_no_cv_text():
    """SQL/Python/Excel in profile.skills → profile_tools_signals without CV text."""
    profile = {
        "id": "p-fallback",
        "skills": ["sql", "python", "excel", "power bi", "kpi", "reporting"],
    }
    ctx = extract_profile_context("p-fallback", cv_text_cleaned=None, profile=profile)
    assert not ctx.has_cv_text, "has_cv_text must be False when cv_text_cleaned is absent"
    assert len(ctx.profile_tools_signals) >= 2, (
        f"Expected >= 2 tools from profile.skills, got: {ctx.profile_tools_signals}"
    )
    assert "SQL" in ctx.profile_tools_signals or "Python" in ctx.profile_tools_signals, (
        f"Expected SQL or Python in profile_tools_signals, got: {ctx.profile_tools_signals}"
    )


def test_has_cv_text_true_when_cv_text_provided():
    """has_cv_text must be True when cv_text_cleaned is non-empty."""
    ctx = extract_profile_context("p-cv", cv_text_cleaned="Expert SQL, Python, Power BI.")
    assert ctx.has_cv_text is True


def test_has_cv_text_false_when_cv_text_empty_string():
    """has_cv_text must be False for empty string."""
    ctx = extract_profile_context("p-empty", cv_text_cleaned="")
    assert ctx.has_cv_text is False


# ── B) Stakeholder friction guard ────────────────────────────────────────────

def test_no_stakeholder_friction_when_has_cv_text_false():
    """Offer with stakeholder_exposure=HIGH + profile has_cv_text=False → no friction."""
    # Profile with no CV text → has_cv_text=False, stakeholder_signal=UNKNOWN
    profile = {
        "id": "p-notext",
        "skills": ["sql", "python", "excel"],
    }
    prof_ctx = extract_profile_context("p-notext", cv_text_cleaned=None, profile=profile)
    assert prof_ctx.has_cv_text is False
    assert prof_ctx.experience_signals.stakeholder_signal == "UNKNOWN"

    # Offer with HIGH stakeholder exposure
    offer_desc = "Reporting pour la direction générale et les clients. SQL requis."
    offer_ctx = extract_offer_context("o-high-stk", offer_desc)
    assert offer_ctx.work_style_signals.stakeholder_exposure == "HIGH"

    fit = extract_context_fit(prof_ctx, offer_ctx, matched_skills=[], missing_skills=[])
    friction_stk = [f for f in fit.likely_frictions if "parties prenantes" in f.lower()]
    assert not friction_stk, (
        f"Expected no stakeholder friction when has_cv_text=False, got: {fit.likely_frictions}"
    )


def test_stakeholder_clarifying_question_added_when_no_cv_text():
    """When has_cv_text=False and offer has HIGH stakeholder, add clarifying question."""
    profile = {"id": "p-notext2", "skills": ["sql", "python"]}
    prof_ctx = extract_profile_context("p-notext2", cv_text_cleaned=None, profile=profile)

    offer_desc = "Reporting pour la direction et interlocuteurs clients. SQL requis."
    offer_ctx = extract_offer_context("o-stk-q", offer_desc)

    fit = extract_context_fit(prof_ctx, offer_ctx, matched_skills=[], missing_skills=[])
    stk_question = [q for q in fit.clarifying_questions if "interlocuteurs" in q.lower()]
    assert stk_question, (
        f"Expected clarifying question about interlocuteurs, got: {fit.clarifying_questions}"
    )


def test_stakeholder_friction_fires_when_has_cv_text_true():
    """When has_cv_text=True and stakeholder_signal=UNKNOWN, friction is generated."""
    # Deliberately no stakeholder keywords → signal stays UNKNOWN
    cv_text = "Expert SQL et Python. Travail technique autonome, scripts d'automatisation."
    prof_ctx = extract_profile_context("p-cv-stk", cv_text_cleaned=cv_text)
    assert prof_ctx.has_cv_text is True

    offer_desc = "Reporting pour la direction générale et les clients. SQL requis."
    offer_ctx = extract_offer_context("o-stk-fire", offer_desc)
    assert offer_ctx.work_style_signals.stakeholder_exposure == "HIGH"

    fit = extract_context_fit(prof_ctx, offer_ctx, matched_skills=[], missing_skills=[])
    friction_stk = [f for f in fit.likely_frictions if "parties prenantes" in f.lower()]
    assert friction_stk, (
        f"Expected stakeholder friction when has_cv_text=True + signal=UNKNOWN, got: {fit.likely_frictions}"
    )


# ── C) OfferContext responsibilities never empty for non-empty description ────

def test_responsibilities_not_empty_for_nonempty_description():
    """Any non-empty description must produce responsibilities_count >= 1."""
    descs = [
        "KPI dashboarding, reporting hebdo.",
        "Data ops: normalisation des sources, SQL + Python.",
        "Analyse des opérations supply chain, Excel, SQL, forecasting.",
        "Product analytics, funnels de conversion, A/B tests.",
        "Développer des pipelines ETL avec Python et Airflow.",
    ]
    for desc in descs:
        ctx = extract_offer_context(f"o-resp-{hash(desc)}", desc)
        assert len(ctx.responsibilities) >= 1, (
            f"responsibilities empty for description: {desc!r}\n"
            f"Got: {ctx.responsibilities}"
        )


def test_responsibilities_uses_first_sentence_as_fallback():
    """When no action verbs and no bullets, use first sentence as fallback."""
    desc = "KPI dashboarding, reporting hebdo, SQL requis."
    ctx = extract_offer_context("o-fallback-resp", desc)
    assert len(ctx.responsibilities) >= 1, (
        f"Expected fallback responsibility, got: {ctx.responsibilities}"
    )
    # Fallback should not trigger clarification about responsibilities
    resp_flags = [q for q in ctx.needs_clarification if "responsabilités" in q.lower()]
    assert not resp_flags, (
        f"Unexpected responsibilities clarification flag: {ctx.needs_clarification}"
    )


# ── D) primary_role_type diversity — DATA_ENGINEERING for normalisation/csv ──

def test_primary_role_type_data_engineering_for_normalisation_csv():
    """'normalisation des sources, csv, python' → DATA_ENGINEERING (not UNKNOWN)."""
    desc = "Data ops: normalisation des sources, qualite data, SQL + Python, csv."
    ctx = extract_offer_context("o-de-norm", desc)
    assert ctx.primary_role_type == "DATA_ENGINEERING", (
        f"Expected DATA_ENGINEERING for normalisation/csv desc, got {ctx.primary_role_type}"
    )


def test_primary_role_type_distribution_not_all_bi_reporting():
    """Five diverse descriptions must not all resolve to BI_REPORTING."""
    descs = [
        ("o-bi", "Reporting BI, Power BI, tableaux de bord KPI pour la direction."),
        ("o-de", "Développer des pipelines ETL avec Python, Airflow et dbt."),
        ("o-pa", "Product analytics, funnels de conversion, A/B tests, Tableau."),
        ("o-ops", "Analyse des opérations supply chain, logistique, Excel, SQL."),
        ("o-de2", "Data ops: normalisation des sources, csv, qualité data, Python."),
    ]
    results = {}
    for oid, desc in descs:
        ctx = extract_offer_context(oid, desc)
        results[oid] = ctx.primary_role_type

    bi_count = sum(1 for v in results.values() if v == "BI_REPORTING")
    assert bi_count <= 2, (
        f"Expected <= 2 BI_REPORTING in 5 diverse offers, got {bi_count}: {results}"
    )
    unique_types = set(results.values())
    assert len(unique_types) >= 3, (
        f"Expected >= 3 distinct primary_role_types, got {len(unique_types)}: {results}"
    )


# ── E) fit_summary distinct >= 4 ─────────────────────────────────────────────

def test_fit_summary_distinct_count_with_mixed_profile():
    """Profile without CV text must still produce >= 3 distinct fit_summaries."""
    profile = {
        "id": "p-nosv",
        "skills": ["sql", "python", "excel", "power bi", "tableau", "kpi"],
    }
    prof_ctx = extract_profile_context("p-nosv", cv_text_cleaned=None, profile=profile)

    descs = {
        "os1": "Reporting BI, Power BI, tableaux de bord KPI pour la direction.",
        "os2": "Développer des pipelines ETL avec Python, Airflow et dbt.",
        "os3": "Product analytics, funnels de conversion, A/B tests, Tableau.",
        "os4": "Analyse des opérations supply chain, logistique, Excel, SQL.",
        "os5": "Data ops: normalisation des sources, csv, qualité data, Python.",
    }
    summaries = set()
    for oid, desc in descs.items():
        octx = extract_offer_context(oid, desc)
        fit = extract_context_fit(prof_ctx, octx, matched_skills=["SQL"], missing_skills=[])
        if fit.fit_summary:
            summaries.add(fit.fit_summary)

    assert len(summaries) >= 3, (
        f"Expected >= 3 distinct fit_summaries (no-cv profile), got {len(summaries)}: {summaries}"
    )


# ── F) fit_summary UNKNOWN fallback ──────────────────────────────────────────

def test_fit_summary_unknown_offer_uses_contextual_fallback():
    """Offer with no role signals → fit_summary is the contextual fallback string."""
    desc = "Poste à pourvoir, contacter RH."  # Completely vague
    offer_ctx = extract_offer_context("o-unk", desc)
    assert offer_ctx.primary_role_type == "UNKNOWN", (
        f"Expected UNKNOWN primary_role_type for vague desc, got {offer_ctx.primary_role_type}"
    )

    prof_ctx = extract_profile_context("p-unk", cv_text_cleaned="Expert SQL et Python.")
    fit = extract_context_fit(prof_ctx, offer_ctx, matched_skills=[], missing_skills=[])

    assert fit.fit_summary is not None, "fit_summary must not be None even for UNKNOWN offers"
    assert "ESCO" not in (fit.fit_summary or ""), (
        f"fit_summary for UNKNOWN offer must not be ESCO-technical: {fit.fit_summary!r}"
    )
    assert "peu détaillée" in (fit.fit_summary or "").lower() or "vérifier" in (fit.fit_summary or "").lower(), (
        f"Expected contextual fallback message for UNKNOWN offer, got: {fit.fit_summary!r}"
    )
