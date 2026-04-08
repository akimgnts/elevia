"""
ai_structure.py — POST /ai/structure-offer

Structured, noise-free rewrite of a job offer description.
Loads the raw description from fact_offers, calls offer_structurer,
returns 6 canonical blocks.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from ..schemas.offer_structure import (
    StructureOfferRequest,
    StructureOfferResponse,
    StructuredOfferMeta,
    StructuredOfferSummary,
)
from ..utils.db import get_connection

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ai"])

_src_root = Path(__file__).parent.parent.parent
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_offer_description(offer_id: str) -> str:
    conn = get_connection()
    row = conn.execute(
        "SELECT description FROM fact_offers WHERE id = ?",
        (offer_id,),
    ).fetchone()
    if not row:
        return ""
    return str(row[0] or "")


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/ai/structure-offer", response_model=StructureOfferResponse)
async def structure_offer_endpoint(payload: StructureOfferRequest) -> StructureOfferResponse:
    """
    POST /ai/structure-offer

    Structured, mission-first rewrite of a job offer in 7 blocks:
      quick_read · mission_summary · responsibilities · tools_environment ·
      role_context · key_requirements · nice_to_have

    Translates to French if the offer is in English.
    Eliminates: internal region codes (SouthAM, AMEA…), internal program
    names (Digital4Now, Learning Lab…), HR jargon.

    Body:
      offer_id        — required; must exist in fact_offers
      missions        — optional; pre-extracted mission bullets
      requirements    — optional; pre-extracted requirements
      tools_stack     — optional; pre-extracted tool mentions
      context_tags    — optional; context labels (vie, international, remote…)
    """
    t0 = time.time()

    description = _load_offer_description(payload.offer_id)
    if not description and not payload.missions:
        raise HTTPException(status_code=404, detail=f"Offer not found: {payload.offer_id}")

    from ai.offer_structurer import structure_offer

    raw = structure_offer(
        offer_id=payload.offer_id,
        description=description,
        missions=payload.missions,
        requirements=payload.requirements,
        tools_stack=payload.tools_stack,
        context_tags=payload.context_tags,
    )

    meta_raw: Dict[str, Any] = raw.get("meta") or {}
    summary = StructuredOfferSummary(
        quick_read=raw.get("quick_read", ""),
        mission_summary=raw.get("mission_summary", ""),
        responsibilities=raw.get("responsibilities", []),
        tools_environment=raw.get("tools_environment", []),
        role_context=raw.get("role_context", []),
        key_requirements=raw.get("key_requirements", []),
        nice_to_have=raw.get("nice_to_have", []),
        meta=StructuredOfferMeta(
            offer_id=meta_raw.get("offer_id", payload.offer_id),
            llm_used=bool(meta_raw.get("llm_used", False)),
            fallback_used=bool(meta_raw.get("fallback_used", True)),
            duration_ms=int(meta_raw.get("duration_ms", 0)),
            model=meta_raw.get("model"),
        ),
    )

    return StructureOfferResponse(
        ok=True,
        summary=summary,
        duration_ms=int((time.time() - t0) * 1000),
    )
