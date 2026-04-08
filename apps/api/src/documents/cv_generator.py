"""
cv_generator.py — CV generation orchestration (Sprint CV Generator v1).

Pipeline per request:
  1. Resolve offer (DB direct query, no load_catalog_offers)
  2. Compute profile fingerprint (deterministic)
  3. Check cache → return immediately on hit
  4. Extract ATS keywords (deterministic)
  5. If LLM available → call LLM → validate Pydantic → anti-lie filter → cache
  6. If LLM disabled/error → build deterministic fallback
  7. Return CvDocumentPayload

Constraints:
  - Zero modification to scoring core (apps/api/src/matching/*)
  - 1 LLM call max per cache miss
  - Logs: DOC_CV_* events (no payload dumps, no key values)
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import List, Optional, Tuple

from pydantic import ValidationError

from .apply_pack_cv_engine import build_targeted_cv
from .ats_keywords import extract_ats_keywords, keywords_overlap
from .cache import cache_get, cache_set, make_cache_key
from .llm_client import call_llm_json, is_llm_available
from .schemas import (
    AtsNotes,
    AutonomyEnum,
    CvDocumentPayload,
    CvMeta,
    CvRequest,
    ExperienceBlock,
    PROMPT_VERSION,
)

logger = logging.getLogger(__name__)

# documents/ → src/ → apps/api/  (3 levels, shallower than api/utils/ which is 4)
_DB_PATH = Path(__file__).parent.parent.parent / "data" / "db" / "offers.db"
_PROMPT_PATH = Path(__file__).parent / "prompt_cv_v1.txt"

_MAX_DESC_CHARS = 1200
_MAX_EXPERIENCES = 3
_MAX_KEYWORDS = 12


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
    raw = json.dumps(
        {
            "skills": skills,
            "education": education,
            "experiences": experiences,
            "career_completeness": career_completeness,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ── Anti-lie filter ───────────────────────────────────────────────────────────

def _antilies(
    payload: CvDocumentPayload,
    profile: dict,
    offer_keywords: List[str],
) -> CvDocumentPayload:
    """
    Filter fabricated content:
    - keywords_injected → only items from offer_keywords
    - tools → only items from profile skills
    Returns sanitized copy (no mutation).
    """
    profile_skills_norm = {s.lower().strip() for s in profile.get("skills", []) if s}
    kw_set = {k.lower() for k in offer_keywords}

    safe_keywords = [k for k in payload.keywords_injected if k.lower() in kw_set]

    safe_blocks: List[ExperienceBlock] = []
    for block in payload.experience_blocks:
        safe_tools = [t for t in block.tools if t.lower() in profile_skills_norm]
        safe_blocks.append(block.model_copy(update={"tools": safe_tools}))

    return payload.model_copy(
        update={
            "keywords_injected": safe_keywords,
            "experience_blocks": safe_blocks,
        }
    )


# ── Fallback builder (deterministic, no LLM) ─────────────────────────────────

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


# ── LLM prompt builder ────────────────────────────────────────────────────────

def _build_experiences_text(profile: dict) -> Tuple[str, int]:
    """
    Build the experiences text block for the LLM prompt.

    Priority:
      1. career_profile.experiences — rich data with bullets, achievements, tools
      2. profile.experiences        — basic dicts (title, company, duration)
      3. Empty fallback

    Returns (text, experience_count).
    """
    career_profile = profile.get("career_profile") or {}
    career_exps = career_profile.get("experiences") or []

    if career_exps:
        # Rich mode — bullets and achievements from CareerProfile
        lines: List[str] = []
        for exp in career_exps[:_MAX_EXPERIENCES]:
            if not isinstance(exp, dict):
                continue
            title = str(exp.get("title") or "").strip()
            company = str(exp.get("company") or "").strip()
            start = str(exp.get("start_date") or "").strip()
            end = str(exp.get("end_date") or "").strip()
            dates = f"{start} – {end}".strip(" –") if (start or end) else ""
            autonomy = str(exp.get("autonomy") or "").strip()

            header = f"--- {title}"
            if company:
                header += f" @ {company}"
            if dates:
                header += f" ({dates})"
            if autonomy:
                header += f" [{autonomy}]"
            lines.append(header)

            for resp in (exp.get("responsibilities") or [])[:4]:
                lines.append(f"  • {resp}")
            for ach in (exp.get("achievements") or [])[:2]:
                lines.append(f"  → Impact: {ach}")
            exp_tools = (exp.get("tools") or [])[:6]
            if exp_tools:
                lines.append(f"  Outils: {', '.join(exp_tools)}")

        return ("\n".join(lines) if lines else "(aucune expérience fournie)", len(career_exps))

    # Basic mode — legacy experience dicts
    experiences = profile.get("experiences") or []
    exp_lines: List[str] = []
    for exp in experiences[:_MAX_EXPERIENCES]:
        if not isinstance(exp, dict):
            continue
        t = str(exp.get("title") or exp.get("role") or "").strip()
        c = str(exp.get("company") or "").strip()
        d = str(exp.get("dates") or exp.get("duration") or exp.get("duree") or "").strip()
        if t:
            line = f"- {t}"
            if c:
                line += f" @ {c}"
            if d:
                line += f" ({d})"
            exp_lines.append(line)
    return ("\n".join(exp_lines) if exp_lines else "(aucune expérience fournie)", len(exp_lines))


def _build_prompt(
    offer: dict,
    profile: dict,
    keywords: List[str],
) -> Tuple[str, str]:
    """
    Build (system_prompt, user_prompt) from prompt_cv_v1.txt template.
    Truncates description to _MAX_DESC_CHARS. Allowlist of fields.

    Uses career_profile.experiences when available for richer experience text
    (includes responsibility bullets, achievements, and tools per experience).
    Falls back to basic experience list for legacy profiles.
    """
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    if "USER:" in template:
        sys_part, user_part = template.split("USER:", 1)
        system_prompt = sys_part.replace("SYSTEM:", "").strip()
        user_template = user_part.strip()
    else:
        system_prompt = "Réponds UNIQUEMENT en JSON valide. Aucun texte libre."
        user_template = template

    experiences_text, exp_count = _build_experiences_text(profile)

    desc_trunc = (offer.get("description") or "")[:_MAX_DESC_CHARS]
    user_prompt = (
        user_template
        .replace("{title}", offer.get("title") or "")
        .replace("{company}", offer.get("company") or "")
        .replace("{country}", offer.get("country") or "")
        .replace("{description_truncated}", desc_trunc)
        .replace("{keywords}", ", ".join(keywords))
        .replace("{skills}", ", ".join(str(s) for s in profile.get("skills", [])[:15]))
        .replace("{languages}", ", ".join(str(l) for l in profile.get("languages", [])))
        .replace("{education}", str(profile.get("education") or ""))
        .replace("{experiences_count}", str(exp_count))
        .replace("{experiences_text}", experiences_text)
    )

    return system_prompt, user_prompt


# ── LLM response → Pydantic ───────────────────────────────────────────────────

def _parse_llm_response(
    raw: dict,
    offer_id: str,
    fingerprint: str,
    cache_hit: bool = False,
) -> Optional[CvDocumentPayload]:
    """
    Validate LLM JSON against CvDocumentPayload schema.
    Injects meta. Returns None on validation failure.
    """
    try:
        # Inject meta (not sent to LLM)
        raw["meta"] = {
            "offer_id": offer_id,
            "profile_fingerprint": fingerprint,
            "prompt_version": PROMPT_VERSION,
            "cache_hit": cache_hit,
            "fallback_used": False,
        }
        return CvDocumentPayload.model_validate(raw)
    except (ValidationError, Exception) as exc:
        logger.warning(
            '{"event":"DOC_CV_SCHEMA_FAIL","error_class":"%s","detail":"%s"}',
            type(exc).__name__,
            str(exc)[:120].replace('"', "'"),
        )
        return None


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

    # 5. Deterministic targeted engine
    payload = _build_fallback(
        profile=profile,
        offer=offer,
        keywords=[],
        fingerprint=fingerprint,
        offer_id=req.offer_id,
        reason="deterministic_engine",
    )

    # 7. Cache write (best-effort)
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
