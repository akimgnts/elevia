from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from api.utils.profile_summary_builder import build_profile_summary
from api.utils.profile_summary_store import store_profile_summary
from compass.profile_structurer import structure_profile_text_v1
from compass.structuring import ProfileEnrichmentAgent, ProfileStructuringAgent
from documents.career_profile import from_profile_structured_v1, load_career_profile, to_experience_dicts
from semantic.profile_cache import cache_profile_text, compute_profile_hash
from semantic.text_utils import hash_text

from .contracts import CacheHookResult

logger = logging.getLogger(__name__)


def _explicit_or_profile_list(
    explicit: list[Dict[str, Any]] | None,
    profile: Dict[str, Any],
    *profile_keys: str,
) -> list[Dict[str, Any]]:
    if explicit is not None:
        return list(explicit)
    for key in profile_keys:
        value = profile.get(key)
        if value is not None:
            return list(value)
    return []


def _identity_present(profile: Dict[str, Any]) -> bool:
    identity = profile.get("identity")
    if isinstance(identity, dict) and any(identity.get(key) for key in ("full_name", "email", "phone", "linkedin", "location")):
        return True
    career_profile = profile.get("career_profile")
    if isinstance(career_profile, dict):
        cp_identity = career_profile.get("identity")
        if isinstance(cp_identity, dict) and any(
            cp_identity.get(key) for key in ("full_name", "email", "phone", "linkedin", "location")
        ):
            return True
    return any(profile.get(key) for key in ("full_name", "email", "phone", "linkedin", "location"))


def _legacy_experience_count(profile: Dict[str, Any]) -> int:
    experiences = profile.get("experiences")
    if isinstance(experiences, list):
        return len(experiences)
    career_profile = profile.get("career_profile")
    if isinstance(career_profile, dict):
        cp_experiences = career_profile.get("experiences")
        if isinstance(cp_experiences, list):
            return len(cp_experiences)
    return 0


def _legacy_education_count(profile: Dict[str, Any]) -> int:
    education = profile.get("education")
    if isinstance(education, list):
        return len(education)
    career_profile = profile.get("career_profile")
    if isinstance(career_profile, dict):
        cp_education = career_profile.get("education")
        if isinstance(cp_education, list):
            return len(cp_education)
    return 0


def _augment_document_understanding_comparison_metrics(
    *,
    profile_snapshot: Dict[str, Any],
    document_understanding: Dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(document_understanding, dict):
        return {}

    diagnostics = document_understanding.setdefault("parsing_diagnostics", {})
    if not isinstance(diagnostics, dict):
        diagnostics = {}
        document_understanding["parsing_diagnostics"] = diagnostics

    comparison_metrics = diagnostics.setdefault("comparison_metrics", {})
    if not isinstance(comparison_metrics, dict):
        comparison_metrics = {}
        diagnostics["comparison_metrics"] = comparison_metrics

    identity = document_understanding.get("identity")
    if not isinstance(identity, dict):
        identity = {}

    experience_blocks = document_understanding.get("experience_blocks")
    if not isinstance(experience_blocks, list):
        experience_blocks = []

    project_blocks = document_understanding.get("project_blocks")
    if not isinstance(project_blocks, list):
        project_blocks = []

    suspicious_merges = diagnostics.get("suspicious_merges")
    if not isinstance(suspicious_merges, list):
        suspicious_merges = []

    orphan_lines = diagnostics.get("orphan_lines")
    if not isinstance(orphan_lines, list):
        orphan_lines = []

    comparison_metrics["identity_detected_legacy"] = _identity_present(profile_snapshot)
    comparison_metrics["identity_detected_understanding"] = bool(any(identity.values()))
    comparison_metrics["experience_count_legacy"] = _legacy_experience_count(profile_snapshot)
    comparison_metrics["experience_count_understanding"] = len(experience_blocks)
    comparison_metrics["project_count_understanding"] = len(project_blocks)
    comparison_metrics["suspicious_merges_count"] = len(suspicious_merges)
    comparison_metrics["orphan_lines_count"] = len(orphan_lines)
    comparison_metrics["invalid_experience_headers_count"] = int(
        comparison_metrics.get("invalid_experience_headers_count", 0) or 0
    )

    comparison_metrics.setdefault("identity_detected", comparison_metrics["identity_detected_understanding"])
    comparison_metrics.setdefault("experience_blocks_count", comparison_metrics["experience_count_understanding"])
    comparison_metrics.setdefault("project_blocks_count", comparison_metrics["project_count_understanding"])
    comparison_metrics.setdefault("legacy_experiences_count", comparison_metrics["experience_count_legacy"])
    comparison_metrics.setdefault("legacy_education_count", _legacy_education_count(profile_snapshot))
    comparison_metrics["experience_count_delta_vs_legacy"] = (
        int(comparison_metrics["experience_count_understanding"]) - int(comparison_metrics["experience_count_legacy"])
    )
    comparison_metrics["education_count_delta_vs_legacy"] = (
        len(document_understanding.get("education_blocks") or []) - comparison_metrics["legacy_education_count"]
    )
    return comparison_metrics


def run_profile_cache_hooks(
    *,
    cv_text: str,
    profile: Dict[str, Any],
    canonical_skills: list[Dict[str, Any]] | None = None,
    unresolved: list[Dict[str, Any]] | None = None,
    removed: list[Dict[str, Any]] | None = None,
) -> CacheHookResult:
    profile_hash = compute_profile_hash(profile)
    cache_profile_text(profile_hash, cv_text)
    extracted_text_hash = hash_text(cv_text)
    document_understanding = profile.get("document_understanding")
    profile_snapshot = dict(profile)

    try:
        structured = structure_profile_text_v1(cv_text, debug=False)

        # ── Profile summary (existing) ──────────────────────────────────
        summary = build_profile_summary(structured, extra_skills=profile.get("skills"))
        store_profile_summary(profile_hash, summary.model_dump())
        if os.getenv("ELEVIA_DEBUG_PROFILE_SUMMARY", "").strip().lower() in {"1", "true", "yes", "on"}:
            logger.info(
                "PROFILE_SUMMARY_STORED profile_id=%s last_updated=%s",
                profile_hash,
                summary.last_updated,
            )

        # ── CareerProfile extraction (additive — document generation only) ──
        # Builds rich experience data (bullets, tools, achievements) from the
        # already-computed ProfileStructuredV1. Stored as two keys:
        #   profile["career_profile"]  — full CareerProfile dict (for CV generator)
        #   profile["experiences"]     — enriched experience dicts (compatible with
        #                                apply_pack_cv_engine._normalize_experience)
        # NEVER touches: skills_uri, skills, languages, education_level (matching core)
        # raw_languages: prefer profile["languages"] (set by ESCO pipeline),
        # fall back to languages extracted directly from CV text by the structurer.
        raw_languages = profile.get("languages") or structured.extracted_languages or []
        career_profile = from_profile_structured_v1(
            structured,
            raw_skills=profile.get("skills") or [],
            raw_languages=raw_languages,
        )
        career_profile_dict = career_profile.model_dump()
        profile["career_profile"] = career_profile_dict
        profile["experiences"] = to_experience_dicts(career_profile)
        canonical_skill_inputs = _explicit_or_profile_list(
            canonical_skills,
            profile,
            "canonical_skills",
        )
        unresolved_inputs = _explicit_or_profile_list(
            unresolved,
            profile,
            "unresolved",
        )
        removed_inputs = _explicit_or_profile_list(
            removed,
            profile,
            "generic_filter_removed",
            "removed",
        )
        agent = ProfileStructuringAgent()
        agent_result = agent.run(
            {
                "career_profile": career_profile_dict,
                "raw_profile": dict(profile),
                "canonical_skills": canonical_skill_inputs,
                "unresolved": unresolved_inputs,
                "removed": removed_inputs,
            }
        )
        career_profile_dict = agent_result.get("career_profile_enriched") or career_profile_dict
        structuring_report = agent_result.get("structuring_report") or {}

        enrichment_agent = ProfileEnrichmentAgent()
        enrichment_result = enrichment_agent.run(
            {
                "career_profile": career_profile_dict,
                "structuring_report": structuring_report,
                "canonical_skills": canonical_skill_inputs,
                "unresolved": unresolved_inputs,
                "rejected_noise": removed_inputs,
            }
        )
        career_profile_dict = enrichment_result.get("career_profile_enriched") or career_profile_dict
        profile["career_profile"] = career_profile_dict
        profile["structuring_report"] = structuring_report
        enrichment_report = dict(enrichment_result.get("enrichment_report") or {})
        enrichment_report.setdefault("auto_filled", [])
        enrichment_report.setdefault("suggestions", [])
        enrichment_report.setdefault("questions", [])
        enrichment_report.setdefault("reused_rejected", [])
        enrichment_report.setdefault("confidence_scores", [])
        enrichment_report.setdefault("priority_signals", [])
        enrichment_report.setdefault("canonical_candidates", [])
        enrichment_report.setdefault("learning_candidates", [])
        enrichment_report.setdefault("stats", {})
        profile["enrichment_report"] = enrichment_report

        comparison_metrics = _augment_document_understanding_comparison_metrics(
            profile_snapshot=profile_snapshot,
            document_understanding=profile.get("document_understanding"),
        )

        enriched_career_profile = load_career_profile(career_profile_dict)
        profile["experiences"] = to_experience_dicts(enriched_career_profile)
        structuring_stats = structuring_report.get("stats", {})
        enrichment_stats = profile["enrichment_report"].get("stats", {})
        linked_tools = sum(
            len(link.get("tools") or [])
            for exp in career_profile_dict.get("experiences", [])
            for link in exp.get("skill_links", [])
        )
        raw_tools = sum(len(exp.get("tools") or []) for exp in career_profile_dict.get("experiences", []))

        logger.info(
            "[parse-file] career_profile extracted exps=%d completeness=%.2f",
            len(enriched_career_profile.experiences),
            enriched_career_profile.completeness,
        )
        logger.info(
            "STRUCTURING_STATS exps=%d skill_links=%d questions=%d coverage_ratio=%.4f tools_attached=%d tools_unattached=%d",
            int(structuring_stats.get("experiences_processed", 0) or 0),
            int(structuring_stats.get("skill_links_created", 0) or 0),
            int(structuring_stats.get("questions_generated", 0) or 0),
            float(structuring_stats.get("coverage_ratio", 0.0) or 0.0),
            linked_tools,
            max(0, raw_tools - linked_tools),
        )
        logger.info(
            "ENRICHMENT_STATS auto_filled=%d suggestions=%d questions=%d priority_signals=%d",
            int(enrichment_stats.get("auto_filled_count", 0) or 0),
            int(enrichment_stats.get("suggestions_count", 0) or 0),
            int(enrichment_stats.get("questions_count", 0) or 0),
            len(profile["enrichment_report"].get("priority_signals", [])),
        )
        if comparison_metrics:
            logger.info(
                json.dumps(
                    {
                        "event": "DOCUMENT_UNDERSTANDING_COMPARISON_METRICS",
                        "profile_hash": profile_hash,
                        "extracted_text_hash": extracted_text_hash,
                        "comparison_metrics": {
                            "identity_detected_legacy": comparison_metrics.get("identity_detected_legacy"),
                            "identity_detected_understanding": comparison_metrics.get("identity_detected_understanding"),
                            "experience_count_legacy": comparison_metrics.get("experience_count_legacy"),
                            "experience_count_understanding": comparison_metrics.get("experience_count_understanding"),
                            "project_count_understanding": comparison_metrics.get("project_count_understanding"),
                            "suspicious_merges_count": comparison_metrics.get("suspicious_merges_count"),
                            "orphan_lines_count": comparison_metrics.get("orphan_lines_count"),
                            "invalid_experience_headers_count": comparison_metrics.get("invalid_experience_headers_count"),
                        },
                    }
                )
            )

    except Exception as exc:
        logger.warning("[parse-file] profile hooks failed: %s", type(exc).__name__)
    finally:
        if document_understanding is not None:
            profile["document_understanding"] = document_understanding

    return CacheHookResult(
        profile_hash=profile_hash,
        extracted_text_hash=extracted_text_hash,
    )
