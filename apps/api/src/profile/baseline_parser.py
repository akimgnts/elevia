"""
baseline_parser.py — Shared deterministic baseline CV parsing logic.

Shared by:
  - POST /profile/parse-baseline  (JSON text input)
  - POST /profile/parse-file      (multipart file upload)

No LLM. No external calls. Deterministic: same input → same output.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, List

# Ensure src/ on path for esco imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from esco.extract import extract_raw_skills_from_profile
from profile.skill_filter import strict_filter_skills

logger = logging.getLogger(__name__)

MAX_CV_CHARS = 50_000  # cap to avoid pathological inputs


def run_baseline(cv_text: str, *, profile_id: str = "baseline-profile") -> Dict:
    """
    Run deterministic baseline parsing on raw CV text.

    Args:
        cv_text:    Raw text from CV (any encoding already resolved).
        profile_id: ID to embed in the returned profile dict.

    Returns:
        dict with keys:
          source, skills_raw, skills_canonical, canonical_count, profile,
          raw_detected, validated_skills, filtered_out

    The `profile` value is directly usable as POST /inbox `profile` field.
    """
    text = cv_text[:MAX_CV_CHARS]

    skills_raw: List[str] = extract_raw_skills_from_profile({"cv_text": text})

    # Apply strict ESCO filter: normalize → noise removal → ESCO lookup → truncate
    filter_result = strict_filter_skills(skills_raw)
    skills_canonical: List[str] = filter_result["skills"]

    logger.debug(
        "[baseline_parser] profile_id=%s raw=%d validated=%d",
        profile_id,
        filter_result["raw_detected"],
        filter_result["validated_skills"],
    )

    return {
        "source": "baseline",
        "skills_raw": skills_raw,
        "skills_canonical": skills_canonical,
        "canonical_count": len(skills_canonical),
        "raw_detected": filter_result["raw_detected"],
        "validated_skills": filter_result["validated_skills"],
        "filtered_out": filter_result["filtered_out"],
        "profile": {
            "id": profile_id,
            "skills": skills_canonical,
            "skills_source": "baseline",
        },
        "warnings": [],
    }
