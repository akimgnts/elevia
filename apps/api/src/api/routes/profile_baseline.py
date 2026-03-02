"""
profile_baseline.py — Deterministic baseline CV parsing endpoint.

POST /profile/parse-baseline
  - No LLM required. No OPENAI_API_KEY needed.
  - Delegates to profile.baseline_parser.run_baseline (shared with parse-file).
  - Returns a profile dict compatible with POST /inbox.
"""
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from profile.baseline_parser import run_baseline  # shared extractor
from profile.profile_cluster import detect_profile_cluster
from semantic.profile_cache import cache_profile_text, compute_profile_hash
from compass.profile_structurer import structure_profile_text_v1
from compass.canonical_pipeline import is_compass_e_enabled, is_trace_enabled
from api.utils.profile_summary_builder import build_profile_summary
from api.utils.profile_summary_store import store_profile_summary

logger = logging.getLogger(__name__)
router = APIRouter(tags=["profile"])


class ParseBaselineRequest(BaseModel):
    cv_text: str = Field(..., min_length=10, description="Raw CV text to parse")


class ParseBaselineResponse(BaseModel):
    source: str
    skills_raw: List[str]
    skills_canonical: List[str]
    canonical_count: int
    raw_detected: int
    validated_skills: int
    filtered_out: int
    validated_items: List[dict] = []
    validated_labels: List[str] = []
    raw_tokens: List[str] = []
    filtered_tokens: List[str] = []
    alias_hits_count: int = 0
    alias_hits: List[dict] = []
    skill_groups: List[dict] = []
    skills_uri_count: int = 0
    skills_uri_collapsed_dupes: int = 0
    skills_unmapped_count: int = 0
    skills_dupes: List[dict] = []
    profile: dict
    warnings: List[str] = []
    profile_cluster: Optional[dict] = None
    pipeline_used: str = "baseline"
    compass_e_enabled: bool = False
    domain_skills_active: List[str] = []
    domain_skills_pending_count: int = 0
    llm_fired: bool = False


@router.post("/profile/parse-baseline", response_model=ParseBaselineResponse)
async def parse_baseline(req: ParseBaselineRequest, request: Request) -> ParseBaselineResponse:
    """
    Deterministic baseline CV parser. No LLM. No external calls.

    Extracts skills by matching CV text against ESCO vocabulary tokens.
    Returns a `profile` dict ready to be passed directly to POST /inbox.
    """
    if not req.cv_text.strip():
        raise HTTPException(status_code=422, detail="cv_text is empty")

    try:
        result = run_baseline(req.cv_text)
    except Exception as exc:
        logger.error("[parse-baseline] extraction error: %s", exc)
        raise HTTPException(status_code=500, detail="Extraction failed") from exc

    logger.info(
        "[parse-baseline] canonical_count=%d request_id=%s",
        result["canonical_count"],
        getattr(request.state, "request_id", "n/a"),
    )

    profile = result.get("profile") or {}
    profile_hash = compute_profile_hash(profile)
    cache_profile_text(profile_hash, req.cv_text)

    # ── Profile summary cache (deterministic) ────────────────────────────────
    try:
        structured = structure_profile_text_v1(req.cv_text, debug=False)
        summary = build_profile_summary(structured, extra_skills=profile.get("skills"))
        store_profile_summary(profile_hash, summary.model_dump())
        if os.getenv("ELEVIA_DEBUG_PROFILE_SUMMARY", "").strip().lower() in {"1", "true", "yes", "on"}:
            logger.info(
                "PROFILE_SUMMARY_STORED profile_id=%s last_updated=%s",
                profile_hash,
                summary.last_updated,
            )
    except Exception as exc:
        logger.warning("[parse-baseline] profile summary failed: %s", type(exc).__name__)

    # ── Profile cluster (deterministic, no LLM) ───────────────────────────────
    skills_for_cluster: List[str] = []
    validated_items = result.get("validated_items") or []
    if validated_items:
        skills_for_cluster = [
            str(item.get("label") or item.get("uri") or "")
            for item in validated_items
            if isinstance(item, dict)
        ]
        skills_for_cluster = [s for s in skills_for_cluster if s]
    if not skills_for_cluster:
        skills_for_cluster = result.get("skills_canonical") or []
    if not skills_for_cluster:
        skills_for_cluster = result.get("skills_raw") or []

    profile_cluster = detect_profile_cluster(skills_for_cluster)
    logger.info(json.dumps({
        "event": "PROFILE_CLUSTER_DETECTED",
        "dominant_cluster": profile_cluster.get("dominant_cluster"),
        "dominance_percent": profile_cluster.get("dominance_percent"),
        "skills_count": profile_cluster.get("skills_count"),
        "request_id": getattr(request.state, "request_id", "n/a"),
    }))

    result["profile_cluster"] = profile_cluster

    # ── Compass E enrichment (canonical layer) ────────────────────────────────
    compass_e_on = is_compass_e_enabled()
    domain_skills_active: List[str] = []
    domain_skills_pending_count = 0
    llm_fired = False

    if compass_e_on:
        try:
            from compass.cv_enricher import enrich_cv
            esco_labels = result.get("validated_labels") or []
            cluster_key = (profile_cluster.get("dominant_cluster") or "").upper() or None
            enrichment = enrich_cv(
                cv_text=req.cv_text,
                cluster=cluster_key,
                esco_skills=esco_labels,
                llm_enabled=True,
            )
            domain_skills_active = enrichment.domain_skills_active
            domain_skills_pending_count = len(enrichment.domain_skills_pending)
            llm_fired = enrichment.llm_triggered
        except Exception as exc:
            logger.warning("[parse-baseline] compass_e enrichment failed (non-fatal): %s", type(exc).__name__)

    pipeline_tag = "baseline+compass_e+llm" if (compass_e_on and llm_fired) \
        else ("baseline+compass_e" if compass_e_on else "baseline")

    if is_trace_enabled():
        logger.info(
            "[PIPELINE_WIRING] parse-baseline pipeline_used=%s compass_e=%s domain_active=%d request_id=%s",
            pipeline_tag, compass_e_on, len(domain_skills_active),
            getattr(request.state, "request_id", "n/a"),
        )

    return ParseBaselineResponse(
        **result,
        pipeline_used=pipeline_tag,
        compass_e_enabled=compass_e_on,
        domain_skills_active=domain_skills_active,
        domain_skills_pending_count=domain_skills_pending_count,
        llm_fired=llm_fired,
    )
