from __future__ import annotations

from typing import Any, Dict, List

from compass.profile.profile_effective_skills import build_effective_skills_view

from .contracts import MatchingInputStageResult


def build_matching_input_trace(
    *,
    baseline_esco_count: int,
    profile: dict | None,
    stages: List[dict],
) -> MatchingInputStageResult:
    trace: Dict[str, Any] = {
        "freeze_boundary": "matching formula is unchanged; parsing may only add traceable URI channels",
        "stage_order": [
            "baseline_extraction",
            "canonical_mapping",
            "domain_enrichment",
            "promotion_enrichment",
            "matching_preparation",
        ],
        "stages": stages,
        "baseline_skills_uri_count": baseline_esco_count,
    }
    if profile:
        view = build_effective_skills_view(profile.get("skills_uri") or [], profile)
        trace["effective_skills"] = {
            "promote_enabled": view.promote_enabled,
            "base_count": len(view.base_uris),
            "domain_count": len(view.domain_uris),
            "promoted_count": len(view.promoted_uris),
            "effective_count": len(view.effective_uris),
            "added_domain_count": len(view.added_domain_uris),
            "added_promoted_count": len(view.added_promoted_uris) if view.promote_enabled else 0,
            "input_channels": ["base_uri", "domain_uri", "esco_promotion"],
            "provenance": dict(view.provenance),
        }
    else:
        trace["effective_skills"] = {
            "promote_enabled": False,
            "base_count": 0,
            "domain_count": 0,
            "promoted_count": 0,
            "effective_count": 0,
            "added_domain_count": 0,
            "added_promoted_count": 0,
            "input_channels": ["base_uri", "domain_uri", "esco_promotion"],
            "provenance": {},
        }
    return MatchingInputStageResult(matching_input_trace=trace)
