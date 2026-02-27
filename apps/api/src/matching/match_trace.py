"""
match_trace.py - Instrumentation de debug pour le matching
Sprint Debug - Trace complète étape par étape

Activé par: ELEVIA_DEBUG_MATCHING=1
"""

import os
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .extractors import ExtractedProfile, extract_profile, normalize_skill

logger = logging.getLogger(__name__)


def _debug_enabled() -> bool:
    value = os.getenv("ELEVIA_DEBUG_MATCHING", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _use_uri_scoring() -> bool:
    value = os.getenv("ELEVIA_SCORE_USE_URIS", "1").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _normalize_uri_list(raw_skills) -> List[str]:
    if isinstance(raw_skills, str):
        raw_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
    if isinstance(raw_skills, list):
        normalized = [str(s).strip() for s in raw_skills if isinstance(s, str) and str(s).strip()]
        return _dedupe_preserve_order(normalized)
    return []

@dataclass
class MatchTraceResult:
    """Résultat de trace pour une offre."""
    offer_id: str
    # Profile
    profile_skills_raw_count: int
    profile_skills_norm_count: int
    profile_skills_sample: List[str]
    # Offer
    offer_skills_raw_count: int
    offer_skills_norm_count: int
    offer_skills_sample: List[str]
    # Intersection
    intersection_count: int
    matched_skills: List[str]
    missing_skills: List[str]
    # Scores
    skills_score: float
    education_score: float
    languages_score: float
    country_score: float
    total_score: int
    # Reasons
    reasons: List[str]


def trace_single_match(
    profile: ExtractedProfile,
    offer: Dict,
    engine: Any,
) -> MatchTraceResult:
    """
    Trace complète d'un match profil/offre.

    Args:
        profile: ExtractedProfile extrait
        offer: Dict de l'offre
        engine: MatchingEngine instance

    Returns:
        MatchTraceResult avec toutes les étapes
    """
    offer_id = offer.get("id") or offer.get("offer_id") or "unknown"

    # Profile skills
    if _use_uri_scoring():
        profile_skills_norm = list(getattr(profile, "skills_uri", []))
        raw_skills = offer.get("skills_uri") or offer.get("skills", [])
        offer_skills_norm = _normalize_uri_list(raw_skills)
        offer_skills_set = set(offer_skills_norm)
    else:
        profile_skills_norm = list(profile.skills)
        raw_skills = offer.get("skills", [])
        if isinstance(raw_skills, str):
            raw_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
        offer_skills_norm = [normalize_skill(s) for s in raw_skills if s]
        offer_skills_set = set(offer_skills_norm)

    # Use engine to get full result (authoritative)
    result = engine.score_offer(profile, offer)
    breakdown = result.breakdown
    skills_debug = result.match_debug.get("skills", {}) if result.match_debug else {}
    matched_skills = skills_debug.get("matched", [])
    missing_skills = skills_debug.get("missing", [])
    skills_score = len(matched_skills) / len(offer_skills_set) if offer_skills_set else 0.0

    return MatchTraceResult(
        offer_id=str(offer_id),
        profile_skills_raw_count=profile.matching_skills_count,
        profile_skills_norm_count=len(profile.skills),
        profile_skills_sample=sorted(profile_skills_norm)[:10],
        offer_skills_raw_count=len(raw_skills),
        offer_skills_norm_count=len(offer_skills_set),
        offer_skills_sample=sorted(offer_skills_norm)[:10],
        intersection_count=len(matched_skills),
        matched_skills=matched_skills,
        missing_skills=missing_skills[:5],
        skills_score=round(breakdown.get("skills", 0.0), 3),
        education_score=round(breakdown.get("education", 0.0), 3),
        languages_score=round(breakdown.get("languages", 0.0), 3),
        country_score=round(breakdown.get("country", 0.0), 3),
        total_score=result.score,
        reasons=result.reasons,
    )


def trace_matching_batch(
    raw_profile: Dict,
    offers: List[Dict],
    engine: Any,
    max_traces: int = 30,
) -> Dict[str, Any]:
    """
    Trace un batch de matching avec logs.

    Args:
        raw_profile: Profil brut (dict)
        offers: Liste des offres
        engine: MatchingEngine instance
        max_traces: Max offres à tracer (défaut 30)

    Returns:
        Dict avec:
        - profile_summary: résumé du profil
        - traces: liste de MatchTraceResult
        - stats: statistiques globales
    """
    # Extract profile
    profile = extract_profile(raw_profile)

    profile_summary = {
        "profile_id": profile.profile_id,
        "skills_count": len(profile.skills),
        "skills_sample": sorted(list(profile.skills))[:15],
        "languages": sorted(list(profile.languages)),
        "education_level": profile.education_level,
        "preferred_countries": sorted(list(profile.preferred_countries)),
        "skill_source": profile.skill_source,
    }

    traces = []
    for offer in offers[:max_traces]:
        trace = trace_single_match(profile, offer, engine)
        traces.append(trace)

        if _debug_enabled():
            logger.info(
                "MATCH_TRACE offer_id=%s total=%s skills_score=%.3f "
                "intersection=%s profile_skills=%s offer_skills=%s "
                "matched=%s",
                trace.offer_id,
                trace.total_score,
                trace.skills_score,
                trace.intersection_count,
                trace.profile_skills_norm_count,
                trace.offer_skills_norm_count,
                trace.matched_skills[:5],
            )

    # Stats
    scores = [t.total_score for t in traces]
    matched_counts = [t.intersection_count for t in traces]

    stats = {
        "total_offers": len(offers),
        "traced_offers": len(traces),
        "scores_above_15": sum(1 for s in scores if s > 15),
        "scores_above_80": sum(1 for s in scores if s >= 80),
        "offers_with_matched_skills": sum(1 for c in matched_counts if c > 0),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "max_score": max(scores) if scores else 0,
        "avg_intersection": round(sum(matched_counts) / len(matched_counts), 1) if matched_counts else 0,
    }

    return {
        "profile_summary": profile_summary,
        "traces": traces,
        "stats": stats,
    }


def print_trace_report(result: Dict[str, Any], limit: int = 5) -> None:
    """Affiche un rapport de trace lisible."""
    print("=" * 60)
    print("MATCH TRACE REPORT")
    print("=" * 60)

    ps = result["profile_summary"]
    print(f"\n[PROFILE] {ps['profile_id']}")
    print(f"  skills_count: {ps['skills_count']}")
    print(f"  skills_sample: {ps['skills_sample']}")
    print(f"  languages: {ps['languages']}")
    print(f"  education_level: {ps['education_level']}")
    print(f"  skill_source: {ps['skill_source']}")

    stats = result["stats"]
    print(f"\n[STATS]")
    print(f"  total_offers: {stats['total_offers']}")
    print(f"  traced_offers: {stats['traced_offers']}")
    print(f"  scores_above_15: {stats['scores_above_15']}")
    print(f"  scores_above_80: {stats['scores_above_80']}")
    print(f"  offers_with_matched_skills: {stats['offers_with_matched_skills']}")
    print(f"  avg_score: {stats['avg_score']}")
    print(f"  max_score: {stats['max_score']}")

    print(f"\n[TRACES] (first {limit})")
    for trace in result["traces"][:limit]:
        print(f"\n  --- {trace.offer_id} ---")
        print(f"    total_score: {trace.total_score}")
        print(f"    skills_score: {trace.skills_score}")
        print(f"    intersection: {trace.intersection_count}")
        print(f"    matched_skills: {trace.matched_skills}")
        print(f"    missing_skills: {trace.missing_skills}")
        print(f"    reasons: {trace.reasons}")

    print("\n" + "=" * 60)
