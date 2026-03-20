"""
profile_baseline.py — Deterministic baseline CV parsing endpoint.

POST /profile/parse-baseline
  - No LLM required. No OPENAI_API_KEY needed.
  - Uses the shared modular parsing pipeline.
  - Returns a profile dict compatible with POST /inbox.
"""
import logging
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from compass.pipeline import build_parse_baseline_response_payload

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
    pipeline_used: str = "canonical_compass"
    pipeline_variant: str = "canonical_compass_baseline"
    compass_e_enabled: bool = False
    domain_skills_active: List[str] = []
    domain_skills_pending_count: int = 0
    llm_fired: bool = False
    mapping_inputs_count: int = 0
    structured_signal_units: List[dict] = []
    top_signal_units: List[dict] = []
    secondary_signal_units: List[dict] = []
    structured_signal_stats: dict = {}
    generic_filter_removed: List[dict] = []
    preserved_explicit_skills: List[dict] = []
    profile_summary_skills: List[dict] = []
    dropped_by_priority: List[dict] = []
    priority_trace: List[dict] = []
    priority_stats: dict = {}
    profile_intelligence: dict = {}
    profile_intelligence_ai_assist: dict = {}


@router.post("/profile/parse-baseline", response_model=ParseBaselineResponse)
async def parse_baseline(req: ParseBaselineRequest, request: Request) -> ParseBaselineResponse:
    if not req.cv_text.strip():
        raise HTTPException(status_code=422, detail="cv_text is empty")

    try:
        payload = build_parse_baseline_response_payload(
            cv_text=req.cv_text,
            request_id=getattr(request.state, "request_id", "n/a"),
        )
    except Exception as exc:
        logger.error("[parse-baseline] pipeline error: %s", exc)
        raise HTTPException(status_code=500, detail="Extraction failed") from exc

    return ParseBaselineResponse(**payload)
