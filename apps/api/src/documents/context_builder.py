"""
context_builder.py — Deterministic matched/missing skill resolver.

Used by POST /documents/cv/for-offer to enrich CV ordering with inbox context.

Contract:
  - If InboxContext.matched_skills provided → use directly (trusted, already computed)
  - Else → compute from ATS keywords vs profile skills (deterministic fallback)
  - All outputs: sorted(normalized_str) — never set iteration
  - No LLM. No scoring core imports.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .ats_keywords import extract_ats_keywords, keywords_overlap


def build_matched_skills(
    offer: dict,
    profile: dict,
    matched_skills: Optional[List[str]] = None,
    missing_skills: Optional[List[str]] = None,
) -> Tuple[List[str], List[str]]:
    """
    Return (matched_core_skills, missing_core_skills) — deterministic sorted lists.

    Priority:
      1. If matched_skills is provided and non-empty → use as-is (inbox already computed)
      2. Else → extract ATS keywords from offer, compute overlap with profile skills

    Args:
        offer:          Offer dict (needs title + description for fallback computation)
        profile:        Profile dict (needs skills list)
        matched_skills: Pre-computed matched skills from inbox (optional)
        missing_skills: Pre-computed missing skills from inbox (optional)

    Returns:
        Tuple of (matched_core, missing_core) — each sorted ascending, lowercased.
    """
    # Path 1 — caller provides context (from inbox match result)
    if matched_skills:
        matched_norm = sorted({s.lower().strip() for s in matched_skills if s and s.strip()})
        missing_norm = sorted({s.lower().strip() for s in (missing_skills or []) if s and s.strip()})
        return matched_norm, missing_norm

    # Path 2 — compute from offer keywords vs profile skills (deterministic fallback)
    keywords = extract_ats_keywords(
        title=offer.get("title") or "",
        description=offer.get("description") or "",
    )
    profile_skills = [str(s) for s in profile.get("skills", []) if s]
    matched, missing = keywords_overlap(profile_skills, keywords)

    # Stable sort (already lowercased by keywords_overlap)
    return sorted(matched), sorted(missing)
