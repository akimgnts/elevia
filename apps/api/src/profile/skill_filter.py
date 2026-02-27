"""
skill_filter.py — Strict ESCO-based skill filtering layer.

Pipeline (applied after raw extraction):
  1. Normalize: lowercase, strip, deduplicate
  2. Basic noise removal: tokens with '@', digits, length < 3, stopwords
  3. ESCO alias pre-pass: map tokens directly to verified ESCO URIs (no fuzzy)
  4. ESCO strict filter: keep only remaining tokens that map to ESCO (no fuzzy)
  5. Deduplicate by ESCO URI (keep preferred label)
  6. Truncate to MAX_VALIDATED

No scoring logic here. No LLM. Deterministic.
"""
from __future__ import annotations

import importlib
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from ..esco.extract import STOPWORDS
    from ..esco.mapper import map_skill
    from .esco_aliases import load_alias_map, alias_key
except ImportError:
    _esco_extract = importlib.import_module("esco.extract")
    _esco_mapper = importlib.import_module("esco.mapper")
    _esco_aliases = importlib.import_module("profile.esco_aliases")
    STOPWORDS = _esco_extract.STOPWORDS
    map_skill = _esco_mapper.map_skill
    load_alias_map = _esco_aliases.load_alias_map
    alias_key = _esco_aliases.alias_key

logger = logging.getLogger(__name__)

MAX_VALIDATED = 40
MAX_ALIAS_HITS_DEBUG = 50  # cap for debug list

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

    Pipeline:
      1. Normalize + deduplicate
      2. Basic noise removal
      3. Alias pre-pass: direct URI mapping for known FR CV vocabulary
      4. ESCO strict map_skill (no fuzzy) for remaining tokens
      5. Deduplicate by URI
      6. Truncate to MAX_VALIDATED

    Args:
        raw_skills: List of raw skill strings (from extract_raw_skills_from_profile).

    Returns:
        {
            "raw_detected": int,
            "validated_skills": int,
            "filtered_out": int,
            "skills": List[str],                       # ESCO preferred labels (max 40)
            "validated_items": List[Dict[str,str]],    # [{uri, label}, ...] (max 40)
            "filtered_tokens": List[str],              # tokens not matched by alias or ESCO
            "alias_hits_count": int,                   # how many were matched via alias layer
            "alias_hits": List[Dict[str,str]],         # [{alias, label}, ...] (max 50, debug)
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

    # Step 3 — alias pre-pass (deterministic, direct URI mapping)
    alias_map = load_alias_map()  # singleton, graceful fallback to {}
    seen_uris: set[str] = set()
    validated_items: List[Dict] = []
    filtered_tokens: List[str] = []
    alias_hits: List[Dict] = []
    remaining_for_esco: List[str] = []

    for token in after_noise:
        token_key = alias_key(token)
        alias_entry = alias_map.get(token_key)
        if alias_entry is not None:
            uri = str(alias_entry["uri"])
            label = str(alias_entry["label"])
            if uri not in seen_uris:
                seen_uris.add(uri)
                validated_items.append({"uri": uri, "label": label})
                if len(alias_hits) < MAX_ALIAS_HITS_DEBUG:
                    alias_hits.append({"alias": str(alias_entry.get("alias", token)), "label": label})
            # token handled by alias — do not send to map_skill
        else:
            remaining_for_esco.append(token)

    # Step 4 — ESCO strict filter for non-alias tokens (enable_fuzzy=False)
    for token in remaining_for_esco:
        result = map_skill(token, enable_fuzzy=False)
        if result is None:
            filtered_tokens.append(token)
            continue
        uri = result.get("esco_id") or result.get("canonical") or ""
        if uri in seen_uris:
            continue  # deduplicate by ESCO URI
        seen_uris.add(uri)
        label = result.get("label") or result.get("canonical") or token
        validated_items.append({"uri": uri, "label": label})

    # Step 5 — truncate
    final_items = validated_items[:MAX_VALIDATED]
    final_labels = [item["label"] for item in final_items]

    validated_count = len(final_items)
    alias_hits_count = len(alias_hits)
    filtered_out = raw_detected - validated_count

    logger.debug(
        "[skill_filter] raw=%d noise_removed=%d alias_hits=%d esco_validated=%d truncated_to=%d",
        raw_detected,
        raw_detected - len(after_noise),
        alias_hits_count,
        len(validated_items),
        validated_count,
    )

    return {
        "raw_detected": raw_detected,
        "validated_skills": validated_count,
        "filtered_out": filtered_out,
        "skills": final_labels,
        "validated_items": final_items,
        "filtered_tokens": filtered_tokens,
        "alias_hits_count": alias_hits_count,
        "alias_hits": alias_hits,
    }
