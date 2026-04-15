"""
cv_generator.py — CV generation orchestration (Sprint CV Generator v1).

Pipeline per request:
  1. Resolve offer (DB direct query, no load_catalog_offers)
  2. Compute profile fingerprint (deterministic)
  3. Check cache → return immediately on hit
  4. Build deterministic targeted CV (build_targeted_cv)
  5. Cache write → return CvDocumentPayload

Constraints:
  - Zero modification to scoring core (apps/api/src/matching/*)
  - Fully deterministic — no LLM calls in this module
  - Logs: DOC_CV_* events (no payload dumps, no key values)
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import List, Optional

from .apply_pack_cv_engine import build_targeted_cv
from .cache import cache_get, cache_set, make_cache_key
from .schemas import (
    AtsNotes,
    CvDocumentPayload,
    CvMeta,
    CvRequest,
    ExperienceBlock,
    PROMPT_VERSION,
)

logger = logging.getLogger(__name__)

# documents/ → src/ → apps/api/  (3 levels, shallower than api/utils/ which is 4)
_DB_PATH = Path(__file__).parent.parent.parent / "data" / "db" / "offers.db"


# ── Structured logging ────────────────────────────────────────────────────────

def _log(event: str, **fields) -> None:
    """Emit Railway-compatible structured JSON log. No payload dumps."""
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False))


# ── Offer loading (DB-direct, no load_catalog_offers) ────────────────────────

def _load_offer(offer_id: str) -> Optional[dict]:
    """
    Load a single offer from SQLite by exact offer_id.
    Returns dict with id, title, description, company, country, is_vie.
    Never modifies scoring core.
    """
    if not _DB_PATH.exists():
        return None

    try:
        conn = sqlite3.connect(str(_DB_PATH), timeout=3)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT id, source, title, description, company, city, country, payload_json
            FROM fact_offers WHERE id = ?
            """,
            (offer_id,),
        ).fetchone()
        conn.close()

        if not row:
            return None

        offer = dict(row)

        # Extract is_vie from payload_json (bool-safe)
        if offer.get("payload_json"):
            try:
                payload = json.loads(offer["payload_json"])
                is_vie = payload.get("is_vie")
                if isinstance(is_vie, bool):
                    offer["is_vie"] = is_vie
                # Surface rich offer fields for CV generation (structured_v1, cv_strategy, skills)
                for field in ("structured_v1", "cv_strategy", "skills"):
                    if field in payload and offer.get(field) is None:
                        offer[field] = payload[field]
            except Exception:
                pass
        offer.pop("payload_json", None)
        return offer

    except Exception as exc:
        logger.warning(
            '{"event":"DOC_CV_OFFER_LOAD_ERROR","error_class":"%s"}',
            type(exc).__name__,
        )
        return None


# ── Profile fingerprint ───────────────────────────────────────────────────────

def _profile_fingerprint(profile: dict) -> str:
    """
    Deterministic fingerprint from skills + education + experiences.
    Includes career_profile.experiences completeness so the cache invalidates
    when the candidate reuploads a richer CV.
    Same profile → same fingerprint (order-independent).
    Returns 16 hex chars.
    """
    skills = sorted(str(s).lower().strip() for s in profile.get("skills", []) if s)
    education = profile.get("education") or []
    experiences = profile.get("experiences") or []
    # Include career_profile completeness as a cache-busting signal
    career_completeness = (profile.get("career_profile") or {}).get("completeness", 0.0)
    # Bust cache when identity becomes available (richer profile)
    identity_present = bool((profile.get("career_profile") or {}).get("identity"))
    raw = json.dumps(
        {
            "skills": skills,
            "education": education,
            "experiences": experiences,
            "career_completeness": career_completeness,
            "identity_present": identity_present,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ── Deterministic CV builder ──────────────────────────────────────────────────

def _build_fallback(
    profile: dict,
    offer: dict,
    keywords: List[str],
    fingerprint: str,
    offer_id: str,
    reason: str = "llm_disabled",
) -> CvDocumentPayload:
    """
    Build a deterministic targeted CV from profile data + offer data.
    """
    engineered = build_targeted_cv(profile=profile, offer=offer)

    _log(
        "DOC_CV_FALLBACK_USED",
        reason=reason,
        offer_id=offer_id,
        profile_fingerprint_short=fingerprint[:8],
    )

    return CvDocumentPayload(
        summary=engineered["summary"],
        keywords_injected=engineered["keywords_injected"],
        experience_blocks=[ExperienceBlock.model_validate(block) for block in engineered["experience_blocks"]],
        ats_notes=AtsNotes.model_validate(engineered["ats_notes"]),
        cv=engineered["cv"],
        debug=engineered["debug"],
        meta=CvMeta(
            offer_id=offer_id,
            profile_fingerprint=fingerprint,
            prompt_version=PROMPT_VERSION,
            cache_hit=False,
            fallback_used=True,
        ),
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_cv(req: CvRequest) -> CvDocumentPayload:
    """
    Orchestrate CV generation:
    cache hit → return | cache miss → LLM or fallback → cache → return.

    Logs: DOC_CV_REQUEST, DOC_CV_CACHE_HIT, DOC_CV_LLM_CALL, DOC_CV_OK,
          DOC_CV_FALLBACK_USED, DOC_CV_FAIL.
    """
    t0 = time.time()

    # 1. Resolve profile
    profile = req.profile or {}
    if not profile:
        profile = {}

    # 2. Resolve offer
    offer = _load_offer(req.offer_id)
    if not offer:
        _log("DOC_CV_FAIL", error_class="OfferNotFound", safe_message="offer not found in DB")
        raise ValueError(f"Offer not found: {req.offer_id}")

    # 3. Fingerprint
    fingerprint = _profile_fingerprint(profile)
    cache_key = make_cache_key(fingerprint, req.offer_id, PROMPT_VERSION)
    fingerprint_short = fingerprint[:8]

    _log(
        "DOC_CV_REQUEST",
        cache_key_short=cache_key[:12],
        offer_id=req.offer_id,
        profile_fingerprint_short=fingerprint_short,
        prompt_version=PROMPT_VERSION,
        lang=req.lang,
    )

    # 4. Cache lookup
    cached = cache_get(cache_key)
    if cached:
        _log("DOC_CV_CACHE_HIT", offer_id=req.offer_id, fingerprint_short=fingerprint_short)
        try:
            payload = CvDocumentPayload.model_validate(cached)
            payload = payload.model_copy(
                update={"meta": payload.meta.model_copy(update={"cache_hit": True})}
            )
            _log("DOC_CV_OK", duration_ms=int((time.time() - t0) * 1000), cache_hit=True)
            return payload
        except Exception:
            pass  # cache corrupt → regenerate

    # 4. Build deterministic CV
    payload = _build_fallback(
        profile=profile,
        offer=offer,
        keywords=[],
        fingerprint=fingerprint,
        offer_id=req.offer_id,
        reason="deterministic_engine",
    )

    # 5. Cache write (best-effort)
    cache_set(
        key=cache_key,
        doc_type="cv_v1",
        offer_id=req.offer_id,
        profile_fingerprint=fingerprint,
        prompt_version=PROMPT_VERSION,
        payload=payload.model_dump(),
    )

    duration_ms = int((time.time() - t0) * 1000)
    _log(
        "DOC_CV_OK",
        duration_ms=duration_ms,
        cache_hit=False,
        fallback_used=payload.meta.fallback_used,
        verdict_fields_present=bool(payload.summary and payload.ats_notes),
    )
    return payload


# ── Enrichment (deterministic reordering, no LLM) ────────────────────────────

def enrich_payload(
    payload: CvDocumentPayload,
    matched_core_skills: List[str],
) -> CvDocumentPayload:
    """
    Reorder CV payload to surface matched_core_skills first.

    keywords_injected: matched first (alpha), then rest (alpha).
    experience_blocks.tools: matched first (alpha), then rest (alpha).

    Contract:
      - Deterministic: same inputs → same output, no set iteration
      - No mutation: returns model_copy
      - No LLM. No scoring core.
    """
    if not matched_core_skills:
        return payload

    matched_norm = {s.lower().strip() for s in matched_core_skills if s and s.strip()}

    def _reorder(items: List[str]) -> List[str]:
        """Matched items first (alpha), rest after (alpha). Stable."""
        first = sorted(i for i in items if i.lower().strip() in matched_norm)
        rest = sorted(i for i in items if i.lower().strip() not in matched_norm)
        return first + rest

    new_keywords = _reorder(payload.keywords_injected)

    new_blocks: List[ExperienceBlock] = []
    for block in payload.experience_blocks:
        new_blocks.append(block.model_copy(update={"tools": _reorder(block.tools)}))

    return payload.model_copy(
        update={
            "keywords_injected": new_keywords,
            "experience_blocks": new_blocks,
        }
    )


# Public alias — lets routes load an offer without duplicating DB code
get_offer = _load_offer
