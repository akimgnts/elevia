from __future__ import annotations

from compass.profile.profile_intelligence import build_profile_intelligence


def _unit(*, raw_text: str, action_verb: str, obj: str, domain: str, ranking_score: float = 1.2) -> dict:
    return {
        "raw_text": raw_text,
        "action_verb": action_verb,
        "object": obj,
        "domain": domain,
        "ranking_score": ranking_score,
        "specificity_score": ranking_score,
    }


def _skill(label: str, *, cluster_name: str, genericity_score: float = 0.2) -> dict:
    return {
        "label": label,
        "cluster_name": cluster_name,
        "genericity_score": genericity_score,
    }


def _fake_role_resolution(raw_title: str = "") -> dict:
    return {
        "raw_title": raw_title,
        "normalized_title": raw_title,
        "primary_role_family": None,
        "secondary_role_families": [],
        "candidate_occupations": [],
        "occupation_confidence": 0.0,
    }


def test_finance_profile_maps_to_finance_ops(monkeypatch):
    monkeypatch.setattr(
        "compass.profile.profile_intelligence._safe_role_resolution",
        lambda _cv_text, _canonical_skills: _fake_role_resolution("assistant controleur de gestion"),
    )

    result = build_profile_intelligence(
        cv_text="Assistant controleur de gestion",
        profile={},
        profile_cluster={"dominant_cluster": "FINANCE_LEGAL", "confidence": 0.8},
        top_signal_units=[
            _unit(raw_text="preparation de reportings mensuels", action_verb="preparation", obj="reportings mensuels", domain="finance", ranking_score=1.5),
            _unit(raw_text="suivi ecarts budget realise", action_verb="suivi", obj="ecarts budget realise", domain="finance", ranking_score=1.35),
        ],
        secondary_signal_units=[],
        preserved_explicit_skills=[
            _skill("Financial Analysis", cluster_name="FINANCE_BUSINESS_OPERATIONS"),
            _skill("Budget Tracking", cluster_name="FINANCE_BUSINESS_OPERATIONS"),
            _skill("Management Control", cluster_name="FINANCE_BUSINESS_OPERATIONS"),
            _skill("Excel", cluster_name="GENERIC_TRANSVERSAL", genericity_score=0.1),
        ],
        profile_summary_skills=[
            _skill("Reporting", cluster_name="FINANCE_BUSINESS_OPERATIONS"),
            _skill("Monthly Closing", cluster_name="FINANCE_BUSINESS_OPERATIONS"),
        ],
        canonical_skills=[
            _skill("Financial Analysis", cluster_name="FINANCE_BUSINESS_OPERATIONS"),
            _skill("Budget Tracking", cluster_name="FINANCE_BUSINESS_OPERATIONS"),
        ],
    )

    assert result["dominant_role_block"] == "finance_ops"
    assert "finance" in result["dominant_domains"]
    assert result["role_hypotheses"][0]["label"] in {"Contrôleur de gestion", "Financial Analyst"}


def test_sales_profile_maps_to_sales_business_dev(monkeypatch):
    monkeypatch.setattr(
        "compass.profile.profile_intelligence._safe_role_resolution",
        lambda _cv_text, _canonical_skills: _fake_role_resolution("business developer"),
    )

    result = build_profile_intelligence(
        cv_text="Business Developer",
        profile={},
        profile_cluster={"dominant_cluster": "MARKETING_SALES", "confidence": 0.7},
        top_signal_units=[
            _unit(raw_text="qualification de leads", action_verb="qualification", obj="leads", domain="sales", ranking_score=1.5),
            _unit(raw_text="suivi portefeuille clients", action_verb="suivi", obj="portefeuille clients", domain="sales", ranking_score=1.4),
        ],
        secondary_signal_units=[],
        preserved_explicit_skills=[
            _skill("Lead Qualification", cluster_name="MARKETING_SALES_GROWTH"),
            _skill("Prospecting", cluster_name="MARKETING_SALES_GROWTH"),
            _skill("CRM Management", cluster_name="MARKETING_SALES_GROWTH"),
            _skill("Salesforce", cluster_name="MARKETING_SALES_GROWTH", genericity_score=0.1),
        ],
        profile_summary_skills=[_skill("Sales Follow-up", cluster_name="MARKETING_SALES_GROWTH")],
        canonical_skills=[_skill("Lead Qualification", cluster_name="MARKETING_SALES_GROWTH")],
    )

    assert result["dominant_role_block"] == "sales_business_dev"
    assert result["role_hypotheses"][0]["label"] == "Business Developer"
    assert "sales" in result["dominant_domains"]


def test_data_profile_maps_to_data_analytics(monkeypatch):
    monkeypatch.setattr(
        "compass.profile.profile_intelligence._safe_role_resolution",
        lambda _cv_text, _canonical_skills: _fake_role_resolution("data analyst"),
    )

    result = build_profile_intelligence(
        cv_text="Data Analyst",
        profile={},
        profile_cluster={"dominant_cluster": "DATA_IT", "confidence": 0.9},
        top_signal_units=[
            _unit(raw_text="analyse de donnees", action_verb="analyse", obj="donnees clients", domain="data", ranking_score=1.6),
            _unit(raw_text="creation de dashboards power bi", action_verb="creation", obj="dashboards power bi", domain="data", ranking_score=1.4),
        ],
        secondary_signal_units=[],
        preserved_explicit_skills=[
            _skill("Data Analysis", cluster_name="DATA_ANALYTICS_AI"),
            _skill("SQL", cluster_name="DATA_ANALYTICS_AI", genericity_score=0.1),
            _skill("Power BI", cluster_name="DATA_ANALYTICS_AI", genericity_score=0.1),
        ],
        profile_summary_skills=[_skill("Business Intelligence", cluster_name="DATA_ANALYTICS_AI")],
        canonical_skills=[_skill("Data Analysis", cluster_name="DATA_ANALYTICS_AI")],
    )

    assert result["dominant_role_block"] == "data_analytics"
    assert result["role_hypotheses"][0]["label"] == "Data Analyst"
    assert "data" in result["dominant_domains"]


def test_marketing_analyst_title_overrides_data_bias(monkeypatch):
    monkeypatch.setattr(
        "compass.profile.profile_intelligence._safe_role_resolution",
        lambda _cv_text, _canonical_skills: {
            "raw_title": "marketing data analyst",
            "normalized_title": "marketing data analyst",
            "recent_experience_title": "",
            "primary_role_family": "data_analytics",
            "secondary_role_families": [],
            "candidate_occupations": [],
            "occupation_confidence": 0.64,
        },
    )

    result = build_profile_intelligence(
        cv_text="Marketing Data Analyst",
        profile={},
        profile_cluster={"dominant_cluster": "MARKETING_SALES", "confidence": 0.7},
        top_signal_units=[
            _unit(raw_text="automated content generation", action_verb="generation", obj="content generation", domain="marketing", ranking_score=1.3),
            _unit(raw_text="campaign performance analysis", action_verb="analysis", obj="campaign performance", domain="marketing", ranking_score=1.25),
        ],
        secondary_signal_units=[],
        preserved_explicit_skills=[
            _skill("Power BI", cluster_name="DATA_ANALYTICS_AI", genericity_score=0.1),
            _skill("Data Analysis", cluster_name="DATA_ANALYTICS_AI"),
            _skill("Content Writing", cluster_name="MARKETING_SALES_GROWTH"),
            _skill("Campaign Reporting", cluster_name="MARKETING_SALES_GROWTH"),
        ],
        profile_summary_skills=[_skill("Email Marketing", cluster_name="MARKETING_SALES_GROWTH")],
        canonical_skills=[
            _skill("Power BI", cluster_name="DATA_ANALYTICS_AI", genericity_score=0.1),
            _skill("Content Writing", cluster_name="MARKETING_SALES_GROWTH"),
        ],
    )

    assert result["dominant_role_block"] == "marketing_communication"
    assert result["role_hypotheses"][0]["label"] == "Marketing Analyst"


def test_supply_chain_reporting_prefers_supply_chain_over_data(monkeypatch):
    monkeypatch.setattr(
        "compass.profile.profile_intelligence._safe_role_resolution",
        lambda _cv_text, _canonical_skills: {
            "raw_title": "supply chain performance analyst",
            "normalized_title": "supply chain performance analyst",
            "recent_experience_title": "",
            "primary_role_family": "supply_chain",
            "secondary_role_families": [],
            "candidate_occupations": [],
            "occupation_confidence": 0.66,
        },
    )

    result = build_profile_intelligence(
        cv_text="Supply Chain Performance Analyst",
        profile={},
        profile_cluster={"dominant_cluster": "SUPPLY_OPS", "confidence": 0.7},
        top_signal_units=[
            _unit(raw_text="reporting data kpi supply chain", action_verb="reporting", obj="kpi supply chain", domain="supply_chain", ranking_score=1.35),
            _unit(raw_text="suivi fournisseurs et stocks", action_verb="suivi", obj="fournisseurs et stocks", domain="supply_chain", ranking_score=1.28),
        ],
        secondary_signal_units=[],
        preserved_explicit_skills=[
            _skill("Power BI", cluster_name="DATA_ANALYTICS_AI", genericity_score=0.1),
            _skill("Data Analysis", cluster_name="DATA_ANALYTICS_AI"),
            _skill("Inventory Management", cluster_name="FINANCE_BUSINESS_OPERATIONS"),
            _skill("Vendor Follow-up", cluster_name="FINANCE_BUSINESS_OPERATIONS"),
        ],
        profile_summary_skills=[_skill("Procurement", cluster_name="FINANCE_BUSINESS_OPERATIONS")],
        canonical_skills=[
            _skill("Power BI", cluster_name="DATA_ANALYTICS_AI", genericity_score=0.1),
            _skill("Inventory Management", cluster_name="FINANCE_BUSINESS_OPERATIONS"),
        ],
    )

    assert result["dominant_role_block"] == "supply_chain_ops"
    assert result["dominant_domains"][0] == "supply_chain"
