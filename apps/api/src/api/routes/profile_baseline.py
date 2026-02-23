"""
profile_baseline.py — Deterministic baseline CV parsing endpoint.

POST /profile/parse-baseline
  - No LLM required. No OPENAI_API_KEY needed.
  - Delegates to profile.baseline_parser.run_baseline (shared with parse-file).
  - Returns a profile dict compatible with POST /inbox.
"""
import logging
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from profile.baseline_parser import run_baseline  # shared extractor

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
    profile: dict
    warnings: List[str] = []


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

    return ParseBaselineResponse(**result)
