"""
structured_cv_integration.py — Inject structured CV extraction into parse pipeline.

Optional early stage that enhances career_profile with AI-extracted structure.
Fallback to legacy parser if disabled, fails, or validation fails.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from .structured_cv_adapter import structured_to_profile_v1
from .structured_cv_pipeline import extract_and_validate_cv
from .structured_cv_schemas import StructuredCV

logger = logging.getLogger(__name__)


def attempt_structured_cv_extraction(cv_text: str) -> tuple[Optional[StructuredCV], dict]:
    """
    Attempt AI-powered structured CV extraction.

    Returns:
        (structured_cv, metadata)
        where metadata tracks extraction source and quality
    """
    # Check flags at runtime (allows test env var changes)
    ai_enabled = os.getenv("ELEVIA_STRUCTURED_CV_AI", "").lower() in ("1", "true", "yes")
    mock_enabled = os.getenv("ELEVIA_STRUCTURED_CV_MOCK", "").lower() in ("1", "true", "yes")

    metadata = {
        "structured_cv_enabled": ai_enabled,
        "extraction_source": "legacy_parser",
        "structured_cv_success": False,
        "structured_cv_validation": None,
        "structured_cv_warnings": [],
        "fallback_reason": None,
    }

    if not ai_enabled:
        logger.debug("[structured-cv-integration] AI disabled, using legacy parser")
        metadata["fallback_reason"] = "feature_flag_off"
        return None, metadata

    # Try extraction
    cv, is_valid, warnings = extract_and_validate_cv(cv_text)

    if cv is None:
        if is_valid:
            # Not an error, just not available
            logger.debug("[structured-cv-integration] Structured extraction unavailable")
            metadata["fallback_reason"] = "extraction_unavailable"
        else:
            logger.warning(
                "[structured-cv-integration] Validation failed: %s",
                "; ".join(warnings),
            )
            metadata["fallback_reason"] = "validation_failed"
            metadata["structured_cv_warnings"] = warnings
        return None, metadata

    # Success
    logger.info(
        "[structured-cv-integration] Extraction OK: %d exp, %d proj, %d edu",
        len(cv.experiences),
        len(cv.projects),
        len(cv.education),
    )
    # Set extraction source (mock or AI)
    if mock_enabled:
        metadata["extraction_source"] = "structured_mock"
        logger.info("[structured-cv-integration] Using MOCK extraction")
    else:
        metadata["extraction_source"] = "structured_ai"

    metadata["structured_cv_success"] = True
    metadata["structured_cv_validation"] = is_valid
    metadata["structured_cv_warnings"] = warnings

    return cv, metadata


def enhance_profile_with_structured_cv(
    profile: dict,
    structured_cv: Optional[StructuredCV],
) -> dict:
    """
    Enhance existing profile with structured CV data.

    If structured_cv provided, merges its career_profile into existing profile.
    Otherwise returns profile unchanged.
    """
    if structured_cv is None:
        return profile

    try:
        profile_v1 = structured_to_profile_v1(structured_cv)

        # Merge into profile
        if not isinstance(profile, dict):
            profile = {}

        career_profile = profile.get("career_profile", {})
        if not isinstance(career_profile, dict):
            career_profile = {}

        # Update career_profile with structured data
        career_profile["experiences"] = [e.model_dump() for e in profile_v1.experiences]
        career_profile["projects"] = [p.model_dump() for p in profile_v1.projects]
        career_profile["education"] = [ed.model_dump() for ed in profile_v1.education]
        career_profile["certifications"] = [c.model_dump() for c in profile_v1.certifications]
        career_profile["extracted_tools"] = profile_v1.extracted_tools
        career_profile["extracted_companies"] = profile_v1.extracted_companies
        career_profile["extracted_titles"] = profile_v1.extracted_titles
        career_profile["extracted_languages"] = profile_v1.extracted_languages
        career_profile["cv_quality"] = profile_v1.cv_quality.model_dump()

        profile["career_profile"] = career_profile
        logger.info("[structured-cv-integration] Profile enhanced with structured data")

        return profile

    except Exception as e:
        logger.warning("[structured-cv-integration] Enhancement failed: %s", e)
        return profile
