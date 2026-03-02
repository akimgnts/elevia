"""
cluster_library_api.py — Read-only API for the cluster domain skill library.

Endpoints:
  GET  /cluster/library/metrics   — ClusterLibraryMetrics (token counts, LLM stats, drift)
  GET  /cluster/library/radar     — MarketRadarReport (emerging skills, new active, pending)
  GET  /cluster/library/skills    — List of ClusterDomainSkill (filterable by cluster/status)
  POST /cluster/library/enrich/cv — Enrich a CV text against the library (debug/admin use)

Score invariance: none of these endpoints touch score_core.
ELEVIA_DEBUG_CLUSTER=1 for verbose logging.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from compass.cluster_library import get_library
from compass.cv_enricher import enrich_cv
from compass.offer_enricher import generate_library_metrics, generate_market_radar

logger = logging.getLogger(__name__)
router = APIRouter(tags=["cluster-library"])

_debug = os.getenv("ELEVIA_DEBUG_CLUSTER", "").strip().lower() in {"1", "true", "yes"}


# ── Read endpoints ────────────────────────────────────────────────────────────

@router.get(
    "/cluster/library/metrics",
    summary="Métriques de la cluster library (actif, pending, LLM, drift)",
    response_class=JSONResponse,
)
async def get_cluster_metrics() -> JSONResponse:
    try:
        metrics = generate_library_metrics(save=False)
        return JSONResponse(content=metrics.model_dump())
    except Exception as exc:
        logger.exception("cluster/library/metrics error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/cluster/library/radar",
    summary="Market Radar — compétences émergentes non-ESCO par cluster",
    response_class=JSONResponse,
)
async def get_market_radar(
    top_n: int = Query(10, ge=1, le=50, description="Top N emerging skills per cluster"),
) -> JSONResponse:
    try:
        report = generate_market_radar(top_n=top_n, save=False)
        return JSONResponse(content=report.model_dump())
    except Exception as exc:
        logger.exception("cluster/library/radar error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/cluster/library/skills",
    summary="Liste des skills de la library (filtre par cluster/status)",
    response_class=JSONResponse,
)
async def get_library_skills(
    cluster: Optional[str] = Query(None, description="Filter by cluster (e.g. DATA_IT)"),
    status: Optional[str] = Query(None, description="Filter by status: PENDING | ACTIVE"),
) -> JSONResponse:
    try:
        lib = get_library()
        skills = lib.get_all_skills(status=status, cluster=cluster)
        return JSONResponse(content=[s.model_dump() for s in skills])
    except Exception as exc:
        logger.exception("cluster/library/skills error")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Write endpoints (admin / debug) ──────────────────────────────────────────

class CVEnrichRequest(BaseModel):
    cv_text: str = Field(..., min_length=1, description="Raw CV text")
    cluster: str = Field(..., min_length=1, description="Cluster key (e.g. DATA_IT)")
    esco_skills: List[str] = Field(default_factory=list, description="ESCO skill labels already matched")
    llm_enabled: bool = Field(False, description="Allow LLM trigger (default off for safety)")


@router.post(
    "/cluster/library/enrich/cv",
    summary="Enrichir un CV contre la cluster library (debug/admin)",
    response_class=JSONResponse,
    description="""
Fait tourner le pipeline d'enrichissement CV sur le texte fourni.

**Non destiné à la production directe** — utile pour tests et debug.
LLM est désactivé par défaut (`llm_enabled=false`).
Score invariance: ne touche pas score_core.
""",
)
async def enrich_cv_endpoint(request: CVEnrichRequest) -> JSONResponse:
    try:
        result = enrich_cv(
            cv_text=request.cv_text,
            cluster=request.cluster,
            esco_skills=request.esco_skills,
            llm_enabled=request.llm_enabled,
        )
        return JSONResponse(content=result.model_dump())
    except Exception as exc:
        logger.exception("cluster/library/enrich/cv error")
        raise HTTPException(status_code=500, detail=str(exc))
