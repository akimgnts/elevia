from __future__ import annotations

import logging
import os
from typing import Any, Dict

from api.utils.profile_summary_builder import build_profile_summary
from api.utils.profile_summary_store import store_profile_summary
from compass.profile_structurer import structure_profile_text_v1
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

    return CacheHookResult(
        profile_hash=profile_hash,
        extracted_text_hash=extracted_text_hash,
    )
