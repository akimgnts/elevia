"""
analyze_ai_quality.py — POST /analyze/audit-ai-quality (DEV-only).

Compute cluster-aware AI recovery quality metrics (display-only).
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from analysis.ai_quality_audit import audit_ai_quality
from api.utils.inbox_catalog import load_catalog_offers

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analyze"])


def _dev_tools_enabled() -> bool:
    return os.getenv("ELEVIA_DEV_TOOLS", "").lower() in {"1", "true", "yes"}


class OfferLite(BaseModel):
    id: Optional[str] = None
    offer_cluster: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    skills_display: List[str] = Field(default_factory=list)


class AuditAIQualityRequest(BaseModel):
    cluster: str = Field(..., description="Dominant cluster (e.g. DATA_IT)")
    validated_esco_labels: List[str] = Field(default_factory=list)
    recovered_skills: List[str] = Field(default_factory=list)
    offers: Optional[List[OfferLite]] = None


class AuditAIQualityResponse(BaseModel):
    validated_esco_count: int
    ai_recovered_count: int
    ai_overlap_with_offers: int
    ai_unique_vs_esco: int
    cluster_coherence_score: float
    noise_ratio_estimate: float
    offers_considered: int
    request_id: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None


@router.post(
    "/analyze/audit-ai-quality",
    response_model=AuditAIQualityResponse,
    summary="DEV-only: audit AI recovery quality (no scoring impact)",
)
async def post_audit_ai_quality(req: AuditAIQualityRequest) -> JSONResponse:
    request_id = uuid.uuid4().hex

    if not _dev_tools_enabled():
        logger.info(
            "AI_QUALITY_AUDIT_BLOCKED request_id=%s reason=DEV_TOOLS_DISABLED",
            request_id,
        )
        return JSONResponse(
            status_code=400,
            content={
                "validated_esco_count": 0,
                "ai_recovered_count": 0,
                "ai_overlap_with_offers": 0,
                "ai_unique_vs_esco": 0,
                "cluster_coherence_score": 0.0,
                "noise_ratio_estimate": 0.0,
                "offers_considered": 0,
                "request_id": request_id,
                "error_code": "DEV_TOOLS_DISABLED",
                "error_message": "analyze/audit-ai-quality requires ELEVIA_DEV_TOOLS=1.",
            },
        )

    cluster = (req.cluster or "").strip().upper()

    if req.offers is not None:
        offers: List[Dict[str, Any]] = [
            o.model_dump() if hasattr(o, "model_dump") else o.dict() for o in req.offers
        ]
    else:
        offers = load_catalog_offers()

    if cluster:
        offers = [o for o in offers if (o.get("offer_cluster") or "").upper() == cluster]

    metrics = audit_ai_quality(
        profile={"validated_esco_labels": req.validated_esco_labels},
        offers=offers,
        recovered_skills=req.recovered_skills,
    )

    logger.info(
        "AI_QUALITY_AUDIT request_id=%s cluster=%s recovered=%d overlap=%d",
        request_id,
        cluster or "UNKNOWN",
        metrics["ai_recovered_count"],
        metrics["ai_overlap_with_offers"],
    )

    return JSONResponse(
        status_code=200,
        content={
            **metrics,
            "offers_considered": len(offers),
            "request_id": request_id,
            "error_code": None,
            "error_message": None,
        },
    )
