"""
baseline_parser.py — Shared deterministic baseline CV parsing logic.

Shared by:
  - POST /profile/parse-baseline  (JSON text input)
  - POST /profile/parse-file      (multipart file upload)

No LLM. No external calls. Deterministic: same input → same output.
"""
from __future__ import annotations

import importlib
import logging
import sys
import re
from pathlib import Path
from typing import Dict, List

# Ensure src/ on path for esco imports
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from ..esco.extract import extract_raw_skills_from_profile
    from ..esco.mapper import map_skill
    from ..esco.uri_collapse import collapse_to_uris
except ImportError:
    _esco_extract = importlib.import_module("esco.extract")
    _esco_mapper = importlib.import_module("esco.mapper")
    _esco_collapse = importlib.import_module("esco.uri_collapse")
    extract_raw_skills_from_profile = _esco_extract.extract_raw_skills_from_profile
    map_skill = _esco_mapper.map_skill
    collapse_to_uris = _esco_collapse.collapse_to_uris
from profile.esco_grouping import group_validated_items
from profile.skill_filter import strict_filter_skills

logger = logging.getLogger(__name__)

MAX_CV_CHARS = 50_000  # cap to avoid pathological inputs
MAX_DEBUG_TOKENS = 200
MAX_DEBUG_DUPES = 20

_WS_RE = re.compile(r"\s+")


def _normalize_token(token: str) -> str:
    return _WS_RE.sub(" ", token.strip().lower())


def _cap_tokens(tokens: List[str], cap: int = MAX_DEBUG_TOKENS) -> List[str]:
    return tokens[:cap]


def _dedupe_preserve_order(tokens: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        result.append(token)
    return result


def _clean_extra_tokens(extra_tokens: List[str]) -> List[str]:
    cleaned: List[str] = []
    for token in extra_tokens:
        if not isinstance(token, str):
            continue
        norm = _normalize_token(token)
        if norm:
            cleaned.append(norm)
    return _dedupe_preserve_order(cleaned)


def run_baseline_from_tokens(
    raw_tokens: List[str],
    *,
    profile_id: str = "baseline-profile",
    source: str = "baseline",
) -> Dict:
    """
    Run deterministic baseline parsing from pre-extracted raw tokens.
    """
    filter_result = strict_filter_skills(raw_tokens)
    skills_canonical: List[str] = filter_result["skills"]
    validated_items = filter_result["validated_items"]
    skills_uri = [item.get("uri") for item in validated_items if item.get("uri")]
    skills_uri_count = len(skills_uri)
    skills_unmapped_count = len(filter_result.get("filtered_tokens", []))

    skills_uri_collapsed_dupes = 0
    dupes_by_uri: List[Dict[str, object]] = []
    if map_skill and collapse_to_uris:
        mapped_items: List[Dict[str, str]] = []
        for token in raw_tokens:
            result = map_skill(token, enable_fuzzy=False)
            if not result:
                continue
            mapped_items.append({
                "surface": token,
                "esco_uri": result.get("esco_id", ""),
                "esco_label": result.get("label") or result.get("canonical") or token,
                "source": "baseline",
            })
        collapsed = collapse_to_uris(mapped_items)
        skills_uri_collapsed_dupes = int(collapsed.get("collapsed_dupes", 0) or 0)
        display = collapsed.get("display") or []
        label_map = {
            item.get("uri"): item.get("label")
            for item in display
            if isinstance(item, dict) and item.get("uri")
        }
        for uri, surfaces in (collapsed.get("dupes") or {}).items():
            if not surfaces:
                continue
            dupes_by_uri.append({
                "label": label_map.get(uri, uri),
                "surfaces": surfaces,
            })
        if len(dupes_by_uri) > MAX_DEBUG_DUPES:
            dupes_by_uri = dupes_by_uri[:MAX_DEBUG_DUPES]

    # Group validated skills by ESCO collection for display
    skill_groups = group_validated_items(validated_items)

    logger.debug(
        "[baseline_parser] profile_id=%s raw=%d validated=%d groups=%d",
        profile_id,
        filter_result["raw_detected"],
        filter_result["validated_skills"],
        len(skill_groups),
    )

    return {
        "source": source,
        "skills_raw": raw_tokens,
        "skills_canonical": skills_canonical,
        "canonical_count": len(skills_canonical),
        "raw_detected": filter_result["raw_detected"],
        "validated_skills": filter_result["validated_skills"],
        "filtered_out": filter_result["filtered_out"],
        "validated_items": validated_items,
        "validated_labels": _cap_tokens([item["label"] for item in validated_items]),
        "raw_tokens": _cap_tokens(raw_tokens),
        "filtered_tokens": _cap_tokens(filter_result.get("filtered_tokens", [])),
        "alias_hits_count": filter_result.get("alias_hits_count", 0),
        "alias_hits": filter_result.get("alias_hits", []),
        "skill_groups": skill_groups,
        "skills_uri_count": skills_uri_count,
        "skills_uri_collapsed_dupes": skills_uri_collapsed_dupes,
        "skills_unmapped_count": skills_unmapped_count,
        "skills_dupes": dupes_by_uri,
        "profile": {
            "id": profile_id,
            "skills": skills_canonical,
            "skills_source": "baseline",
            "skills_uri": skills_uri,
        },
        "warnings": [],
    }


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
    return run_baseline_from_tokens(skills_raw, profile_id=profile_id, source="baseline")


def run_baseline_with_extra_tokens(
    cv_text: str,
    extra_tokens: List[str],
    *,
    profile_id: str = "baseline-profile",
    source: str = "llm",
) -> Dict:
    """
    Baseline parsing with extra tokens (e.g., LLM suggestions).
    """
    base_tokens = extract_raw_skills_from_profile({"cv_text": cv_text[:MAX_CV_CHARS]})
    extra_clean = _clean_extra_tokens(extra_tokens)
    combined = _dedupe_preserve_order(base_tokens + extra_clean)
    return run_baseline_from_tokens(combined, profile_id=profile_id, source=source)
