"""
skill_filter.py — Strict ESCO-based skill filtering layer.

Pipeline (applied after raw extraction):
  1. Normalize: lowercase, strip, deduplicate
  2. Basic noise removal: tokens with '@', digits, length < 3, stopwords
  3. ESCO strict filter: keep only tokens that map to ESCO (no fuzzy)
  4. Deduplicate by ESCO URI (keep preferred label)
  5. Truncate to MAX_VALIDATED

No scoring logic here. No LLM. Deterministic.
"""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from esco.extract import STOPWORDS
from esco.mapper import map_skill

logger = logging.getLogger(__name__)

MAX_VALIDATED = 40

_DIGIT_RE = re.compile(r"\d")


def _has_noise(token: str) -> bool:
    """Return True if token should be removed by basic noise rules."""
    if "@" in token:
        return True
    if _DIGIT_RE.search(token):
        return True
    if len(token) < 3:
        return True
    if token in STOPWORDS:
        return True
    return False


def strict_filter_skills(raw_skills: List[str]) -> Dict:
    """
    Apply ESCO strict filter to a list of raw skill tokens.

    Args:
        raw_skills: List of raw skill strings (from extract_raw_skills_from_profile).

    Returns:
        {
            "raw_detected": int,       # count before filtering
            "validated_skills": int,   # count after ESCO filter
            "filtered_out": int,       # raw_detected - validated_skills
            "skills": List[str],       # final skill labels (ESCO preferred, max 40)
        }
    """
    raw_detected = len(raw_skills)

    # Step 1 — normalize + deduplicate
    seen_normalized: set[str] = set()
    deduped: List[str] = []
    for s in raw_skills:
        norm = s.strip().lower()
        if norm and norm not in seen_normalized:
            seen_normalized.add(norm)
            deduped.append(s.strip())

    # Step 2 — basic noise removal
    after_noise = [t for t in deduped if not _has_noise(t.lower())]

    # Step 3 — ESCO strict filter (enable_fuzzy=False)
    seen_uris: set[str] = set()
    validated: List[str] = []
    for token in after_noise:
        result = map_skill(token, enable_fuzzy=False)
        if result is None:
            continue
        uri = result.get("esco_id") or result.get("canonical")
        if uri in seen_uris:
            continue  # deduplicate by ESCO URI
        seen_uris.add(uri)
        # Use preferred label from ESCO
        label = result.get("label") or result.get("canonical") or token
        validated.append(label)

    # Step 4 — truncate
    final = validated[:MAX_VALIDATED]

    validated_count = len(final)
    filtered_out = raw_detected - validated_count

    logger.debug(
        "[skill_filter] raw=%d noise_removed=%d esco_validated=%d truncated_to=%d",
        raw_detected,
        raw_detected - len(after_noise),
        len(validated),
        validated_count,
    )

    return {
        "raw_detected": raw_detected,
        "validated_skills": validated_count,
        "filtered_out": filtered_out,
        "skills": final,
    }
