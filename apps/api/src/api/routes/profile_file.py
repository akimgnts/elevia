"""
profile_file.py — CV file upload + deterministic baseline parsing.

POST /profile/parse-file
  - Accepts PDF or TXT (multipart/form-data field: `file`)
  - Extracts text from the file
  - Runs deterministic baseline parsing (no LLM required)
  - Returns profile compatible with POST /inbox
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, Query
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from compass.pipeline import build_parse_file_response_payload
from compass.pipeline.contracts import ParseFilePipelineRequest, PipelineHTTPError

router = APIRouter(tags=["profile"])


class ParseFileResponse(BaseModel):
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

    return ParseFileResponse(**response_payload)
