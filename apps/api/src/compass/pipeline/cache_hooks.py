from __future__ import annotations

import logging
import os
from typing import Any, Dict

from api.utils.profile_summary_builder import build_profile_summary
from api.utils.profile_summary_store import store_profile_summary
from compass.profile_structurer import structure_profile_text_v1
from documents.career_profile import from_profile_structured_v1, to_experience_dicts
from semantic.profile_cache import cache_profile_text, compute_profile_hash
from semantic.text_utils import hash_text

from .contracts import CacheHookResult

logger = logging.getLogger(__name__)


def run_profile_cache_hooks(*, cv_text: str, profile: Dict[str, Any]) -> CacheHookResult:
    profile_hash = compute_profile_hash(profile)
    cache_profile_text(profile_hash, cv_text)
    extracted_text_hash = hash_text(cv_text)

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
        career_profile = from_profile_structured_v1(
            structured,
            raw_skills=profile.get("skills") or [],
            raw_languages=profile.get("languages") or [],
        )
        profile["career_profile"] = career_profile.model_dump()
        # Enrich experiences so the CV engine gets bullets/achievements/tools
        if career_profile.experiences:
            profile["experiences"] = to_experience_dicts(career_profile)

        logger.info(
            "[parse-file] career_profile extracted exps=%d completeness=%.2f",
            len(career_profile.experiences),
            career_profile.completeness,
        )

    except Exception as exc:
        logger.warning("[parse-file] profile hooks failed: %s", type(exc).__name__)

    return CacheHookResult(
        profile_hash=profile_hash,
        extracted_text_hash=extracted_text_hash,
    )
