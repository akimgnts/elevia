"""
profile_baseline.py — Deterministic baseline CV parsing endpoint.

POST /profile/parse-baseline
  - No LLM required. No OPENAI_API_KEY needed.
  - Uses the ESCO-based token extractor from esco.extract.
  - Deterministic: same input → same output (sorted).
  - Returns a profile dict compatible with POST /inbox.
"""
import logging
import sys
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

# Ensure src/ is on path for esco imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from esco.extract import extract_raw_skills_from_profile

logger = logging.getLogger(__name__)
router = APIRouter(tags=["profile"])


class ParseBaselineRequest(BaseModel):
    cv_text: str = Field(..., min_length=10, description="Raw CV text to parse")


class ParseBaselineResponse(BaseModel):
    source: str
    skills_raw: List[str]
    skills_canonical: List[str]
    canonical_count: int
    profile: dict


@router.post("/profile/parse-baseline", response_model=ParseBaselineResponse)
async def parse_baseline(req: ParseBaselineRequest, request: Request) -> ParseBaselineResponse:
    """
    Deterministic baseline CV parser. No LLM. No external calls.

    Extracts skills by matching CV text against ESCO vocabulary tokens.
    Returns a `profile` dict ready to be passed directly to POST /inbox.

    X-Request-Id header is set by middleware.
    """
    if not req.cv_text.strip():
        raise HTTPException(status_code=422, detail="cv_text is empty")

    try:
        skills_raw: List[str] = extract_raw_skills_from_profile({"cv_text": req.cv_text})
    except Exception as exc:
        logger.error("[parse-baseline] extraction error: %s", exc)
        raise HTTPException(status_code=500, detail="Extraction failed") from exc

    # Canonical = raw (already normalized and expanded by extractor)
    skills_canonical = skills_raw
    canonical_count = len(skills_canonical)

    logger.info(
        "[parse-baseline] canonical_count=%d request_id=%s",
        canonical_count,
        getattr(request.state, "request_id", "n/a"),
    )

    profile = {
        "id": "baseline-profile",
        "skills": skills_canonical,
        "skills_source": "baseline",
    }

    return ParseBaselineResponse(
        source="baseline",
        skills_raw=skills_raw,
        skills_canonical=skills_canonical,
        canonical_count=canonical_count,
        profile=profile,
    )
