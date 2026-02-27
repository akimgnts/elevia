"""
context.py — Deterministic context extraction endpoints.

No scoring impact. Grounded only.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.schemas.context import (  # noqa: E402
    ContextFit,
    ContextFitRequest,
    OfferContext,
    OfferContextRequest,
    ProfileContext,
    ProfileContextRequest,
)
from api.utils.context_store import (  # noqa: E402
    get_offer_context,
    get_profile_context,
    store_offer_context,
    store_profile_context,
)
from context.extractors import (  # noqa: E402
    clean_description,
    extract_context_fit,
    extract_offer_context,
    extract_profile_context,
)
from semantic.embedding_store import get_profile_text_info  # noqa: E402
router = APIRouter(prefix="/context", tags=["context"])


@router.post("/offer", response_model=OfferContext)
async def context_offer(req: OfferContextRequest) -> OfferContext:
    description = clean_description(req.description or "")
    if not description:
        cached = get_offer_context(req.offer_id)
        if cached:
            return OfferContext.model_validate(cached)

    context = extract_offer_context(req.offer_id, description)
    store_offer_context(req.offer_id, context.model_dump())
    return context


@router.post("/profile", response_model=ProfileContext)
async def context_profile(req: ProfileContextRequest) -> ProfileContext:
    text = req.cv_text_cleaned or ""
    if not text and req.profile_id:
        info = get_profile_text_info(req.profile_id)
        if info and info.get("snippet"):
            text = str(info["snippet"])

    if not text:
        cached = get_profile_context(req.profile_id)
        if cached:
            return ProfileContext.model_validate(cached)

    context = extract_profile_context(
        req.profile_id,
        cv_text_cleaned=text or None,
        parsed_sections=req.parsed_sections,
        profile=req.profile,
    )
    store_profile_context(req.profile_id, context.model_dump())
    return context


@router.post("/fit", response_model=ContextFit)
async def context_fit(req: ContextFitRequest) -> ContextFit:
    context = extract_context_fit(
        profile_context=req.profile_context,
        offer_context=req.offer_context,
        matched_skills=req.matched_skills,
        missing_skills=req.missing_skills,
    )
    return context
