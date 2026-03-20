"""Backward-compatible explanation adapter for legacy inbox fields."""
from __future__ import annotations

from typing import Any, Dict, Optional

from compass.explainability.explanation_builder import build_offer_explanation


def _map_match_strength(confidence: Optional[str], score: Optional[int]) -> Optional[str]:
    if confidence:
        conf = confidence.strip().upper()
        if conf == "HIGH":
            return "STRONG"
        if conf == "MED":
            return "MEDIUM"
        return "WEAK"
    if score is None:
        return None
    if score >= 75:
        return "STRONG"
    if score >= 50:
        return "MEDIUM"
    return "WEAK"


def build_explanation(
    match_debug: Dict[str, Any],
    *,
    score: Optional[int] = None,
    confidence: Optional[str] = None,
) -> Dict[str, Any]:
    explanation = build_offer_explanation(
        match_debug,
        score=score,
        confidence=confidence,
    )

    strengths = explanation.get("strengths") or []
    blockers = explanation.get("blockers") or []
    next_actions = explanation.get("next_actions") or []

    why_match = strengths[:2] if strengths else ["No strong skill signals yet"]
    main_blockers = blockers[:2]
    next_move = (
        next_actions[0]
        if next_actions
        else "Add clearer skill evidence to your profile before targeting this role."
    )

    return {
        "fit_score": explanation.get("score"),
        "match_strength": _map_match_strength(confidence, score),
        "why_match": why_match,
        "main_blockers": main_blockers,
        "distance": explanation.get("fit_label"),
        "next_move": next_move,
    }
