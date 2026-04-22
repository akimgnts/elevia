from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, Optional

from api.utils.analyze_recovery_cache import PIPELINE_VERSION
from compass.ai_raw_cv_reconstruction import (
    RawCvReconstructionV1,
    build_raw_cv_reconstruction,
    raw_cv_reconstruction_enabled,
    skipped_raw_cv_reconstruction,
)
from compass.ai_profile_reconstruction import (
    build_profile_reconstruction,
)
from compass.canonical_pipeline import get_extracted_profile_snapshot, is_trace_enabled, run_cv_pipeline
from compass.extraction.enriched_concept_builder import build_enriched_concepts
from compass.extraction.enriched_signal_builder import build_enriched_signals
from compass.extraction.precanonical_recovery import build_precanonical_recovery
from compass.profile.profile_intelligence import build_profile_intelligence
from compass.profile.profile_intelligence_ai_assist import build_profile_intelligence_ai_assist

from .cache_hooks import run_profile_cache_hooks
from .canonical_mapping_stage import dedupe_by_canonical_key, run_canonical_mapping_stage, select_mapping_inputs
from .contracts import (
    EnrichedConceptStageResult,
    EnrichedSignalStageResult,
    ParseFilePipelineArtifacts,
    ParseFilePipelineRequest,
    ProfileIntelligenceAiAssistStageResult,
    ProfileIntelligenceStageResult,
)
from .dev_payload_builder import build_analyze_dev_payload, dev_tools_enabled
from .enrichment_stage import run_enrichment_stage
from .ingestion_stage import ingest_profile_file
from .matching_input_stage import build_matching_input_trace
from .response_builder import (
    build_parse_baseline_response_payload_from_artifacts,
    build_parse_file_response_payload_from_artifacts,
)
from .structured_extraction_stage import run_structured_extraction_stage
from .skill_candidate_stage import run_skill_candidate_stage
from .text_extraction_stage import extract_profile_text

logger = logging.getLogger(__name__)


def _count_sequence(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _experience_count(career_profile: Any) -> int:
    if isinstance(career_profile, dict):
        return _count_sequence(career_profile.get("experiences"))
    experiences = getattr(career_profile, "experiences", None)
    return _count_sequence(experiences)


def evaluate_ai_raw_cv_reconstruction_decision(context: Dict[str, Any]) -> Dict[str, object]:
    career_profile = context.get("career_profile") or {}
    metrics = {
        "experiences": _experience_count(career_profile),
        "structured_signal_units": _count_sequence(context.get("structured_signal_units")),
        "validated_items": _count_sequence(context.get("validated_items")),
        "canonical_skills": _count_sequence(context.get("canonical_skills")),
    }

    hard_blocks: list[str] = []
    weak_reasons: list[str] = []
    if metrics["structured_signal_units"] <= 3:
        weak_reasons.append("low_structured_signal")
    if metrics["validated_items"] <= 8:
        weak_reasons.append("low_validated_items")
    if metrics["canonical_skills"] <= 15:
        weak_reasons.append("low_canonical_skills")

    if metrics["experiences"] == 0 and weak_reasons:
        return {
            "enabled": True,
            "reasons": ["no_experience", *weak_reasons],
            "metrics": metrics,
        }

    if metrics["experiences"] >= 2 and metrics["structured_signal_units"] >= 5:
        hard_blocks.append("good_profile_experiences_and_structured_signal")
    if metrics["validated_items"] >= 10 and metrics["canonical_skills"] >= 20:
        hard_blocks.append("good_skills_signal")

    if hard_blocks:
        return {
            "enabled": False,
            "reasons": hard_blocks,
            "metrics": metrics,
        }

    return {
        "enabled": False,
        "reasons": ["insufficient_dirty_signals"],
        "metrics": metrics,
    }


def should_use_ai_raw_cv_reconstruction(context: Dict[str, Any]) -> bool:
    return bool(evaluate_ai_raw_cv_reconstruction_decision(context)["enabled"])


def _log_ai_raw_cv_reconstruction_decision(decision: Dict[str, object]) -> None:
    logger.info(
        json.dumps(
            {
                "event": "AI1_DECISION",
                "enabled": bool(decision.get("enabled")),
                "reasons": decision.get("reasons") or [],
                "metrics": decision.get("metrics") or {},
            }
        )
    )


def _ai_raw_cv_context_from_artifacts(artifacts: ParseFilePipelineArtifacts) -> Dict[str, object]:
    profile = artifacts.enrichment.profile if artifacts.enrichment else {}
    career_profile = profile.get("career_profile") if isinstance(profile, dict) else {}
    return {
        "career_profile": career_profile or {},
        "structured_signal_units": artifacts.structured_extraction.structured_units,
        "validated_items": artifacts.result.get("validated_items", []),
        "canonical_skills": artifacts.canonical_mapping.canonical_skills_list,
        "cv_text": artifacts.source_cv_text or artifacts.cv_text,
    }


def _run_profile_text_pipeline(
    *,
    cv_text: str,
    source_cv_text: Optional[str] = None,
    raw_cv_reconstruction: Optional[RawCvReconstructionV1] = None,
    request_id: str,
    profile_id: str,
    enrich_llm: int,
    filename: str,
    content_type: str,
) -> ParseFilePipelineArtifacts:
    original_cv_text = source_cv_text if source_cv_text is not None else cv_text
    reconstruction = raw_cv_reconstruction or skipped_raw_cv_reconstruction()
    pipeline = run_cv_pipeline(
        cv_text,
        profile_id=profile_id,
        enrich_llm_legacy=(enrich_llm == 1),
    )
    result = pipeline.baseline_result

    if enrich_llm == 1:
        pipeline_variant = "legacy_llm_enrichment"
    elif pipeline.compass_e_enabled:
        pipeline_variant = "canonical_compass_with_compass_e"
    else:
        pipeline_variant = "canonical_compass_baseline"
    mode = (
        "llm"
        if (
            pipeline_variant == "legacy_llm_enrichment"
            and pipeline.legacy_llm_available
            and pipeline.legacy_llm_error is None
        )
        else "baseline"
    )
    ai_available = pipeline.legacy_llm_available if enrich_llm == 1 else False
    ai_added_count = pipeline.legacy_llm_added_count if enrich_llm == 1 else 0
    ai_error: Optional[str] = pipeline.legacy_llm_error if enrich_llm == 1 else None

    logger.info(
        "[parse-file] filename=%s content_type=%s text_len=%d raw=%d validated=%d request_id=%s",
        filename,
        content_type,
        len(cv_text),
        result["raw_detected"],
        result["validated_skills"],
        request_id,
    )

    profile = get_extracted_profile_snapshot(pipeline)
    cache_result = run_profile_cache_hooks(cv_text=cv_text, profile=profile)

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

    skill_candidates = run_skill_candidate_stage(cv_text, cluster_key)
    precanonical_recovery = build_precanonical_recovery(cv_text)
    base_mapping_inputs = dedupe_by_canonical_key(
        list(select_mapping_inputs(skill_candidates))
        + list(precanonical_recovery.get("relevant_phrases") or [])
    )
    structured_extraction = run_structured_extraction_stage(
        cv_text=str(precanonical_recovery.get("cleaned_text") or cv_text),
        base_mapping_inputs=base_mapping_inputs,
    )
    enriched_signals = EnrichedSignalStageResult(
        enriched_signals=list(
            build_enriched_signals(
                structured_units=structured_extraction.structured_units,
                raw_text=cv_text,
            ).get("enriched_signals")
            or []
        ),
    )
    concept_signals = EnrichedConceptStageResult(
        concept_signals=list(
            build_enriched_concepts(
                enriched_signals.enriched_signals,
            ).get("concept_signals")
            or []
        ),
    )
    canonical_mapping = run_canonical_mapping_stage(
        request_id=request_id,
        cluster_key=cluster_key,
        skill_candidates=skill_candidates,
        structured_extraction=structured_extraction,
        cv_text=cv_text,
        validated_labels=esco_labels,
        base_mapping_inputs=base_mapping_inputs,
    )
    enrichment = run_enrichment_stage(
        cv_text=cv_text,
        profile=profile,
        result=result,
        cluster_key=cluster_key,
        esco_labels=esco_labels,
        pipeline_resolved_to_esco=pipeline.resolved_to_esco,
        pipeline_rejected_tokens=pipeline.rejected_tokens,
        canonical_mapping=canonical_mapping,
    )
    matching_input = build_matching_input_trace(
        baseline_esco_count=enrichment.baseline_esco_count,
        profile=enrichment.profile,
        stages=enrichment.matching_trace_stages,
    )
    profile_intelligence = ProfileIntelligenceStageResult(
        data=build_profile_intelligence(
            cv_text=cv_text,
            profile=enrichment.profile,
            profile_cluster=profile_cluster,
            top_signal_units=structured_extraction.top_signal_units,
            secondary_signal_units=structured_extraction.secondary_signal_units,
            preserved_explicit_skills=canonical_mapping.preserved_explicit_skills,
            profile_summary_skills=canonical_mapping.profile_summary_skills,
            canonical_skills=canonical_mapping.canonical_skills_list,
            enriched_signals=enriched_signals.enriched_signals,
        )
    )
    profile_intelligence_ai_assist = ProfileIntelligenceAiAssistStageResult(
        data=build_profile_intelligence_ai_assist(
            profile_intelligence=profile_intelligence.data,
            top_signal_units=structured_extraction.top_signal_units,
        )
    )
    profile_reconstruction = build_profile_reconstruction(
        {
            "cv_text": cv_text,
            "career_profile": enrichment.profile.get("career_profile") if isinstance(enrichment.profile, dict) else {},
            "structured_signal_units": structured_extraction.structured_units,
            "validated_items": result.get("validated_items", []),
            "canonical_skills": canonical_mapping.canonical_skills_list,
            "raw_cv_reconstruction": reconstruction.model_dump(),
            "profile_intelligence": profile_intelligence.data,
        }
    )

    if is_trace_enabled():
        logger.info(
            "[PIPELINE_WIRING] parse-file pipeline_used=%s compass_e=%s domain_active=%d request_id=%s",
            pipeline_variant,
            pipeline.compass_e_enabled,
            len(pipeline.domain_skills_active),
            request_id,
        )

    profile_fingerprint: Optional[str] = None
    if cache_result.extracted_text_hash and cluster_key:
        try:
            profile_fingerprint = hashlib.sha256(
                f"{cache_result.extracted_text_hash}|{cluster_key}|{PIPELINE_VERSION}".encode("utf-8")
            ).hexdigest()
        except Exception:
            profile_fingerprint = None

    artifacts = ParseFilePipelineArtifacts(
        result=result,
        pipeline_variant=pipeline_variant,
        mode=mode,
        compass_e_enabled=pipeline.compass_e_enabled,
        ai_available=ai_available,
        ai_added_count=ai_added_count,
        ai_error=ai_error,
        extracted_text_hash=cache_result.extracted_text_hash,
        profile_hash=cache_result.profile_hash,
        profile_fingerprint=profile_fingerprint,
        profile_cluster=profile_cluster,
        skill_candidates=skill_candidates,
        structured_extraction=structured_extraction,
        enriched_signals=enriched_signals,
        concept_signals=concept_signals,
        canonical_mapping=canonical_mapping,
        enrichment=enrichment,
        matching_input=matching_input,
        profile_intelligence=profile_intelligence,
        profile_intelligence_ai_assist=profile_intelligence_ai_assist,
        raw_cv_reconstruction=reconstruction,
        profile_reconstruction=profile_reconstruction,
        warnings=[],
        cv_text=cv_text,
        source_cv_text=original_cv_text,
        filename=filename,
        content_type=content_type,
        domain_skills_active=pipeline.domain_skills_active,
        domain_skills_pending_count=pipeline.domain_skills_pending_count,
        llm_fired=pipeline.llm_fired,
        pipeline_warnings=pipeline.warnings,
    )
    return artifacts


def build_parse_file_response_payload(request: ParseFilePipelineRequest) -> Dict[str, object]:
    ingestion = ingest_profile_file(request)
    extraction = extract_profile_text(ingestion)
    initial_artifacts = _run_profile_text_pipeline(
        cv_text=extraction.cv_text,
        source_cv_text=extraction.cv_text,
        raw_cv_reconstruction=skipped_raw_cv_reconstruction(),
        request_id=request.request_id,
        profile_id=f"file-{extraction.filename}",
        enrich_llm=request.enrich_llm,
        filename=extraction.filename,
        content_type=extraction.content_type,
    )

    context = _ai_raw_cv_context_from_artifacts(initial_artifacts)
    if raw_cv_reconstruction_enabled():
        decision = evaluate_ai_raw_cv_reconstruction_decision(context)
    else:
        base_metrics = evaluate_ai_raw_cv_reconstruction_decision(context)["metrics"]
        decision = {
            "enabled": False,
            "reasons": ["feature_flag_off"],
            "metrics": base_metrics,
        }
    _log_ai_raw_cv_reconstruction_decision(decision)

    if not bool(decision["enabled"]):
        response_payload = build_parse_file_response_payload_from_artifacts(initial_artifacts)
        if dev_tools_enabled():
            response_payload["analyze_dev"] = build_analyze_dev_payload(initial_artifacts)
        return response_payload

    raw_cv_reconstruction = build_raw_cv_reconstruction(
        cv_text=extraction.cv_text,
        request_id=request.request_id,
        filename=extraction.filename,
        content_type=extraction.content_type,
    )
    working_cv_text = (
        raw_cv_reconstruction.rebuilt_profile_text
        if raw_cv_reconstruction.status in {"ok", "partial"} and raw_cv_reconstruction.rebuilt_profile_text.strip()
        else extraction.cv_text
    )
    artifacts = _run_profile_text_pipeline(
        cv_text=working_cv_text,
        source_cv_text=extraction.cv_text,
        raw_cv_reconstruction=raw_cv_reconstruction,
        request_id=request.request_id,
        profile_id=f"file-{extraction.filename}",
        enrich_llm=request.enrich_llm,
        filename=extraction.filename,
        content_type=extraction.content_type,
    )

    response_payload = build_parse_file_response_payload_from_artifacts(artifacts)
    if dev_tools_enabled():
        response_payload["analyze_dev"] = build_analyze_dev_payload(artifacts)
    return response_payload


def build_parse_baseline_response_payload(*, cv_text: str, request_id: str) -> Dict[str, object]:
    stripped = cv_text.strip()
    artifacts = _run_profile_text_pipeline(
        cv_text=stripped,
        source_cv_text=stripped,
        raw_cv_reconstruction=skipped_raw_cv_reconstruction(),
        request_id=request_id,
        profile_id="baseline",
        enrich_llm=0,
        filename="baseline.txt",
        content_type="text/plain",
    )
    return build_parse_baseline_response_payload_from_artifacts(artifacts)
