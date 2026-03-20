from __future__ import annotations

from compass.explainability.semantic_explanation_builder import build_semantic_explainability


def _profile(**overrides):
    payload = {
        "dominant_role_block": "finance_ops",
        "dominant_domains": ["finance", "data"],
        "top_profile_signals": ["reporting", "audit", "analyse financiere", "sql"],
        "profile_summary": "Profil orienté finance opérationnelle avec ancrage reporting et audit.",
    }
    payload.update(overrides)
    return payload



def _offer(**overrides):
    payload = {
        "dominant_role_block": "finance_ops",
        "dominant_domains": ["finance"],
        "top_offer_signals": ["reporting", "audit", "budget"],
        "required_skills": ["reporting", "audit", "vba", "modelisation financiere"],
        "optional_skills": ["power bi"],
        "offer_summary": "Poste orienté finance opérationnelle avec ancrage reporting budgétaire.",
    }
    payload.update(overrides)
    return payload



def test_same_role_block_yields_high_alignment():
    result = build_semantic_explainability(
        profile_intelligence=_profile(),
        offer_intelligence=_offer(),
        explanation={"strengths": ["reporting"], "blockers": ["VBA"], "gaps": []},
    )

    assert result is not None
    assert result["role_alignment"]["alignment"] == "high"
    assert result["domain_alignment"]["shared_domains"] == ["finance"]
    assert "reporting" in result["signal_alignment"]["matched_signals"]
    assert any(item.lower() in {"vba", "modelisation financiere"} for item in result["signal_alignment"]["missing_core_signals"])
    assert result["alignment_summary"].startswith("Ton profil et ce poste sont alignes")



def test_adjacent_role_block_yields_medium_alignment():
    result = build_semantic_explainability(
        profile_intelligence=_profile(dominant_role_block="business_analysis", dominant_domains=["business", "finance"]),
        offer_intelligence=_offer(),
        explanation={"strengths": [], "blockers": [], "gaps": []},
    )

    assert result is not None
    assert result["role_alignment"]["alignment"] == "medium"



def test_signal_lists_are_bounded_and_deterministic():
    result = build_semantic_explainability(
        profile_intelligence=_profile(top_profile_signals=["reporting", "audit", "analyse financiere", "sql", "power bi", "excel", "budget"]),
        offer_intelligence=_offer(required_skills=["reporting", "audit", "vba", "modelisation financiere", "budget", "excel", "power bi"]),
        explanation={"strengths": ["reporting", "audit"], "blockers": ["VBA"], "gaps": ["Modelisation financiere"]},
    )

    assert result is not None
    assert len(result["signal_alignment"]["matched_signals"]) <= 5
    assert len(result["signal_alignment"]["missing_core_signals"]) <= 5
    assert result == build_semantic_explainability(
        profile_intelligence=_profile(top_profile_signals=["reporting", "audit", "analyse financiere", "sql", "power bi", "excel", "budget"]),
        offer_intelligence=_offer(required_skills=["reporting", "audit", "vba", "modelisation financiere", "budget", "excel", "power bi"]),
        explanation={"strengths": ["reporting", "audit"], "blockers": ["VBA"], "gaps": ["Modelisation financiere"]},
    )
