"""
profile_baseline.py — Deterministic baseline CV parsing endpoint.

POST /profile/parse-baseline
  - No LLM required. No OPENAI_API_KEY needed.
  - Delegates to profile.baseline_parser.run_baseline (shared with parse-file).
  - Returns a profile dict compatible with POST /inbox.
"""
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from profile.baseline_parser import run_baseline  # shared extractor
from profile.profile_cluster import detect_profile_cluster
from semantic.profile_cache import cache_profile_text, compute_profile_hash

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
    return ParseBaselineResponse(**result)
