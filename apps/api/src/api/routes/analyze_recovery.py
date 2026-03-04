"""
analyze_recovery.py — POST /analyze/recover-skills (DEV-only).

Cluster-aware AI skill recovery for the Analyze page.
Input:  cluster + ignored_tokens + noise_tokens + validated_esco_labels + optional cv_excerpt
Output: recovered_skills list (display-only, max 20) + ai_available flag

DEV gate: returns 400 unless ELEVIA_DEV_TOOLS=1 in environment.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import List, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analyze"])


def _dev_tools_enabled() -> bool:
    return os.getenv("ELEVIA_DEV_TOOLS", "").lower() in {"1", "true", "yes"}


# ── Request / Response models ──────────────────────────────────────────────────

class RecoverSkillsRequest(BaseModel):
    cluster: str = Field(..., description="Dominant cluster (e.g. DATA_IT)")
    ignored_tokens: List[str] = Field(default_factory=list, description="Tokens filtered by parser")
    noise_tokens: List[str] = Field(default_factory=list, description="Noisy / partial tokens")
    validated_esco_labels: List[str] = Field(default_factory=list, description="Already-validated ESCO labels (dedup guard)")
    profile_text_excerpt: Optional[str] = Field(None, description="Optional raw CV text (first 1500 chars used)")


class RecoveredSkillItemModel(BaseModel):
    label: str
    kind: str
    confidence: float
    source: str
    evidence: str
    why_cluster_fit: str


class RecoverSkillsResponse(BaseModel):
    recovered_skills: List[RecoveredSkillItemModel]
    ai_available: bool
    ai_error: Optional[str]
    error_code: Optional[str]
    error_message: Optional[str]
    cluster: str
    ignored_token_count: int
    noise_token_count: int
    error: Optional[str]
    request_id: str


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "/analyze/recover-skills",
    response_model=RecoverSkillsResponse,
    summary="DEV-only: recover skills missed by deterministic parsing (AI)",
)
async def post_recover_skills(req: RecoverSkillsRequest) -> JSONResponse:
    request_id = uuid.uuid4().hex

    if not _dev_tools_enabled():
        logger.info(
            "RECOVER_SKILLS_BLOCKED request_id=%s reason=DEV_TOOLS_DISABLED",
            request_id,
        )
        return JSONResponse(
            status_code=400,
            content={
                "recovered_skills": [],
                "ai_available": False,
                "ai_error": "DEV_TOOLS_DISABLED",
                "error_code": "DEV_TOOLS_DISABLED",
                "error_message": "analyze/recover-skills requires ELEVIA_DEV_TOOLS=1.",
                "cluster": req.cluster,
                "ignored_token_count": len(req.ignored_tokens),
                "noise_token_count": len(req.noise_tokens),
                "request_id": request_id,
                "error": {
                    "code": "DEV_TOOLS_DISABLED",
                    "message": "analyze/recover-skills requires ELEVIA_DEV_TOOLS=1.",
                    "hint": "Set ELEVIA_DEV_TOOLS=1 and restart the API.",
                    "request_id": request_id,
                },
            },
        )

    logger.info(
        "RECOVER_SKILLS_REQUEST request_id=%s cluster=%s ignored=%d noise=%d",
        request_id,
        req.cluster,
        len(req.ignored_tokens),
        len(req.noise_tokens),
    )

    from compass.analyze_skill_recovery import recover_skills_cluster_aware

    result = recover_skills_cluster_aware(
        cluster=req.cluster,
        ignored_tokens=req.ignored_tokens,
        noise_tokens=req.noise_tokens,
        validated_esco_labels=req.validated_esco_labels,
        profile_text_excerpt=req.profile_text_excerpt,
    )

    logger.info(
        "RECOVER_SKILLS_RESULT request_id=%s cluster=%s recovered=%d ai_available=%s error=%s",
        request_id,
        result.cluster,
        len(result.recovered_skills),
        result.ai_available,
        result.ai_error,
    )

    error_code = result.ai_error
    error_message = result.error_message

    return JSONResponse(
        status_code=200,
        content={
            "recovered_skills": [
                {
                    "label": s.label,
                    "kind": s.kind,
                    "confidence": s.confidence,
                    "source": s.source,
                    "evidence": s.evidence,
                    "why_cluster_fit": s.why_cluster_fit,
                }
                for s in result.recovered_skills
            ],
            "ai_available": result.ai_available,
            "ai_error": error_code,
            "error_code": error_code,
            "error_message": error_message,
            "cluster": result.cluster,
            "ignored_token_count": result.ignored_token_count,
            "noise_token_count": result.noise_token_count,
            "error": result.error,
            "request_id": request_id,
        },
    )
