"""
profile_file.py — CV file upload + deterministic baseline parsing.

POST /profile/parse-file
  - Accepts PDF or TXT (multipart/form-data field: `file`)
  - Extracts text from the file
  - Runs deterministic baseline parsing (no LLM required)
  - Persists profile to DB
  - Returns profile compatible with POST /inbox
"""
from __future__ import annotations

from copy import deepcopy
import sys
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, Query
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from compass.pipeline.canonical_mapping_stage import (
    dedupe_canonical_skills_for_display,
    merge_preserved_explicit_canonical_skills,
)
from compass.pipeline import build_parse_file_response_payload
from compass.pipeline.contracts import ParseFilePipelineRequest, PipelineHTTPError
from api.utils.profiles_db import save_profile

router = APIRouter(tags=["profile"])


def _build_matching_input_trace(response_payload: dict) -> dict:
    trace = response_payload.get("matching_input_trace") if isinstance(response_payload, dict) else {}
    return trace if isinstance(trace, dict) else {}


def _build_persisted_profile_data(response_payload: dict) -> dict:
    profile = deepcopy(response_payload.get("profile") or {})
    if not isinstance(profile, dict):
        profile = {}

    canonical_skills = deepcopy(response_payload.get("canonical_skills") or [])
    preserved_explicit_skills = deepcopy(response_payload.get("preserved_explicit_skills") or [])
    canonical_skills = merge_preserved_explicit_canonical_skills(
        canonical_skills,
        preserved_explicit_skills,
    )
    if canonical_skills:
        canonical_skills, _canonical_debug = dedupe_canonical_skills_for_display(
            canonical_skills,
            [],
        )
    resolved_canonical_count = sum(
        1 for item in canonical_skills if isinstance(item, dict) and item.get("canonical_id")
    )

    additive_fields = (
        "preserved_explicit_skills",
        "profile_summary_skills",
    )
    for field in additive_fields:
        if field in response_payload:
            profile[field] = deepcopy(response_payload.get(field))

    profile["canonical_skills"] = canonical_skills
    profile["canonical_skills_count"] = resolved_canonical_count

    return profile


class ParseFileResponse(BaseModel):
    profile_id: str  # NEW: Generated UUID for this parsed profile
    source: str
    mode: str = "baseline"
    pipeline_used: str = "canonical_compass"
    pipeline_variant: str = "canonical_compass_baseline"
    compass_e_enabled: bool = False
    domain_skills_active: List[str] = []
    domain_skills_pending_count: int = 0
    llm_fired: bool = False
    ai_available: bool = False
    ai_added_count: int = 0
    ai_error: Optional[str] = None
    filename: str
    content_type: str
    extracted_text_length: int
    extracted_text_hash: Optional[str] = None
    profile_fingerprint: Optional[str] = None
    recovery_pipeline_version: Optional[str] = None
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
    skills_raw: List[str]
    skills_canonical: List[str]
    profile: dict
    warnings: List[str] = []
    profile_cluster: Optional[dict] = None
    resolved_to_esco: List[dict] = []
    skill_provenance: dict = {}
    baseline_esco_count: int = 0
    injected_esco_from_domain: int = 0
    total_esco_count: int = 0
    matching_input_trace: dict = {}
    rejected_tokens: List[dict] = []
    tight_candidates: List[str] = []
    tight_metrics: dict = {}
    mapping_inputs_count: int = 0
    structured_signal_units: List[dict] = []
    top_signal_units: List[dict] = []
    secondary_signal_units: List[dict] = []
    structured_signal_stats: dict = {}
    generic_filter_removed: List[dict] = []
    enriched_signals: List[dict] = []
    concept_signals: List[dict] = []
    canonical_skills: List[dict] = []
    canonical_skills_count: int = 0
    canonical_hierarchy_added: List[str] = []
    preserved_explicit_skills: List[dict] = []
    profile_summary_skills: List[dict] = []
    dropped_by_priority: List[dict] = []
    priority_trace: List[dict] = []
    priority_stats: dict = {}
    skill_proximity_links: List[dict] = []
    skill_proximity_count: int = 0
    skill_proximity_summary: dict = {}
    profile_intelligence: dict = {}
    profile_intelligence_ai_assist: dict = {}
    raw_cv_reconstruction: dict = {}
    profile_reconstruction: dict = {}
    structured_cv_metadata: dict = {}
    analyze_dev: Optional[dict] = None


@router.post(
    "/profile/parse-file",
    response_model=ParseFileResponse,
    response_model_exclude_unset=True,
)
async def parse_file(
    request: Request,
    file: UploadFile = File(...),
    enrich_llm: int = Query(0, ge=0, le=1, description="1 = attempt LLM skill enrichment"),
) -> ParseFileResponse:
    request_id = getattr(request.state, "request_id", "n/a")
    profile_id = str(uuid.uuid4())  # Generate unique profile ID

    try:
        response_payload = build_parse_file_response_payload(
            ParseFilePipelineRequest(
                request_id=request_id,
                raw_filename=file.filename or "upload",
                content_type=file.content_type or "application/octet-stream",
                file_bytes=await file.read(),
                enrich_llm=enrich_llm,
            )
        )
    except PipelineHTTPError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Extraction failed") from exc

    # Save profile to DB (best-effort, doesn't fail the request if DB unavailable)
    profile_data = _build_persisted_profile_data(response_payload)
    save_profile(profile_id, profile_data, user_id=None)

    # Add profile_id to response
    response_payload["profile_id"] = profile_id
    response_payload["matching_input_trace"] = _build_matching_input_trace(response_payload)

    return ParseFileResponse(**response_payload)


# ============================================================================
# GET /profiles/{profile_id} — Fetch persisted profile
# ============================================================================

class GetProfileResponse(BaseModel):
    profile_id: str
    profile_data: dict
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@router.get("/profiles/{profile_id}", response_model=GetProfileResponse)
async def get_profile(profile_id: str) -> GetProfileResponse:
    """
    Fetch persisted profile by ID.

    Returns profile data if found, 404 otherwise.
    """
    from api.utils.profiles_db import get_profile

    profile_data = get_profile(profile_id)
    if not profile_data:
        raise HTTPException(status_code=404, detail="Profile not found")

    return GetProfileResponse(
        profile_id=profile_id,
        profile_data=profile_data,
        created_at=None,  # TODO: fetch from DB metadata
        updated_at=None,  # TODO: fetch from DB metadata
    )
