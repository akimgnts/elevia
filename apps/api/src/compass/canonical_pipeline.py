"""
compass/canonical_pipeline.py — Single canonical CV processing pipeline.

CANONICAL PIPELINE (CV):
  cv_text
    → run_baseline()                   # ESCO skill extraction (deterministic, always)
    → detect_profile_cluster()         # cluster key (DATA_IT / FINANCE / ...)
    → structure_profile_text_v1()      # experiences, education, certifications
    → build_profile_summary()          # compact profile panel cache
    → [COMPASS_E] enrich_cv()          # non-ESCO domain skills, cluster library update
    → response with pipeline_used tag

PIPELINE_USED tags:
  "baseline"               — ESCO only, no enrichment (COMPASS_E=0, enrich_llm=0)
  "baseline+llm_legacy"    — ESCO + old suggest_skills_from_cv (enrich_llm=1, COMPASS_E=0)
  "baseline+compass_e"     — ESCO + Compass E library enrichment (COMPASS_E=1, no LLM triggered)
  "baseline+compass_e+llm" — ESCO + Compass E + Compass E LLM trigger

FLAGS:
  ELEVIA_ENABLE_COMPASS_E=1     → enable Compass E layer (auto-on in local/dev if unset)
  ELEVIA_TRACE_PIPELINE_WIRING=1 → log detailed pipeline trace
  enrich_llm (query param)       → DEPRECATED: logs warning, still works for compat

SCORE INVARIANCE:
  score_core is NEVER read or written by this module.
  DOMAIN_SKILLS_ACTIVE are display/context only — NOT injected into matching weights.
  This pipeline returns enrichment metadata only; URI injection into matching
  inputs must remain explicit in the caller.
"""
from __future__ import annotations

from copy import deepcopy
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Environment flags ─────────────────────────────────────────────────────────

def is_compass_e_enabled() -> bool:
    """True when ELEVIA_ENABLE_COMPASS_E=1 or when running in local/dev (if unset)."""
    raw = os.getenv("ELEVIA_ENABLE_COMPASS_E")
    if raw is not None and raw.strip() != "":
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    env = os.getenv("ENV", "").strip().lower()
    debug = os.getenv("DEBUG", "").strip().lower()
    dev_tools = os.getenv("ELEVIA_DEV_TOOLS", "").strip().lower()
    elevia_dev = os.getenv("ELEVIA_DEV", "").strip().lower()
    is_dev = (
        env in {"dev", "local"} or
        debug in {"1", "true", "yes", "on"} or
        dev_tools in {"1", "true", "yes", "on"} or
        elevia_dev in {"1", "true", "yes", "on"}
    )
    return is_dev


def is_trace_enabled() -> bool:
    """True when ELEVIA_TRACE_PIPELINE_WIRING=1."""
    return os.getenv("ELEVIA_TRACE_PIPELINE_WIRING", "0").strip().lower() in {"1", "true", "yes", "on"}


# ── Result contract ───────────────────────────────────────────────────────────

@dataclass
class CVPipelineResult:
    """
    Unified result from the canonical CV pipeline.

    baseline_result: raw dict from run_baseline() (unchanged — ESCO fields)
    profile_cluster: dict from detect_profile_cluster()
    pipeline_used:   pipeline tag (e.g. "baseline+compass_e")
    domain_skills_active: ACTIVE Compass E skills for this cluster (display only)
    domain_skills_pending_count: # new PENDING tokens recorded
    compass_e_enabled: whether Compass E layer was run
    llm_fired: whether Compass E LLM was triggered

    score_core is NEVER present here.
    """
    baseline_result: Dict[str, Any]
    profile_cluster: Dict[str, Any] = field(default_factory=dict)
    pipeline_used: str = "baseline"
    domain_skills_active: List[str] = field(default_factory=list)
    domain_skills_pending_count: int = 0
    compass_e_enabled: bool = False
    llm_fired: bool = False
    resolved_to_esco: List[Dict[str, Any]] = field(default_factory=list)  # display-only
    rejected_tokens: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    legacy_llm_available: bool = False
    legacy_llm_added_count: int = 0
    legacy_llm_error: Optional[str] = None


def get_extracted_profile_snapshot(result: CVPipelineResult) -> Dict[str, Any]:
    """
    Return an isolated copy of the extraction-layer profile.

    Parsing/extraction owns the baseline profile shape. Any later enrichment or
    matching-preparation mutation must happen on a copy returned by this helper.
    """
    baseline_result = result.baseline_result or {}
    return deepcopy(baseline_result.get("profile") or {})


# ── Canonical pipeline ────────────────────────────────────────────────────────

def run_cv_pipeline(
    cv_text: str,
    *,
    profile_id: str = "default",
    enrich_llm_legacy: bool = False,
    compass_e_override: Optional[bool] = None,
) -> CVPipelineResult:
    """
    Single canonical entry point for CV processing.

    Args:
        cv_text:            Raw CV text (pre-extracted from file or direct input)
        profile_id:         Identifier for caching (e.g. "file-<name>")
        enrich_llm_legacy:  DEPRECATED — triggers old suggest_skills_from_cv() path.
                            Logs a deprecation warning. Still works for backwards compat.
        compass_e_override: Override ELEVIA_ENABLE_COMPASS_E env var (for testing).

    Returns:
        CVPipelineResult with baseline_result, profile_cluster, pipeline_used,
        and optionally domain_skills_active from Compass E.

    Score invariance: score_core is NEVER read or written here.
    """
    warnings: List[str] = []
    trace = is_trace_enabled()
    use_compass_e = compass_e_override if compass_e_override is not None else is_compass_e_enabled()
    legacy_llm_available = False
    legacy_llm_added_count = 0
    legacy_llm_error: Optional[str] = None

    if trace:
        logger.info(
            "[PIPELINE_WIRING] entry profile_id=%s enrich_llm_legacy=%s compass_e=%s",
            profile_id, enrich_llm_legacy, use_compass_e,
        )

    # ── 1. Baseline (ESCO, always runs) ───────────────────────────────────────
    from profile.baseline_parser import run_baseline, run_baseline_from_tokens  # local import

    baseline_result = run_baseline(cv_text, profile_id=profile_id)
    mode = "baseline"

    # ── 2. Legacy LLM enrichment (DEPRECATED) ─────────────────────────────────
    if enrich_llm_legacy:
        warnings.append(
            "DEPRECATED: enrich_llm=1 uses the legacy suggest_skills_from_cv() pipeline. "
            "Enable ELEVIA_ENABLE_COMPASS_E=1 for the canonical Compass E enrichment."
        )
        logger.warning(
            "[PIPELINE_WIRING] enrich_llm_legacy=True is DEPRECATED. "
            "Use ELEVIA_ENABLE_COMPASS_E=1 for canonical Compass E enrichment. profile_id=%s",
            profile_id,
        )
        try:
            from api.utils.env import get_llm_api_key  # local import
            from profile.llm_skill_suggester import suggest_skills_from_cv  # local import
            if get_llm_api_key():
                legacy_llm_available = True
                llm = suggest_skills_from_cv(cv_text)
                if llm.get("error"):
                    legacy_llm_error = "llm_failed"
                    llm_skills = []
                else:
                    llm_skills = (llm.get("skills") or [])
                if isinstance(llm_skills, list) and llm_skills:
                    base_tokens = baseline_result.get("skills_raw", [])
                    base_set = set(base_tokens)
                    new_tokens = [t for t in llm_skills if isinstance(t, str) and t not in base_set]
                    if new_tokens:
                        legacy_llm_added_count = len(new_tokens)
                        combined = base_tokens + new_tokens
                        baseline_result = run_baseline_from_tokens(
                            combined, profile_id=profile_id, source="llm"
                        )
                        mode = "baseline+llm_legacy"
            else:
                legacy_llm_error = "missing_openai_api_key"
        except Exception as exc:
            logger.warning("[PIPELINE_WIRING] legacy LLM enrichment failed: %s", type(exc).__name__)
            warnings.append(f"legacy_llm_failed: {type(exc).__name__}")
            legacy_llm_error = "llm_failed"

    # ── 3. Profile cluster ─────────────────────────────────────────────────────
    from profile.profile_cluster import detect_profile_cluster  # local import

    skills_for_cluster: List[str] = []
    validated_items = baseline_result.get("validated_items") or []
    if validated_items:
        skills_for_cluster = [
            str(item.get("label") or item.get("uri") or "")
            for item in validated_items if isinstance(item, dict)
        ]
        skills_for_cluster = [s for s in skills_for_cluster if s]
    if not skills_for_cluster:
        skills_for_cluster = baseline_result.get("skills_canonical") or []
    if not skills_for_cluster:
        skills_for_cluster = baseline_result.get("skills_raw") or []

    profile_cluster = detect_profile_cluster(skills_for_cluster)

    if trace:
        logger.info(
            "[PIPELINE_WIRING] cluster detected: %s (%.0f%%) profile_id=%s",
            profile_cluster.get("dominant_cluster"), profile_cluster.get("dominance_percent", 0), profile_id,
        )

    # ── 4. Compass E enrichment (conditional) ─────────────────────────────────
    domain_skills_active: List[str] = []
    domain_skills_pending_count = 0
    llm_fired = False
    resolved_to_esco: List[Dict[str, Any]] = []
    rejected_tokens: List[Dict[str, Any]] = []

    if use_compass_e:
        try:
            from compass.cv_enricher import enrich_cv  # local import
            esco_labels = baseline_result.get("validated_labels") or []
            cluster_key = (profile_cluster.get("dominant_cluster") or "").upper() or None
            enrichment = enrich_cv(
                cv_text=cv_text,
                cluster=cluster_key,
                esco_skills=esco_labels,
                llm_enabled=True,
            )
            domain_skills_active = enrichment.domain_skills_active
            domain_skills_pending_count = len(enrichment.domain_skills_pending)
            llm_fired = enrichment.llm_triggered
            resolved_to_esco = [r.model_dump() for r in enrichment.resolved_to_esco]
            rejected_tokens = enrichment.rejected_tokens[:50]

            if mode == "baseline+llm_legacy":
                mode = "baseline+llm_legacy+compass_e"
            elif llm_fired:
                mode = "baseline+compass_e+llm"
            else:
                mode = "baseline+compass_e"

            if trace:
                logger.info(
                    "[PIPELINE_WIRING] compass_e: active=%d pending=%d llm_fired=%s profile_id=%s",
                    len(domain_skills_active), domain_skills_pending_count, llm_fired, profile_id,
                )
        except Exception as exc:
            logger.warning(
                "[PIPELINE_WIRING] Compass E enrichment failed (non-fatal): %s profile_id=%s",
                type(exc).__name__, profile_id,
            )
            warnings.append(f"compass_e_failed: {type(exc).__name__}")

    if trace:
        logger.info(
            "[PIPELINE_WIRING] done pipeline_used=%s domain_active=%d profile_id=%s",
            mode, len(domain_skills_active), profile_id,
        )

    return CVPipelineResult(
        baseline_result=baseline_result,
        profile_cluster=profile_cluster,
        pipeline_used=mode,
        domain_skills_active=domain_skills_active,
        domain_skills_pending_count=domain_skills_pending_count,
        compass_e_enabled=use_compass_e,
        llm_fired=llm_fired,
        resolved_to_esco=resolved_to_esco,
        rejected_tokens=rejected_tokens,
        warnings=warnings,
        legacy_llm_available=legacy_llm_available,
        legacy_llm_added_count=legacy_llm_added_count,
        legacy_llm_error=legacy_llm_error,
    )
