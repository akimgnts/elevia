"""
structured_cv_pipeline.py — Integration layer for structured CV extraction.

Combines extractor + validator with fallback chain.
NOT YET wired into /parse-file (test & validate first).
"""
from __future__ import annotations

import logging
from typing import Optional

from .structured_cv_extractor import extract_structured_cv
from .structured_cv_schemas import StructuredCV
from .structured_cv_validator import validate_structured_cv

logger = logging.getLogger(__name__)


def extract_and_validate_cv(cv_text: str) -> tuple[Optional[StructuredCV], bool, list[str]]:
    """
    Extract and validate CV structure.

    Returns:
        (structured_cv, is_valid, warnings)
        structured_cv=None if AI disabled or extraction failed (use fallback parser).
        is_valid=False means critical contamination (should reject AI output).
    """
    # Attempt AI extraction
    cv = extract_structured_cv(cv_text)
    if cv is None:
        # AI disabled or failed — caller should use fallback parser
        return None, True, ["Structured extraction not available"]

    # Validate structure
    is_valid, warnings = validate_structured_cv(cv)

    if not is_valid:
        logger.warning(
            "[structured-cv-pipeline] Validation failed: %s — using fallback parser",
            "; ".join(warnings),
        )
        return None, False, warnings

    logger.info("[structured-cv-pipeline] Extraction & validation OK")
    return cv, True, warnings
