"""
apply_pack.py — POST /apply-pack

Generates a tailored CV + cover letter (markdown) from profile + offer data.
Deterministic baseline mode always available (no LLM key required).
Optional LLM enrichment via enrich_llm=1 (best-effort, falls back to baseline).
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Request

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.schemas.apply_pack import (
    ApplyPackMeta,
    ApplyPackRequest,
    ApplyPackResponse,
)
from apply_pack.generator_v0 import (
    build_cv_markdown,
    build_letter_markdown,
    compute_matched_missing,
)
from apply_pack.llm_enricher import enrich_with_llm

logger = logging.getLogger(__name__)

router = APIRouter(tags=["apply-pack"])


@router.post("/apply-pack", response_model=ApplyPackResponse)
async def apply_pack(payload: ApplyPackRequest, request: Request) -> ApplyPackResponse:
    """
    Generate a tailored CV + cover letter for an offer.

    - Baseline mode (no LLM): deterministic, always works.
    - LLM mode (enrich_llm=1): best-effort rewrite via OpenAI if key present.

    Returns: mode + cv_text + letter_text + meta + warnings.
    """
    request_id = getattr(request.state, "request_id", "n/a")

    profile_dict = payload.profile.model_dump()
    offer_dict = payload.offer.model_dump()

    profile_skills: list[str] = payload.profile.skills
    offer_skills: list[str] = payload.offer.skills

    # ── Compute matched / missing if not pre-supplied ─────────────────────────
    if payload.matched_core is not None and payload.missing_core is not None:
        matched = list(payload.matched_core)
        missing = list(payload.missing_core)
    else:
        matched, missing = compute_matched_missing(profile_skills, offer_skills)

    # ── Baseline generation ───────────────────────────────────────────────────
    cv_text = build_cv_markdown(profile_dict, offer_dict, matched, missing)
    letter_text = build_letter_markdown(profile_dict, offer_dict, matched, missing)
    mode = "baseline"
    warnings: list[str] = []

    # ── Optional LLM enrichment ───────────────────────────────────────────────
    if payload.enrich_llm == 1:
        cv_text, letter_text, llm_warnings = enrich_with_llm(
            cv_text=cv_text,
            letter_text=letter_text,
            offer_title=payload.offer.title,
            company=payload.offer.company or "",
        )
        if llm_warnings:
            warnings.extend(llm_warnings)
        else:
            mode = "baseline+llm"

    offer_id = payload.offer.id
    offer_title = payload.offer.title
    company = payload.offer.company or ""

    logger.info(
        "[apply-pack] mode=%s offer_id=%s matched=%d missing=%d cv_len=%d letter_len=%d request_id=%s",
        mode, offer_id, len(matched), len(missing), len(cv_text), len(letter_text), request_id,
    )

    return ApplyPackResponse(
        mode=mode,
        cv_text=cv_text,
        letter_text=letter_text,
        meta=ApplyPackMeta(
            offer_id=offer_id,
            offer_title=offer_title,
            company=company,
            matched_core=matched,
            missing_core=missing,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        warnings=warnings,
    )
