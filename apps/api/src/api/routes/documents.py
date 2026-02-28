"""
documents.py — POST /documents/cv endpoint.

Sprint CV Generator v1. Backend only.

Request:  CvRequest  { profile?, profile_id?, offer_id, lang, style }
Response: CvDocumentResponse { ok, document, duration_ms }

Logs (Railway-compatible JSON):
  DOC_CV_REQUEST    — cache_hit bool, offer_id, fingerprint_short, prompt_version
  DOC_CV_CACHE_HIT  — offer_id
  DOC_CV_LLM_CALL   — model, input_chars, output_chars, duration_ms  (in llm_client)
  DOC_CV_OK         — duration_ms, verdict_fields_present
  DOC_CV_FALLBACK_USED — reason
  DOC_CV_FAIL       — error_class, safe_message

Constraints:
  - ❌ No modification to matching core
  - ✅ DB-only for offers
  - ✅ No API key value in any log or response
"""

import logging
import time
from pathlib import Path
import sys

from fastapi import APIRouter, HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from documents.schemas import CvRequest, CvDocumentResponse
from documents.cv_generator import generate_cv
from documents.llm_client import is_llm_available

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


@router.post("/documents/cv", response_model=CvDocumentResponse)
async def create_cv(req: CvRequest) -> CvDocumentResponse:
    """
    Generate an ATS-optimised CV for a given offer + profile.

    - Cache hit: < 50ms
    - LLM miss: < 3s (excl. LLM call time)
    - Fallback if LLM unavailable or times out
    - JSON strict output — no free text
    """
    t0 = time.time()

    if not req.offer_id or not req.offer_id.strip():
        raise HTTPException(status_code=422, detail="offer_id is required")

    if req.profile is None and req.profile_id is None:
        # Allow empty profile (generates keyword-only fallback)
        req = req.model_copy(update={"profile": {}})

    try:
        payload = generate_cv(req)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(
            '{"event":"DOC_CV_FAIL","error_class":"%s","safe_message":"internal error"}',
            type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="CV generation failed — see logs")

    duration_ms = int((time.time() - t0) * 1000)

    return CvDocumentResponse(
        ok=True,
        document=payload,
        duration_ms=duration_ms,
    )


@router.get("/documents/cv/status")
async def cv_status():
    """Check CV generator readiness (LLM key presence, no value leaked)."""
    llm_ok = is_llm_available()
    return {
        "endpoint": "documents/cv",
        "llm_provider": "openai",
        "llm_key_present": llm_ok,
        "mode": "live" if llm_ok else "fallback_only",
        "prompt_version": "cv_v1",
        "cache": "sqlite",
    }
