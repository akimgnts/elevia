"""
analyze_recovery.py — POST /analyze/recover-skills (DEV-only).

Cluster-aware AI skill recovery for the Analyze page.
Input:  cluster + ignored_tokens + noise_tokens + validated_esco_labels + optional cv_excerpt
Output: recovered_skills list (display-only, max 20) + ai_available flag

DEV gate: returns 400 unless ELEVIA_DEV_TOOLS=1 in environment.
"""
from __future__ import annotations

import hashlib
import json
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


def _stable_hash_request(
    cluster: str,
    ignored_tokens: List[str],
    noise_tokens: List[str],
    validated_labels: List[str],
) -> str:
    from compass.cluster_signal_policy import normalize_token

    def _norm_list(values: List[str]) -> List[str]:
        out = []
        for v in values or []:
            norm = normalize_token(v)
            if norm:
                out.append(norm)
        return sorted(set(out))

    payload = {
        "cluster": (cluster or "").strip().upper(),
        "ignored_tokens": _norm_list(ignored_tokens),
        "noise_tokens": _norm_list(noise_tokens),
        "validated_esco_labels": _norm_list(validated_labels),
    }
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ── Request / Response models ──────────────────────────────────────────────────

class RecoverSkillsRequest(BaseModel):
    cluster: str = Field(..., description="Dominant cluster (e.g. DATA_IT)")
    ignored_tokens: List[str] = Field(default_factory=list, description="Tokens filtered by parser")
    noise_tokens: List[str] = Field(default_factory=list, description="Noisy / partial tokens")
    validated_esco_labels: List[str] = Field(default_factory=list, description="Already-validated ESCO labels (dedup guard)")
    profile_text_excerpt: Optional[str] = Field(None, description="Optional raw CV text (first 1500 chars used)")
    profile_fingerprint: Optional[str] = Field(None, description="Fingerprint of extracted text + cluster + pipeline")
    extracted_text_hash: Optional[str] = Field(None, description="Hash of extracted text (normalized)")
    force: Optional[bool] = Field(False, description="Bypass cache and force LLM call (DEV-only)")


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
    cache_hit: Optional[bool] = None
    ai_fired: Optional[bool] = None
    profile_fingerprint: Optional[str] = None
    request_hash: Optional[str] = None
    raw_count: Optional[int] = None
    candidate_count: Optional[int] = None
    dropped_count: Optional[int] = None
    noise_ratio: Optional[float] = None
    tech_density: Optional[float] = None
    dropped_reasons: Optional[dict] = None
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
                "cache_hit": False,
                "ai_fired": False,
                "profile_fingerprint": req.profile_fingerprint,
                "request_hash": None,
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

    from compass.cluster_signal_policy import build_candidates_for_ai
    from compass.analyze_skill_recovery import recover_skills_cluster_aware
    from api.utils.analyze_recovery_cache import PIPELINE_VERSION, get_cached_recovery, store_recovery_cache

    policy = build_candidates_for_ai(
        cluster=req.cluster,
        ignored_tokens=req.ignored_tokens,
        noise_tokens=req.noise_tokens,
        validated_esco_labels=req.validated_esco_labels,
    )
    candidates = policy.get("candidates") or []
    stats = policy.get("stats") or {}

    logger.info(
        "RECOVER_SKILLS_PREFILTER request_id=%s cluster=%s raw=%s candidates=%s dropped=%s",
        request_id,
        req.cluster,
        stats.get("raw_count"),
        stats.get("candidate_count"),
        stats.get("dropped_count"),
    )

    request_hash = _stable_hash_request(
        req.cluster,
        req.ignored_tokens,
        req.noise_tokens,
        req.validated_esco_labels,
    )
    profile_fingerprint = req.profile_fingerprint
    if not profile_fingerprint and req.extracted_text_hash:
        profile_fingerprint = hashlib.sha256(
            f"{req.extracted_text_hash}|{req.cluster.upper()}|{PIPELINE_VERSION}".encode("utf-8")
        ).hexdigest()

    if not profile_fingerprint:
        return JSONResponse(
            status_code=400,
            content={
                "recovered_skills": [],
                "ai_available": False,
                "ai_error": "INVALID_REQUEST",
                "error_code": "INVALID_REQUEST",
                "error_message": "profile_fingerprint or extracted_text_hash required",
                "cluster": req.cluster,
                "ignored_token_count": len(req.ignored_tokens),
                "noise_token_count": len(req.noise_tokens),
                "cache_hit": False,
                "ai_fired": False,
                "profile_fingerprint": None,
                "request_hash": request_hash,
                "raw_count": stats.get("raw_count"),
                "candidate_count": stats.get("candidate_count"),
                "dropped_count": stats.get("dropped_count"),
                "noise_ratio": stats.get("noise_ratio"),
                "tech_density": stats.get("tech_density"),
                "dropped_reasons": stats.get("dropped_by_reason"),
                "request_id": request_id,
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "profile_fingerprint or extracted_text_hash required",
                    "request_id": request_id,
                },
            },
        )

    if not req.force:
        cached = get_cached_recovery(profile_fingerprint, request_hash)
        if isinstance(cached, list):
            return JSONResponse(
                status_code=200,
                content={
                    "recovered_skills": cached,
                    "ai_available": True,
                    "ai_error": None,
                    "error_code": None,
                    "error_message": None,
                    "cluster": req.cluster,
                    "ignored_token_count": len(req.ignored_tokens),
                    "noise_token_count": len(req.noise_tokens),
                    "cache_hit": True,
                    "ai_fired": False,
                    "profile_fingerprint": profile_fingerprint,
                    "request_hash": request_hash,
                    "raw_count": stats.get("raw_count"),
                    "candidate_count": stats.get("candidate_count"),
                    "dropped_count": stats.get("dropped_count"),
                    "noise_ratio": stats.get("noise_ratio"),
                    "tech_density": stats.get("tech_density"),
                    "dropped_reasons": stats.get("dropped_by_reason"),
                    "request_id": request_id,
                },
            )

    result = recover_skills_cluster_aware(
        cluster=req.cluster,
        ignored_tokens=candidates,
        noise_tokens=[],
        validated_esco_labels=req.validated_esco_labels,
        profile_text_excerpt=req.profile_text_excerpt,
    )
    # Preserve raw counts (pre-filter) for UI visibility
    result.ignored_token_count = len(req.ignored_tokens)
    result.noise_token_count = len(req.noise_tokens)

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

    recovered_payload = [
        {
            "label": s.label,
            "kind": s.kind,
            "confidence": s.confidence,
            "source": s.source,
            "evidence": s.evidence,
            "why_cluster_fit": s.why_cluster_fit,
        }
        for s in result.recovered_skills
    ]

    if result.ai_available and result.ai_error is None:
        store_recovery_cache(profile_fingerprint, request_hash, recovered_payload)
    ai_fired = result.ai_error in {"LLM_CALL_FAILED"} or (result.ai_available and result.ai_error is None)

    return JSONResponse(
        status_code=200,
        content={
            "recovered_skills": recovered_payload,
            "ai_available": result.ai_available,
            "ai_error": error_code,
            "error_code": error_code,
            "error_message": error_message,
            "cluster": result.cluster,
            "ignored_token_count": result.ignored_token_count,
            "noise_token_count": result.noise_token_count,
            "cache_hit": False,
            "ai_fired": ai_fired,
            "profile_fingerprint": profile_fingerprint,
            "request_hash": request_hash,
            "raw_count": stats.get("raw_count"),
            "candidate_count": stats.get("candidate_count"),
            "dropped_count": stats.get("dropped_count"),
            "noise_ratio": stats.get("noise_ratio"),
            "tech_density": stats.get("tech_density"),
            "dropped_reasons": stats.get("dropped_by_reason"),
            "error": result.error,
            "request_id": request_id,
        },
    )
