"""
profile_file.py — CV file upload + deterministic baseline parsing.

POST /profile/parse-file
  - Accepts PDF or TXT (multipart/form-data field: `file`)
  - Extracts text from the file
  - Runs deterministic baseline parsing (no LLM required)
  - Returns profile compatible with POST /inbox
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, Query
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.utils.pdf_text import PdfTextError, extract_text_from_pdf
from semantic.profile_cache import cache_profile_text, compute_profile_hash
from semantic.text_utils import hash_text
from api.utils.analyze_recovery_cache import PIPELINE_VERSION
from compass.profile_structurer import structure_profile_text_v1
from compass.canonical_pipeline import run_cv_pipeline, is_trace_enabled
from compass.domain_uris import build_domain_uris_for_text
from compass.promotion.apply_promotion import apply_profile_esco_promotion
from api.utils.profile_summary_builder import build_profile_summary
from api.utils.profile_summary_store import store_profile_summary

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


def _dev_tools_enabled() -> bool:
    elevia_dev_tools = os.getenv("ELEVIA_DEV_TOOLS", "").strip().lower()
    elevia_dev = os.getenv("ELEVIA_DEV", "").strip().lower()
    return elevia_dev_tools in {"1", "true", "yes", "on"} or elevia_dev in {"1", "true", "yes", "on"}


# ── Response schema ────────────────────────────────────────────────────────────

class ParseFileResponse(BaseModel):
    source: str
    mode: str = "baseline"
    pipeline_used: str = "canonical_compass"
    pipeline_variant: str = "canonical_compass_baseline"
    compass_e_enabled: bool = False
    domain_skills_active: List[str] = []
    domain_skills_pending_count: int = 0
    llm_fired: bool = False
    ai_available: bool = False
    ai_added_count: int = 0
    ai_error: Optional[str] = None
    filename: str
    content_type: str
    extracted_text_length: int
    extracted_text_hash: Optional[str] = None
    profile_fingerprint: Optional[str] = None
    recovery_pipeline_version: Optional[str] = None
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
    profile_cluster: Optional[dict] = None
    resolved_to_esco: List[dict] = []        # domain tokens → ESCO URI (injected into profile)
    skill_provenance: dict = {}              # {baseline_esco, library_token_to_esco, llm_token_to_esco}
    baseline_esco_count: int = 0            # skills_uri_count from ESCO baseline only
    injected_esco_from_domain: int = 0      # URIs added via DOMAIN→ESCO mapping
    total_esco_count: int = 0               # baseline + injected
    rejected_tokens: List[dict] = []        # [{token, token_norm, reason_code}] — debug/obs
    tight_candidates: List[str] = []       # phrase-level extraction (1–5 grams, pre-policy)
    tight_metrics: dict = {}               # raw_count, candidate_count, noise_ratio, tech_density


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

    if enrich_llm == 1 and not _dev_tools_enabled():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "legacy_llm_disabled",
                "message": "Legacy LLM enrichment is DEV-only. Use ELEVIA_DEV_TOOLS=1.",
                "request_id": request_id,
            },
        )

    # ── Canonical pipeline ────────────────────────────────────────────────────
    try:
        pipeline = run_cv_pipeline(
            cv_text,
            profile_id=f"file-{filename}",
            enrich_llm_legacy=(enrich_llm == 1),
        )
    except Exception as exc:
        logger.error("[parse-file] canonical pipeline error: %s request_id=%s", exc, request_id)
        raise HTTPException(status_code=500, detail="Extraction failed") from exc

    result = pipeline.baseline_result
    if enrich_llm == 1:
        pipeline_variant = "legacy_llm_enrichment"
    elif pipeline.compass_e_enabled:
        pipeline_variant = "canonical_compass_with_compass_e"
    else:
        pipeline_variant = "canonical_compass_baseline"
    mode = "llm" if (pipeline_variant == "legacy_llm_enrichment" and pipeline.legacy_llm_available and pipeline.legacy_llm_error is None) else "baseline"
    ai_available = pipeline.legacy_llm_available if enrich_llm == 1 else False
    ai_added_count = pipeline.legacy_llm_added_count if enrich_llm == 1 else 0
    ai_error: Optional[str] = pipeline.legacy_llm_error if enrich_llm == 1 else None

    logger.info(
        "[parse-file] filename=%s content_type=%s text_len=%d raw=%d validated=%d request_id=%s",
        filename, content_type, len(cv_text),
        result["raw_detected"], result["validated_skills"], request_id,
    )

    profile = result.get("profile") or {}
    profile_hash = compute_profile_hash(profile)
    cache_profile_text(profile_hash, cv_text)
    extracted_text_hash = hash_text(cv_text)

    # ── Profile summary cache (deterministic) ────────────────────────────────
    try:
        structured = structure_profile_text_v1(cv_text, debug=False)
        summary = build_profile_summary(structured, extra_skills=profile.get("skills"))
        store_profile_summary(profile_hash, summary.model_dump())
        if os.getenv("ELEVIA_DEBUG_PROFILE_SUMMARY", "").strip().lower() in {"1", "true", "yes", "on"}:
            logger.info(
                "PROFILE_SUMMARY_STORED profile_id=%s last_updated=%s",
                profile_hash,
                summary.last_updated,
            )
    except Exception as exc:
        logger.warning("[parse-file] profile summary failed: %s", type(exc).__name__)

    # ── Profile cluster (computed in canonical pipeline) ──────────────────────
    profile_cluster = pipeline.profile_cluster or {}
    logger.info(json.dumps({
        "event": "PROFILE_CLUSTER_DETECTED",
        "dominant_cluster": profile_cluster.get("dominant_cluster"),
        "dominance_percent": profile_cluster.get("dominance_percent"),
        "skills_count": profile_cluster.get("skills_count"),
        "request_id": request_id,
    }))
    cluster_key = (profile_cluster.get("dominant_cluster") or "").upper() or None
    esco_labels = result.get("validated_labels") or []

    # ── Tight extraction (phrase-level, case-insensitive, pre-policy) ─────────
    tight_candidates: List[str] = []
    tight_metrics: dict = {}
    try:
        from compass.extraction.tight_skill_extractor import extract_tight_skills
        _tight = extract_tight_skills(cv_text, cluster=cluster_key)
        tight_candidates = _tight.skill_candidates
        tight_metrics = _tight.metrics
    except Exception as exc:
        logger.warning("[parse-file] tight extraction failed: %s", type(exc).__name__)

    # ── Compass E enrichment (from canonical pipeline) ────────────────────────
    compass_e_on = pipeline.compass_e_enabled
    domain_skills_active: List[str] = pipeline.domain_skills_active
    domain_skills_pending_count = pipeline.domain_skills_pending_count
    llm_fired = pipeline.llm_fired
    resolved_to_esco: List[dict] = pipeline.resolved_to_esco
    rejected_tokens_list: List[dict] = pipeline.rejected_tokens[:50] if pipeline.rejected_tokens else []

    # Inject resolved ESCO URIs into profile.skills_uri (matching impact, no formula change)
    # extract_profile() reads profile["skills_uri"] — adding URIs here increases coverage.
    baseline_esco_count = result.get("skills_uri_count", 0)
    injected_esco_from_domain = 0
    if resolved_to_esco and profile:
        existing_uris: set = set(profile.get("skills_uri") or [])
        for r in resolved_to_esco:
            uri = r["esco_uri"]
            if uri not in existing_uris:
                existing_uris.add(uri)
                profile.setdefault("skills_uri", []).append(uri)
                injected_esco_from_domain += 1
                label = r.get("esco_label")
                if label:
                    skills_list = profile.setdefault("skills", [])
                    if label not in skills_list:
                        skills_list.append(label)
    total_esco_count = baseline_esco_count + injected_esco_from_domain

    # Inject DOMAIN URIs (active library tokens present in CV) into skills_uri
    domain_uris: List[str] = []
    domain_tokens: List[str] = []
    if cluster_key:
        try:
            domain_tokens, domain_uris = build_domain_uris_for_text(
                cv_text,
                esco_labels,
                cluster_key,
            )
        except Exception as exc:
            logger.warning("[parse-file] domain uri build failed: %s", type(exc).__name__)
    if domain_uris and profile:
        existing_uris: set = set(profile.get("skills_uri") or [])
        for uri in domain_uris:
            if uri not in existing_uris:
                existing_uris.add(uri)
                profile.setdefault("skills_uri", []).append(uri)
        profile["domain_uris"] = domain_uris
        profile["domain_uri_count"] = len(domain_uris)
        profile["domain_tokens"] = domain_tokens

    # Sprint 6 Step 2: ESCO promotion mapping (flag-gated)
    if profile:
        apply_profile_esco_promotion(
            profile,
            base_skills_uri=profile.get("skills_uri") or [],
            tight_candidates=tight_candidates,
            filtered_tokens=result.get("filtered_tokens") or [],
            cluster=cluster_key,
        )

    # Provenance summary (baseline_esco always present from validated_items)
    baseline_esco_labels = [
        str(item.get("label") or item.get("uri") or "")
        for item in result.get("validated_items", [])
        if isinstance(item, dict) and (item.get("label") or item.get("uri"))
    ]
    skill_provenance = {
        "baseline_esco": baseline_esco_labels,
        "library_token_to_esco": [
            r["token_normalized"] for r in resolved_to_esco
            if r.get("provenance") == "library_token_to_esco"
        ],
        "llm_token_to_esco": [
            r["token_normalized"] for r in resolved_to_esco
            if r.get("provenance") == "llm_token_to_esco"
        ],
    }

    # Build pipeline_used tag
    if is_trace_enabled():
        logger.info(
            "[PIPELINE_WIRING] parse-file pipeline_used=%s compass_e=%s domain_active=%d request_id=%s",
            pipeline_variant, compass_e_on, len(domain_skills_active), request_id,
        )

    profile_fingerprint: Optional[str] = None
    if extracted_text_hash and cluster_key:
        try:
            import hashlib
            profile_fingerprint = hashlib.sha256(
                f"{extracted_text_hash}|{cluster_key}|{PIPELINE_VERSION}".encode("utf-8")
            ).hexdigest()
        except Exception:
            profile_fingerprint = None

    return ParseFileResponse(
        source=result["source"],
        mode=mode,
        pipeline_used="canonical_compass",
        pipeline_variant=pipeline_variant,
        compass_e_enabled=compass_e_on,
        domain_skills_active=domain_skills_active,
        domain_skills_pending_count=domain_skills_pending_count,
        llm_fired=llm_fired,
        ai_available=ai_available,
        ai_added_count=ai_added_count,
        ai_error=ai_error,
        filename=filename,
        content_type=content_type,
        extracted_text_length=len(cv_text),
        extracted_text_hash=extracted_text_hash,
        profile_fingerprint=profile_fingerprint,
        recovery_pipeline_version=PIPELINE_VERSION,
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
        warnings=result.get("warnings", []) + warnings + pipeline.warnings,
        profile_cluster=profile_cluster,
        resolved_to_esco=resolved_to_esco,
        skill_provenance=skill_provenance,
        baseline_esco_count=baseline_esco_count,
        injected_esco_from_domain=injected_esco_from_domain,
        total_esco_count=total_esco_count,
        rejected_tokens=rejected_tokens_list,
        tight_candidates=tight_candidates,
        tight_metrics=tight_metrics,
    )
