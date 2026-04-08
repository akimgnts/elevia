"""
ai_justify.py — POST /ai/justify

Business-fit justification powered by the AI layer.
Interprets existing matching signals — never recalculates scores.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from ..schemas.ai_decision import (
    CvStrategy,
    JustificationMeta,
    JustificationPayload,
    JustifyFitRequest,
    JustifyFitResponse,
    NonSkillRequirement,
    TransferableStrength,
    TrueGap,
)
from ..utils.db import get_connection

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ai"])

# Lazy path injection — same pattern as applications.py
_src_root = Path(__file__).parent.parent.parent
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_offer(offer_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single offer row from fact_offers. Returns None if not found."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, title, company, description FROM fact_offers WHERE id = ?",
        (offer_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": str(row[0] or ""),
        "title": str(row[1] or ""),
        "company": str(row[2] or ""),
        "description": str(row[3] or ""),
        "cluster": "",
        "domains": [],
    }


def _extract_profile_meta(profile: Dict[str, Any]) -> tuple[str, str, List[str]]:
    """Extract (role, seniority, domains) from profile dict."""
    pi = profile.get("profile_intelligence") or {}
    role = str(
        pi.get("role_title")
        or profile.get("title")
        or profile.get("role")
        or "Non précisé"
    )
    seniority = str(pi.get("seniority") or profile.get("seniority") or "Non précisé")
    domains: List[str] = list(pi.get("domains") or profile.get("domains") or [])
    return role, seniority, domains


def _build_justification_payload(raw: dict) -> JustificationPayload:
    """Coerce the dict returned by justify_fit() into a JustificationPayload."""
    meta_raw = raw.get("meta") or {}

    true_gaps = [
        TrueGap(
            skill=g["skill"],
            severity=g["severity"],
            why=g["why"],
            mitigation=g.get("mitigation"),
        )
        for g in (raw.get("true_gaps") or [])
    ]

    non_skill = [
        NonSkillRequirement(
            text=r["text"],
            type=r["type"],
            why_not_gap=r["why_not_gap"],
        )
        for r in (raw.get("non_skill_requirements") or [])
    ]

    strengths = [
        TransferableStrength(
            strength=s["strength"],
            evidence=s["evidence"],
            relevance=s["relevance"],
        )
        for s in (raw.get("transferable_strengths") or [])
    ]

    cv_raw = raw.get("cv_strategy") or {}
    cv_strategy = CvStrategy(
        angle=cv_raw.get("angle", ""),
        focus=cv_raw.get("focus", ""),
        positioning_phrase=cv_raw.get("positioning_phrase", ""),
    )

    meta = JustificationMeta(
        offer_id=meta_raw.get("offer_id", ""),
        profile_id=meta_raw.get("profile_id"),
        duration_ms=int(meta_raw.get("duration_ms", 0)),
        llm_used=bool(meta_raw.get("llm_used", False)),
        fallback_used=bool(meta_raw.get("fallback_used", True)),
        model=meta_raw.get("model"),
    )

    return JustificationPayload(
        decision=raw.get("decision", "MAYBE"),
        fit_summary=raw.get("fit_summary", ""),
        true_gaps=true_gaps,
        non_skill_requirements=non_skill,
        transferable_strengths=strengths,
        cv_strategy=cv_strategy,
        application_effort=raw.get("application_effort", "MEDIUM"),
        confidence=float(raw.get("confidence", 0.7)),
        archetype=raw.get("archetype"),
        meta=meta,
    )


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/ai/justify", response_model=JustifyFitResponse)
async def justify_offer_fit(payload: JustifyFitRequest) -> JustifyFitResponse:
    """
    POST /ai/justify

    Produces AI-powered business-fit justification for one offer × profile pair.
    Interprets existing matching signals — never recalculates or overrides scores.

    Body:
      offer_id          — required, must exist in fact_offers
      profile           — full profile dict (same shape as /inbox payload)
      score             — optional; pre-computed matching score 0–100
      matched_skills    — skills confirmed by matching engine
      missing_skills    — skills flagged as gaps by matching engine
      canonical_skills  — canonical labels from CV parse pipeline
      enriched_signals  — enriched signal labels
      concept_signals   — concept-level signals
      profile_intelligence / offer_intelligence — pre-computed intelligence blobs
      include_cv        — if True, also generate a targeted CV document
    """
    t0 = time.time()

    # 1. Load offer from DB
    offer = _load_offer(payload.offer_id)
    if offer is None:
        raise HTTPException(status_code=404, detail=f"Offer not found: {payload.offer_id}")

    # 2. Extract profile metadata
    profile_role, profile_seniority, profile_domains = _extract_profile_meta(payload.profile)

    # 3. Merge offer_intelligence domains if available
    offer_intelligence = payload.offer_intelligence or {}
    offer_domains = list(
        offer_intelligence.get("canonical_domains")
        or offer.get("domains")
        or []
    )
    offer_cluster = str(
        offer_intelligence.get("cluster")
        or offer.get("cluster")
        or "GENERIC_TRANSVERSAL"
    )

    # 4. Call justification layer (never raises)
    from ai.justification_layer import justify_fit

    raw_result = justify_fit(
        offer_id=payload.offer_id,
        offer_title=offer.get("title", ""),
        offer_company=offer.get("company", ""),
        offer_description=offer.get("description", ""),
        offer_cluster=offer_cluster,
        offer_domains=offer_domains,
        score=payload.score,
        matched_skills=payload.matched_skills,
        missing_skills=payload.missing_skills,
        canonical_skills=payload.canonical_skills,
        enriched_signals=payload.enriched_signals,
        profile_role=profile_role,
        profile_seniority=profile_seniority,
        profile_domains=profile_domains,
        profile_id=payload.profile_id,
    )

    justification = _build_justification_payload(raw_result)

    # 5. Optional CV generation
    cv_document: Optional[Dict[str, Any]] = None
    if payload.include_cv:
        try:
            from documents.schemas import CvRequest
            from documents.cv_generator import generate_cv

            # Inject positioning phrase as strategy_hint for CV generation
            profile_with_hint = dict(payload.profile)
            profile_with_hint["strategy_hint"] = justification.cv_strategy.positioning_phrase

            cv_result = generate_cv(CvRequest(
                offer_id=payload.offer_id,
                profile=profile_with_hint,
            ))
            cv_document = cv_result if isinstance(cv_result, dict) else {"raw": str(cv_result)}
        except Exception as exc:
            logger.warning('{"event":"AI_JUSTIFY_CV_SKIP","reason":"%s"}', str(exc)[:120])

    duration_ms = int((time.time() - t0) * 1000)

    return JustifyFitResponse(
        ok=True,
        justification=justification,
        cv_document=cv_document,
        duration_ms=duration_ms,
    )
