"""
debug_match.py - Endpoint de debug pour le matching (DEV-only)
Sprint Debug - Trace complète du matching avec profil inline

Usage:
  POST /debug/match
  Body: {
    "profile": {...},           # Profil inline
    "offers": [...] (optional)  # Offres custom (sinon utilise catalog)
    "limit": 10 (optional)      # Max offres à tracer
  }
"""

import os
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Import matching engine
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from matching import MatchingEngine
from matching.extractors import extract_profile
from matching.match_trace import trace_matching_batch

from ..utils.inbox_catalog import load_catalog_offers

logger = logging.getLogger(__name__)

router = APIRouter(tags=["debug"])


def _is_dev_mode() -> bool:
    """Check if running in development mode."""
    # Multiple ways to detect dev mode
    env = os.getenv("ENV", "").lower()
    debug = os.getenv("DEBUG", "").lower()
    elevia_dev = os.getenv("ELEVIA_DEV", "").lower()

    return any([
        env in {"dev", "development", "local"},
        debug in {"1", "true", "yes"},
        elevia_dev in {"1", "true", "yes"},
    ])


class DebugMatchRequest(BaseModel):
    """Request body for debug match endpoint."""
    profile: Dict[str, Any] = Field(..., description="Profile to match")
    offers: Optional[List[Dict[str, Any]]] = Field(None, description="Custom offers (optional)")
    limit: int = Field(default=10, ge=1, le=50, description="Max offers to trace")


class DebugMatchResponse(BaseModel):
    """Response for debug match endpoint."""
    profile_summary: Dict[str, Any]
    stats: Dict[str, Any]
    traces: List[Dict[str, Any]]
    dev_mode: bool


@router.post("/debug/match", summary="Debug matching with inline profile (DEV-only)")
async def debug_match(req: DebugMatchRequest) -> DebugMatchResponse:
    """
    Trace le matching d'un profil inline contre les offres.

    DEV-only: Retourne une erreur 403 en production.

    Returns:
        - profile_summary: Résumé du profil extrait
        - stats: Statistiques globales (scores_above_15, offers_with_matched_skills, etc.)
        - traces: Liste des traces par offre (max limit)
    """
    # Check dev mode
    if not _is_dev_mode():
        raise HTTPException(
            status_code=403,
            detail="Debug endpoint only available in development mode. Set ENV=dev or DEBUG=1"
        )

    # Load offers
    if req.offers:
        offers = req.offers
    else:
        offers = load_catalog_offers()

    if not offers:
        raise HTTPException(status_code=404, detail="No offers available")

    # Create engine
    engine = MatchingEngine(offers=offers)

    # Trace matching
    result = trace_matching_batch(req.profile, offers, engine, max_traces=req.limit)

    # Convert traces to dicts
    traces_dicts = []
    for trace in result["traces"]:
        traces_dicts.append({
            "offer_id": trace.offer_id,
            "total_score": trace.total_score,
            "skills_score": trace.skills_score,
            "education_score": trace.education_score,
            "languages_score": trace.languages_score,
            "country_score": trace.country_score,
            "intersection_count": trace.intersection_count,
            "matched_skills": trace.matched_skills,
            "missing_skills": trace.missing_skills,
            "profile_skills_count": trace.profile_skills_norm_count,
            "offer_skills_count": trace.offer_skills_norm_count,
            "reasons": trace.reasons,
        })

    return DebugMatchResponse(
        profile_summary=result["profile_summary"],
        stats=result["stats"],
        traces=traces_dicts,
        dev_mode=True,
    )


@router.get("/debug/status", summary="Check debug mode status")
async def debug_status() -> Dict[str, Any]:
    """Check if debug endpoints are available."""
    return {
        "dev_mode": _is_dev_mode(),
        "env": os.getenv("ENV", "not_set"),
        "debug": os.getenv("DEBUG", "not_set"),
        "elevia_debug_matching": os.getenv("ELEVIA_DEBUG_MATCHING", "not_set"),
    }
