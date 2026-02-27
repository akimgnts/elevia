"""
profile_file.py — CV file upload + deterministic baseline parsing.

POST /profile/parse-file
  - Accepts PDF or TXT (multipart/form-data field: `file`)
  - Extracts text from the file
  - Runs deterministic baseline parsing (no LLM required)
  - Returns profile compatible with POST /inbox
"""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, Query
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.utils.pdf_text import PdfTextError, extract_text_from_pdf
from api.utils.env import get_llm_api_key
from profile.baseline_parser import run_baseline, run_baseline_from_tokens
from profile.llm_skill_suggester import suggest_skills_from_cv
from semantic.profile_cache import cache_profile_text, compute_profile_hash

logger = logging.getLogger(__name__)
router = APIRouter(tags=["profile"])

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB hard cap
ALLOWED_TYPES = {"application/pdf", "text/plain"}
ALLOWED_EXTENSIONS = {".pdf", ".txt"}

_SAFE_FILENAME_RE = re.compile(r"[^\w.\-]")


def _safe_filename(name: str) -> str:
    """Strip path components and non-safe chars from filename."""
    base = Path(name).name  # strip directories
    return _SAFE_FILENAME_RE.sub("_", base)[:128]


def _is_pdf(content_type: str, filename: str) -> bool:
    return content_type == "application/pdf" or filename.lower().endswith(".pdf")


def _is_txt(content_type: str, filename: str) -> bool:
    return content_type.startswith("text/") or filename.lower().endswith(".txt")


# ── Response schema ────────────────────────────────────────────────────────────

class ParseFileResponse(BaseModel):
    source: str
    mode: str = "baseline"
    ai_available: bool = False
    ai_added_count: int = 0
    ai_error: Optional[str] = None
    filename: str
    content_type: str
    extracted_text_length: int
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


# ── Route ──────────────────────────────────────────────────────────────────────

@router.post("/profile/parse-file", response_model=ParseFileResponse)
async def parse_file(
    request: Request,
    file: UploadFile = File(...),
    enrich_llm: int = Query(0, ge=0, le=1, description="1 = attempt LLM skill enrichment"),
) -> ParseFileResponse:
    """
    Upload a CV (PDF or TXT) and run deterministic baseline skill extraction.

    Returns a `profile` dict directly usable in POST /inbox.
    No LLM required. Deterministic: same file → same output.
    """
    request_id = getattr(request.state, "request_id", "n/a")
    raw_filename = file.filename or "upload"
    filename = _safe_filename(raw_filename)
    content_type = (file.content_type or "application/octet-stream").split(";")[0].strip()

    # ── Type check ─────────────────────────────────────────────────────────────
    if not (_is_pdf(content_type, filename) or _is_txt(content_type, filename)):
        logger.warning(
            "[parse-file] rejected unsupported type=%s filename=%s request_id=%s",
            content_type, filename, request_id,
        )
        raise HTTPException(
            status_code=415,
            detail={
                "error": "Unsupported file type",
                "hint": "Upload a PDF (.pdf) or plain text (.txt) file",
                "content_type": content_type,
                "request_id": request_id,
            },
        )

    # ── Read file ──────────────────────────────────────────────────────────────
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "File too large",
                "hint": f"Max {MAX_FILE_BYTES // (1024*1024)} MB",
                "request_id": request_id,
            },
        )

    # ── Extract text ───────────────────────────────────────────────────────────
    warnings: List[str] = []

    if _is_pdf(content_type, filename):
        try:
            cv_text = extract_text_from_pdf(data)
        except PdfTextError as exc:
            logger.warning(
                "[parse-file] PDF extraction error code=%s request_id=%s",
                exc.code, request_id,
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "error": exc.message,
                    "code": exc.code,
                    "hint": "Try a text-layer PDF or paste the CV text at /profile/parse-baseline",
                    "request_id": request_id,
                },
            ) from exc
    else:
        cv_text = data.decode("utf-8", errors="ignore")

    cv_text = cv_text.strip()
    if not cv_text:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "No text extracted from file",
                "request_id": request_id,
            },
        )

    # ── Baseline parse ─────────────────────────────────────────────────────────
    try:
        result = run_baseline(cv_text, profile_id=f"file-{filename}")
    except Exception as exc:
        logger.error("[parse-file] baseline error: %s request_id=%s", exc, request_id)
        raise HTTPException(status_code=500, detail="Extraction failed") from exc

    mode = "baseline"
    ai_available = False
    ai_added_count = 0
    ai_error: Optional[str] = None

    # ── Optional LLM enrichment ───────────────────────────────────────────────
    if enrich_llm == 1:
        if not get_llm_api_key():
            ai_available = False
            ai_error = "missing_openai_api_key"
        else:
            ai_available = True
            llm = suggest_skills_from_cv(cv_text)
            llm_warning = llm.get("warning")
            if llm_warning:
                warnings.append(str(llm_warning))

            llm_error = llm.get("error")
            if llm_error:
                ai_error = "llm_failed"
            else:
                llm_skills = llm.get("skills") or []
                if isinstance(llm_skills, list):
                    base_tokens = result.get("skills_raw", [])
                    base_set = set(base_tokens)
                    new_tokens = [t for t in llm_skills if isinstance(t, str) and t not in base_set]
                    ai_added_count = len(new_tokens)
                    combined = base_tokens + new_tokens
                    result = run_baseline_from_tokens(
                        combined,
                        profile_id=f"file-{filename}",
                        source="llm",
                    )
                    mode = "llm"

    logger.info(
        "[parse-file] filename=%s content_type=%s text_len=%d raw=%d validated=%d request_id=%s",
        filename, content_type, len(cv_text),
        result["raw_detected"], result["validated_skills"], request_id,
    )

    profile = result.get("profile") or {}
    profile_hash = compute_profile_hash(profile)
    cache_profile_text(profile_hash, cv_text)

    return ParseFileResponse(
        source=result["source"],
        mode=mode,
        ai_available=ai_available,
        ai_added_count=ai_added_count,
        ai_error=ai_error,
        filename=filename,
        content_type=content_type,
        extracted_text_length=len(cv_text),
        canonical_count=result["canonical_count"],
        raw_detected=result["raw_detected"],
        validated_skills=result["validated_skills"],
        filtered_out=result["filtered_out"],
        validated_items=result.get("validated_items", []),
        validated_labels=result.get("validated_labels", []),
        raw_tokens=result.get("raw_tokens", []),
        filtered_tokens=result.get("filtered_tokens", []),
        alias_hits_count=result.get("alias_hits_count", 0),
        alias_hits=result.get("alias_hits", []),
        skill_groups=result.get("skill_groups", []),
        skills_uri_count=result.get("skills_uri_count", 0),
        skills_uri_collapsed_dupes=result.get("skills_uri_collapsed_dupes", 0),
        skills_unmapped_count=result.get("skills_unmapped_count", 0),
        skills_dupes=result.get("skills_dupes", []),
        skills_raw=result["skills_raw"],
        skills_canonical=result["skills_canonical"],
        profile=result["profile"],
        warnings=result.get("warnings", []) + warnings,
    )
