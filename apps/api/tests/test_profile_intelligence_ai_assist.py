from __future__ import annotations

from compass.profile.profile_intelligence_ai_assist import build_profile_intelligence_ai_assist


def _profile_intelligence(**overrides):
    base = {
        "dominant_role_block": "data_analytics",
        "secondary_role_blocks": ["business_analysis"],
        "dominant_domains": ["data", "business"],
        "top_profile_signals": ["analyse processus crm", "Data Analysis", "Power BI"],
        "role_hypotheses": [{"label": "Business Analyst", "confidence": 0.9}],
        "profile_summary": "Profil orienté analyse de donnees avec ancrage analyse processus crm.",
        "role_block_scores": [
            {"role_block": "data_analytics", "score": 10.0, "share": 0.52},
            {"role_block": "business_analysis", "score": 9.0, "share": 0.47},
        ],
        "debug": {
            "domain_scores": [
                {"domain": "data", "score": 8.0},
                {"domain": "business", "score": 7.2},
            ]
        },
    }
    base.update(overrides)
    return base


def _top_units():
    return [
        {
            "action_verb": "analyse",
            "object": "processus crm",
            "domain": "business",
            "tools": ["Power BI"],
        }
    ]


def test_ai_assist_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ELEVIA_ENABLE_PROFILE_INTELLIGENCE_AI_ASSIST", raising=False)

    result = build_profile_intelligence_ai_assist(
        profile_intelligence=_profile_intelligence(),
        top_signal_units=_top_units(),
    )

    assert result == {
        "enabled": False,
        "triggered": False,
        "accepted": False,
        "suggestion": None,
    }


def test_ai_assist_skips_clear_profiles(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_PROFILE_INTELLIGENCE_AI_ASSIST", "1")
    monkeypatch.setattr(
        "compass.profile.profile_intelligence_ai_assist.get_llm_api_key",
        lambda: "sk-test",
    )

    result = build_profile_intelligence_ai_assist(
        profile_intelligence=_profile_intelligence(
            dominant_role_block="finance_ops",
            dominant_domains=["finance"],
            role_block_scores=[
                {"role_block": "finance_ops", "score": 14.0, "share": 0.72},
                {"role_block": "data_analytics", "score": 3.0, "share": 0.15},
            ],
            debug={"domain_scores": [{"domain": "finance", "score": 9.0}, {"domain": "data", "score": 1.0}]},
        ),
        top_signal_units=_top_units(),
    )

    assert result["enabled"] is True
    assert result["triggered"] is False
    assert result["accepted"] is False


def test_ai_assist_accepts_high_precision_challenge(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_PROFILE_INTELLIGENCE_AI_ASSIST", "1")
    monkeypatch.setattr(
        "compass.profile.profile_intelligence_ai_assist.get_llm_api_key",
        lambda: "sk-test",
    )
    monkeypatch.setattr(
        "compass.profile.profile_intelligence_ai_assist.call_llm_json",
        lambda **_: (
            {
                "challenge": True,
                "suggested_role_block": "business_analysis",
                "confidence": 0.81,
                "reasoning": "CRM process analysis is stronger than generic BI tooling.",
                "used_signals": ["analyse processus crm", "business"],
            },
            0,
            0,
            0,
        ),
    )

    result = build_profile_intelligence_ai_assist(
        profile_intelligence=_profile_intelligence(),
        top_signal_units=_top_units(),
    )

    assert result["enabled"] is True
    assert result["triggered"] is True
    assert result["accepted"] is True
    assert result["suggestion"]["suggested_role_block"] == "business_analysis"


def test_ai_assist_rejects_unsupported_signal_use(monkeypatch):
    monkeypatch.setenv("ELEVIA_ENABLE_PROFILE_INTELLIGENCE_AI_ASSIST", "1")
    monkeypatch.setattr(
        "compass.profile.profile_intelligence_ai_assist.get_llm_api_key",
        lambda: "sk-test",
    )
    monkeypatch.setattr(
        "compass.profile.profile_intelligence_ai_assist.call_llm_json",
        lambda **_: (
            {
                "challenge": True,
                "suggested_role_block": "business_analysis",
                "confidence": 0.93,
                "reasoning": "Unsupported signal.",
                "used_signals": ["oracle erp"],
            },
            0,
            0,
            0,
        ),
    )

    result = build_profile_intelligence_ai_assist(
        profile_intelligence=_profile_intelligence(),
        top_signal_units=_top_units(),
    )

    assert result["triggered"] is True
    assert result["accepted"] is False
    assert result["suggestion"]["suggested_role_block"] == "business_analysis"
