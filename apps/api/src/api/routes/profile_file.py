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

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[\w.-]+\b", re.IGNORECASE)
_URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
_DOMAIN_RE = re.compile(r"\b[\w-]+(?:\.|\s)(com|fr|net|org|io|co|edu|gov)\b", re.IGNORECASE)
_LINKEDIN_RE = re.compile(r"\blinkedin\.com/\S+|\blinkedin\b", re.IGNORECASE)
_GITHUB_RE = re.compile(r"\bgithub\.com/\S+|\bgithub\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
_SHORT_PHONE_RE = re.compile(r"\b\d{2}\s?\d{2}\b")
_DATE_RE = re.compile(r"\b(19|20)\d{2}([-/\s](19|20)?\d{2})?\b")
_NUMERIC_ONLY_RE = re.compile(r"^\d+$")


def _safe_filename(name: str) -> str:
    """Strip path components and non-safe chars from filename."""
    base = Path(name).name  # strip directories
    return _SAFE_FILENAME_RE.sub("_", base)[:128]


def _filter_noise_candidates(candidates: List[str]) -> tuple[List[str], List[str]]:
    filtered: List[str] = []
    removed: List[str] = []
    seen_removed: set = set()

    for raw in candidates:
        if not isinstance(raw, str):
            continue
        token = raw.strip()
        if not token:
            continue

        reason = None
        token_compact = re.sub(r"\s+", " ", token)
        if _EMAIL_RE.search(token):
            reason = "email"
        elif _URL_RE.search(token):
            reason = "url"
        elif _DOMAIN_RE.search(token_compact):
            reason = "domain"
        elif _LINKEDIN_RE.search(token):
            reason = "linkedin"
        elif _GITHUB_RE.search(token):
            reason = "github"
        elif _PHONE_RE.search(token) or _SHORT_PHONE_RE.search(token):
            reason = "phone"
        elif _DATE_RE.search(token):
            reason = "date"
        elif _NUMERIC_ONLY_RE.match(token.replace(" ", "")):
            reason = "numeric"

        if reason:
            if token not in seen_removed:
                removed.append(token)
                seen_removed.add(token)
            continue

        filtered.append(token)

    return filtered, removed


def _flag_enabled(name: str) -> bool:
    raw = os.getenv(name, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


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
    # Canonical mapping layer (Sprint 0700)
    canonical_skills: List[dict] = []      # [{raw, canonical_id, label, strategy, confidence}]
    canonical_skills_count: int = 0        # number of resolved canonical skills (synonym+tool)
    canonical_hierarchy_added: List[str] = []  # parent IDs added by 1-level expansion
    # Skill proximity layer (display-only, non-scoring)
    skill_proximity_links: List[dict] = []
    skill_proximity_count: int = 0
    skill_proximity_summary: dict = {}
    # Analyze Dev Mode (DEV-only, optional)
    analyze_dev: Optional[dict] = None


# ── Route ──────────────────────────────────────────────────────────────────────

@router.post(
    "/profile/parse-file",
    response_model=ParseFileResponse,
    response_model_exclude_unset=True,
)
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
    noise_removed: List[str] = []
    split_chunks: List[str] = []
    cleaned_chunks: List[str] = []
    mapping_inputs: List[str] = []
    lemmatized_chunks_count = 0
    pos_rejected_count = 0
    enable_phrase_split = _flag_enabled("ELEVIA_ENABLE_PHRASE_SPLITTING")
    enable_chunk_normalizer = _flag_enabled("ELEVIA_ENABLE_CHUNK_NORMALIZER")
    enable_lemmatization = _flag_enabled("ELEVIA_ENABLE_LIGHT_LEMMATIZATION")
    enable_pos_filter = _flag_enabled("ELEVIA_ENABLE_POS_FILTER")
    try:
        from compass.extraction.tight_skill_extractor import extract_tight_skills
        from compass.extraction.phrase_cleaner import split_phrases, clean_chunks
        _tight = extract_tight_skills(cv_text, cluster=cluster_key)
        tight_candidates, noise_removed = _filter_noise_candidates(_tight.skill_candidates)
        if enable_phrase_split:
            split_chunks = split_phrases(tight_candidates)
        if enable_chunk_normalizer:
            base_chunks = split_chunks if split_chunks else tight_candidates
            _clean = clean_chunks(
                base_chunks,
                enable_lemmatization=enable_lemmatization,
                enable_pos_filter=enable_pos_filter,
            )
            cleaned_chunks = _clean.cleaned_chunks
            lemmatized_chunks_count = _clean.lemmatized_count
            pos_rejected_count = _clean.pos_rejected_count
        tight_metrics = dict(_tight.metrics or {})
        tight_metrics["candidate_count"] = len(tight_candidates)
    except Exception as exc:
        logger.warning("[parse-file] tight extraction failed: %s", type(exc).__name__)

    # ── Canonical mapping layer (Sprint 0700) ────────────────────────────────
    # Maps tight_candidates → canonical skill IDs + 1-level hierarchy expansion.
    # Output is display-only (canonical_skills field) and enriches ESCO promotion
    # input with canonical labels (more ESCO-friendly than raw phrases).
    canonical_skills_list: List[dict] = []
    canonical_hierarchy_added: List[str] = []
    canonical_enriched_labels: List[str] = []  # fed into apply_profile_esco_promotion
    resolved_ids: List[str] = []  # canonical_ids resolved — also used by esco_bridge
    canonical_stats = {
        "matched_count": 0,
        "unresolved_count": 0,
        "synonym_count": 0,
        "tool_count": 0,
    }
    expansion_map: dict = {}
    expanded_ids: List[str] = []
    try:
        from compass.canonical.canonical_mapper import map_to_canonical
        from compass.canonical.hierarchy_expander import expand_hierarchy
        if cleaned_chunks:
            mapping_inputs = cleaned_chunks
        elif split_chunks:
            mapping_inputs = split_chunks
        else:
            mapping_inputs = tight_candidates
        _cmap = map_to_canonical(mapping_inputs, cluster=cluster_key)
        # Store display payload
        canonical_skills_list = [
            {
                "raw": m.raw,
                "canonical_id": m.canonical_id,
                "label": m.label,
                "strategy": m.strategy,
                "confidence": m.confidence,
                "cluster_name": m.cluster_name,
                "genericity_score": m.genericity_score,
            }
            for m in _cmap.mappings
        ]
        canonical_stats = {
            "matched_count": _cmap.matched_count,
            "unresolved_count": _cmap.unresolved_count,
            "synonym_count": _cmap.synonym_count,
            "tool_count": _cmap.tool_count,
        }
        # Expand 1 level — adds parents only when not already present
        resolved_ids = list(dict.fromkeys(m.canonical_id for m in _cmap.mappings if m.canonical_id))
        _exp = expand_hierarchy(resolved_ids)
        canonical_hierarchy_added = _exp.added_parents
        expansion_map = _exp.expansion_map
        expanded_ids = _exp.expanded_ids
        # Build enriched label list: canonical labels (resolved) + raw tight (fallback for unresolved)
        # This improves ESCO promotion hit-rate for non-English / aliased skills
        resolved_labels = [m.label for m in _cmap.mappings if m.label]
        canonical_enriched_labels = list(dict.fromkeys(resolved_labels + mapping_inputs))
        if _cmap.matched_count or canonical_hierarchy_added:
            logger.info(json.dumps({
                "event": "CANONICAL_MAPPING",
                "cluster": cluster_key,
                "raw_in": len(tight_candidates),
                "matched": _cmap.matched_count,
                "synonym": _cmap.synonym_count,
                "tool": _cmap.tool_count,
                "unresolved": _cmap.unresolved_count,
                "hierarchy_added": len(canonical_hierarchy_added),
                "request_id": request_id,
            }))
    except Exception as exc:
        logger.warning("[parse-file] canonical mapping failed: %s", type(exc).__name__)
        canonical_enriched_labels = tight_candidates  # safe fallback

    # ── Skill proximity layer (non-scoring, display-only) ───────────────────
    skill_proximity_links: List[dict] = []
    skill_proximity_summary: dict = {}
    skill_proximity_count = 0
    try:
        from compass.canonical.skill_proximity import compute_skill_proximity
        _prox = compute_skill_proximity(resolved_ids, resolved_ids)
        skill_proximity_links = _prox.get("links", [])
        skill_proximity_summary = _prox.get("summary", {})
        skill_proximity_count = int(
            skill_proximity_summary.get("match_count", len(skill_proximity_links))
        )
    except Exception as exc:
        logger.warning("[parse-file] skill proximity failed: %s", type(exc).__name__)

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
    domain_debug: dict = {}
    if cluster_key:
        try:
            domain_tokens, domain_uris, domain_debug = build_domain_uris_for_text(
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

    # Sprint 6 Step 2 + Sprint 0700: ESCO promotion mapping (flag-gated).
    # canonical_enriched_labels: canonical labels first, raw tight_candidates as fallback.
    # This improves ESCO promotion hit-rate without any formula change.
    if profile:
        apply_profile_esco_promotion(
            profile,
            base_skills_uri=profile.get("skills_uri") or [],
            tight_candidates=canonical_enriched_labels or tight_candidates,
            filtered_tokens=result.get("filtered_tokens") or [],
            cluster=cluster_key,
        )

    # Sprint 0700 Step 3: Canonical → ESCO bridge (additive, flag-gated).
    # Uses esco_fr_label from canonical store to look up verified ESCO URIs.
    # Merges with any URIs already set by apply_profile_esco_promotion().
    # Canonical IDs (skill:xxx) are NEVER injected here — only ESCO URIs.
    if profile:
        try:
            from compass.canonical.esco_bridge import build_canonical_esco_promoted
            _bridge_uris = build_canonical_esco_promoted(
                resolved_ids,
                base_skills_uri=profile.get("skills_uri") or [],
                cluster=cluster_key,
            )
            if _bridge_uris:
                _existing_promoted = profile.get("skills_uri_promoted") or []
                profile["skills_uri_promoted"] = list(
                    dict.fromkeys(_existing_promoted + _bridge_uris)
                )
        except Exception as _bridge_exc:
            logger.warning("[parse-file] canonical esco bridge failed: %s", type(_bridge_exc).__name__)

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

    response_payload = dict(
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
        canonical_skills=canonical_skills_list,
        canonical_skills_count=sum(1 for m in canonical_skills_list if m.get("canonical_id")),
        canonical_hierarchy_added=canonical_hierarchy_added,
        skill_proximity_links=skill_proximity_links,
        skill_proximity_count=skill_proximity_count,
        skill_proximity_summary=skill_proximity_summary,
    )

    if _dev_tools_enabled():
        promoted_uris = list(profile.get("skills_uri_promoted") or []) if profile else []
        if cleaned_chunks:
            mapping_count_base = len(cleaned_chunks)
        elif split_chunks:
            mapping_count_base = len(split_chunks)
        else:
            mapping_count_base = len(tight_candidates)
        canonical_success_rate = round(
            (canonical_stats["matched_count"] / mapping_count_base) if mapping_count_base else 0.0, 4
        )
        compass_skill_candidates = int(domain_debug.get("candidates_count", 0) or 0)
        compass_skill_rejected = int(domain_debug.get("rejected_count", 0) or 0)
        analyze_dev = {
            "raw_extraction": {
                "raw_extracted_skills": result.get("skills_raw", []),
                "raw_tokens": result.get("raw_tokens", []),
                "raw_detected": result.get("raw_detected", 0),
                "validated_labels": result.get("validated_labels", []),
            },
            "tight_candidates": {
                "items": tight_candidates,
                "count": len(tight_candidates),
                "top_candidates": tight_candidates[:30],
                "top_filtered": (tight_metrics.get("top_dropped") or [])[:30],
                "split_examples": (tight_metrics.get("split_examples") or [])[:30],
                "cv_structure_rejected_count": tight_metrics.get("cv_structure_rejected_count", 0),
                "cv_structure_rejected_examples": (tight_metrics.get("cv_structure_rejected_examples") or [])[:10],
                "guardrail_scope_mode": tight_metrics.get("guardrail_scope_mode", "unknown"),
                "final_guardrail_rejected_count": tight_metrics.get("final_guardrail_rejected_count", 0),
                "final_guardrail_examples": (tight_metrics.get("final_guardrail_examples") or [])[:10],
            },
            "tight_split_trace": [],
            "tight_selection_trace": (tight_metrics.get("selection_trace") or [])[:30],
            "top_candidates_source": "final_tight_candidates_post_filter",
            "mapping_inputs_source": "",
            "mapping_inputs_preview": [],
            "split_chunks": split_chunks,
            "split_chunks_count": len(split_chunks),
            "cleaned_chunks": cleaned_chunks,
            "cleaned_chunks_count": len(cleaned_chunks),
            "lemmatized_chunks_count": lemmatized_chunks_count,
            "pos_rejected_count": pos_rejected_count,
            "stage_flags": {
                "phrase_splitting": enable_phrase_split,
                "chunk_normalizer": enable_chunk_normalizer,
                "light_lemmatization": enable_lemmatization,
                "pos_filter": enable_pos_filter,
            },
            "noise_removed": noise_removed[:200],
            "canonical_mapping": {
                "mappings": canonical_skills_list,
                "matched_count": canonical_stats["matched_count"],
                "unresolved_count": canonical_stats["unresolved_count"],
                "synonym_count": canonical_stats["synonym_count"],
                "tool_count": canonical_stats["tool_count"],
            },
            "hierarchy_expansion": {
                "input_ids": resolved_ids,
                "added_parents": canonical_hierarchy_added,
                "expansion_map": expansion_map,
                "expanded_ids": expanded_ids or resolved_ids,
            },
            "esco_promotion": {
                "canonical_labels": canonical_enriched_labels,
                "skills_uri_promoted": promoted_uris,
                "promoted_uri_count": len(promoted_uris),
            },
            "proximity": {
                "links": skill_proximity_links,
                "summary": skill_proximity_summary,
                "count": skill_proximity_count,
            },
            "explainability": {
                "status": "not_computed_here",
                "reason": "not_available_at_parse_stage",
            },
            "counters": {
                "raw_count": int(result.get("raw_detected", 0) or 0),
                "tight_count": len(tight_candidates),
                "split_chunks_count": len(split_chunks),
                "cleaned_chunks_count": len(cleaned_chunks),
                "lemmatized_chunks_count": lemmatized_chunks_count,
                "pos_rejected_count": pos_rejected_count,
                "canonical_count": int(canonical_stats["matched_count"]),
                "unresolved_count": int(canonical_stats["unresolved_count"]),
                "expanded_count": len(canonical_hierarchy_added),
                "promoted_uri_count": len(promoted_uris),
                "near_match_count": int(skill_proximity_count),
                "noise_removed_count": len(noise_removed),
                "canonical_success_rate": canonical_success_rate,
                "compass_skill_candidates": compass_skill_candidates,
                "compass_skill_rejected": compass_skill_rejected,
                "cv_structure_rejected_count": int(tight_metrics.get("cv_structure_rejected_count", 0) or 0),
                "tight_single_token_count": int(tight_metrics.get("single_token_count", 0) or 0),
                "tight_generic_rejected_count": int(tight_metrics.get("generic_rejected_count", 0) or 0),
                "tight_numeric_rejected_count": int(tight_metrics.get("numeric_rejected_count", 0) or 0),
                "tight_repeated_fragment_count": int(tight_metrics.get("repeated_fragment_count", 0) or 0),
                "tight_filtered_out_count": int(tight_metrics.get("filtered_out_count", 0) or 0),
                "tight_split_generated_count": int(tight_metrics.get("split_generated_count", 0) or 0),
                "broken_token_repair_count": int(tight_metrics.get("broken_token_repair_count", 0) or 0),
                "generated_composite_rejected_count": int(tight_metrics.get("generated_composite_rejected_count", 0) or 0),
            },
        }
        analyze_dev["broken_token_repair_examples"] = (tight_metrics.get("broken_token_repair_examples") or [])[:20]
        # Mapping inputs source/preview (debug)
        if cleaned_chunks:
            analyze_dev["mapping_inputs_source"] = "cleaned_chunks_post_normalizer"
            analyze_dev["mapping_inputs_preview"] = cleaned_chunks[:20]
        elif split_chunks:
            analyze_dev["mapping_inputs_source"] = "split_chunks_post_noise_filter"
            analyze_dev["mapping_inputs_preview"] = split_chunks[:20]
        else:
            analyze_dev["mapping_inputs_source"] = "final_tight_candidates_post_filter"
            analyze_dev["mapping_inputs_preview"] = tight_candidates[:20]

        # Build split survival trace with canonical reach visibility
        trace_raw = tight_metrics.get("split_trace") or []
        mapping_set = {s.lower() for s in (mapping_inputs or []) if isinstance(s, str)}
        final_set = {s.lower() for s in (tight_candidates or []) if isinstance(s, str)}
        trace_final = []
        for item in trace_raw:
            source = item.get("source")
            generated = item.get("generated") or []
            inserted = item.get("inserted") or []
            survived = item.get("survived_final_tight") or []
            dropped = item.get("dropped") or []
            survived_after_filter = [c for c in survived if c.lower() in final_set]
            present_in_mapping = [c for c in survived_after_filter if c.lower() in mapping_set]
            trace_final.append({
                "source": source,
                "generated": generated,
                "inserted": inserted,
                "survived_after_filter": survived_after_filter,
                "present_in_final_tight": survived_after_filter,
                "present_in_mapping_inputs": present_in_mapping,
                "dropped": dropped,
            })
        analyze_dev["tight_split_trace"] = trace_final[:30]
        response_payload["analyze_dev"] = analyze_dev

    return ParseFileResponse(**response_payload)
