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

from documents.schemas import (
    CvRequest,
    CvDocumentResponse,
    ForOfferRequest,
    ForOfferResponse,
    CvHtmlResponse,
    CvHtmlMeta,
    ForOfferLetterRequest,
    ForOfferLetterResponse,
)
from documents.cv_generator import generate_cv, enrich_payload, get_offer
from documents.context_builder import build_matched_skills
from documents.preview_renderer import render_preview_markdown
from documents.html_renderer import render_cv_html
from documents.cover_letter_generator import generate_cover_letter
from documents.llm_client import is_llm_available
from api.utils.env import get_llm_api_key

logger = logging.getLogger(__name__)

# Safe startup signal — boolean only, key value never logged
logger.info(
    '{"event":"STARTUP","component":"documents","OPENAI_API_KEY_present":%s,"cv_engine":"deterministic_targeted_v2"}',
    "true" if get_llm_api_key() else "false",
)

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

    logger.info(
        '{"event":"DOCUMENTS_REQUEST","kind":"cv","offer_id":"%s","cache_hit":%s,"llm_enabled":%s,"duration_ms":%d}',
        req.offer_id,
        "true" if payload.meta.cache_hit else "false",
        "false",
        duration_ms,
    )

    return CvDocumentResponse(
        ok=True,
        document=payload,
        duration_ms=duration_ms,
    )


@router.post("/documents/cv/for-offer", response_model=ForOfferResponse)
async def create_cv_for_offer(req: ForOfferRequest) -> ForOfferResponse:
    """
    Generate an inbox-contextualised CV for a specific offer.

    Differences vs POST /documents/cv:
      - Accepts InboxContext (matched_skills / missing_skills from inbox)
      - Reorders keywords_injected + experience_block.tools:
          matched skills first (alpha), then rest (alpha) — deterministic
      - Returns preview_text (markdown) ready to display or download
      - context_used=True when inbox context drove the ordering

    Logs: DOC_FOR_OFFER_REQUEST, DOC_FOR_OFFER_OK, DOC_FOR_OFFER_FAIL
    No scoring core changes. No LLM beyond generate_cv().
    """
    t0 = time.time()
    profile = req.profile or {}

    logger.info(
        '{"event":"DOCUMENTS_REQUEST","kind":"cv","offer_id":"%s","has_context":%s,"lang":"%s","llm_enabled":%s}',
        req.offer_id,
        "true" if req.context and req.context.matched_skills else "false",
        req.lang,
        "false",
    )

    # Step 1: Build CV (cache-aware, LLM or fallback)
    cv_req = CvRequest(
        offer_id=req.offer_id,
        profile=profile,
        profile_id=req.profile_id,
        lang=req.lang,
    )
    try:
        payload = generate_cv(cv_req)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(
            '{"event":"DOC_FOR_OFFER_FAIL","error_class":"%s","safe_message":"cv generation failed"}',
            type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="CV generation failed — see logs")

    # Step 2: Build matched/missing context (from inbox or recomputed)
    offer = get_offer(req.offer_id) or {}
    ctx = req.context
    matched_core, _ = build_matched_skills(
        offer=offer,
        profile=profile,
        matched_skills=ctx.matched_skills if ctx else None,
        missing_skills=ctx.missing_skills if ctx else None,
    )
    context_used = bool(ctx and ctx.matched_skills)

    # Step 3: Enrich payload ordering (deterministic, no LLM)
    enriched = enrich_payload(payload, matched_core)

    # Step 4: Render markdown preview
    preview = render_preview_markdown(
        enriched,
        offer_title=offer.get("title") or req.offer_id,
        offer_company=offer.get("company") or "",
        offer_country=offer.get("country") or "",
    )

    duration_ms = int((time.time() - t0) * 1000)
    logger.info(
        '{"event":"DOC_FOR_OFFER_OK","offer_id":"%s","duration_ms":%d,"context_used":%s}',
        req.offer_id,
        duration_ms,
        "true" if context_used else "false",
    )
    logger.info(
        '{"event":"DOCUMENTS_REQUEST","kind":"cv","offer_id":"%s","cache_hit":%s,"llm_enabled":%s,"duration_ms":%d}',
        req.offer_id,
        "true" if enriched.meta.cache_hit else "false",
        "false",
        duration_ms,
    )

    return ForOfferResponse(
        ok=True,
        document=enriched,
        preview_text=preview,
        context_used=context_used,
        duration_ms=duration_ms,
    )


@router.post("/documents/cv/html/for-offer", response_model=CvHtmlResponse)
async def create_cv_html_for_offer(req: ForOfferRequest) -> CvHtmlResponse:
    """
    Render a deterministic HTML CV for a given offer using the versioned template.
    Input is identical to /documents/cv/for-offer.
    """
    t0 = time.time()
    profile = req.profile or {}

    offer = get_offer(req.offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail=f"Offer not found: {req.offer_id}")

    cv_req = CvRequest(
        offer_id=req.offer_id,
        profile=profile,
        profile_id=req.profile_id,
        lang=req.lang,
    )
    try:
        payload = generate_cv(cv_req)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(
            '{"event":"DOCUMENTS_CV_HTML_FAIL","error_class":"%s","safe_message":"cv generation failed"}',
            type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="CV HTML generation failed — see logs")

    ctx = req.context
    matched_core, _ = build_matched_skills(
        offer=offer,
        profile=profile,
        matched_skills=ctx.matched_skills if ctx else None,
        missing_skills=ctx.missing_skills if ctx else None,
    )
    enriched = enrich_payload(payload, matched_core)

    html_output = render_cv_html(enriched, template_version=req.template_version, profile=profile, offer=offer)
    duration_ms = int((time.time() - t0) * 1000)

    logger.info(
        '{"event":"DOCUMENTS_CV_HTML_REQUEST","offer_id":"%s","cache_hit":%s,'
        '"template_version":"%s","duration_ms":%d,"llm_used":%s}',
        req.offer_id,
        "true" if enriched.meta.cache_hit else "false",
        req.template_version,
        duration_ms,
        "false",
    )
    logger.info(
        '{"event":"DOCUMENTS_CV_HTML_RENDERED","offer_id":"%s","html_size":%d,"blocks_count":%d}',
        req.offer_id,
        len(html_output),
        len(enriched.experience_blocks),
    )

    meta = CvHtmlMeta(
        offer_id=req.offer_id,
        prompt_version=enriched.meta.prompt_version,
        cache_hit=enriched.meta.cache_hit,
        fallback_used=enriched.meta.fallback_used,
        template_version=req.template_version,
    )

    return CvHtmlResponse(
        ok=True,
        html=html_output,
        meta=meta,
        duration_ms=duration_ms,
    )


@router.post("/documents/letter/for-offer", response_model=ForOfferLetterResponse)
async def create_letter_for_offer(req: ForOfferLetterRequest) -> ForOfferLetterResponse:
    """
    Generate a deterministic cover letter for a specific offer.

    - Uses InboxContext matched skills if provided
    - No LLM calls
    - Returns preview_text (markdown) + structured blocks
    """
    t0 = time.time()
    profile = req.profile or {}

    logger.info(
        '{"event":"DOCUMENTS_REQUEST","kind":"letter","offer_id":"%s","has_context":%s,"lang":"%s","llm_enabled":false}',
        req.offer_id,
        "true" if req.context and req.context.matched_skills else "false",
        req.lang,
    )

    offer = get_offer(req.offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    ctx = req.context
    matched_core, _ = build_matched_skills(
        offer=offer,
        profile=profile,
        matched_skills=ctx.matched_skills if ctx else None,
        missing_skills=ctx.missing_skills if ctx else None,
    )
    context_used = bool(ctx and ctx.matched_skills)

    try:
        payload, preview = generate_cover_letter(
            offer_id=req.offer_id,
            offer_title=offer.get("title"),
            offer_company=offer.get("company"),
            matched_skills=matched_core,
            context_used=context_used,
        )
    except Exception as exc:
        logger.error(
            '{"event":"DOC_LETTER_FOR_OFFER_FAIL","error_class":"%s","safe_message":"letter generation failed"}',
            type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="Letter generation failed — see logs")

    duration_ms = int((time.time() - t0) * 1000)
    logger.info(
        '{"event":"DOC_LETTER_FOR_OFFER_OK","offer_id":"%s","duration_ms":%d,"context_used":%s}',
        req.offer_id,
        duration_ms,
        "true" if context_used else "false",
    )
    logger.info(
        '{"event":"DOCUMENTS_REQUEST","kind":"letter","offer_id":"%s","cache_hit":false,"llm_enabled":false,"duration_ms":%d}',
        req.offer_id,
        duration_ms,
    )

    return ForOfferLetterResponse(
        ok=True,
        document=payload,
        preview_text=preview,
        duration_ms=duration_ms,
    )


@router.get("/documents/cv/status")
async def cv_status():
    """Check deterministic CV generator readiness."""
    llm_ok = is_llm_available()
    return {
        "endpoint": "documents/cv",
        "llm_provider": "openai",
        "llm_key_present": llm_ok,
        "mode": "deterministic",
        "prompt_version": "cv_v1",
        "cache": "sqlite",
        "llm_used_for_cv": False,
    }
