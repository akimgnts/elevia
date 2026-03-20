"""
explanation_builder.py — Deterministic post-match explainability contract.

Pure transformation layer:
  - never changes score or ranking
  - never exposes canonical/debug internals
  - produces short, front-ready fields
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence


_DISPLAY_OVERRIDES = {
    "sql": "SQL",
    "sap": "SAP",
    "crm": "CRM",
    "erp": "ERP",
    "hr": "HR",
    "api": "API",
    "aws": "AWS",
    "gcp": "GCP",
    "seo": "SEO",
    "sem": "SEM",
    "ml": "ML",
    "bi": "BI",
    "power bi": "Power BI",
    "salesforce": "Salesforce",
    "looker studio": "Looker Studio",
}

_NOISY_LABELS = {
    "ability",
    "both",
    "contribute",
    "query",
}

_UPPERCASE_WORDS = {"sql", "sap", "crm", "erp", "hr", "api", "aws", "gcp", "seo", "sem", "ml", "bi", "ifrs"}


def _normalize_skill_values(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    out: List[str] = []
    for item in values:
        if isinstance(item, str):
            label = item
        elif isinstance(item, dict):
            label = item.get("label") or item.get("name") or ""
        else:
            label = ""
        cleaned = _clean_label(label)
        if cleaned:
            out.append(cleaned)
    return out


def _clean_label(raw: Any) -> Optional[str]:
    if not isinstance(raw, str):
        return None
    label = " ".join(raw.strip().split())
    if not label:
        return None

    lower = label.lower()
    if lower in _NOISY_LABELS:
        return None
    if lower.startswith("skill:") or "http://" in lower or "https://" in lower:
        return None
    if len(label.split()) > 8:
        return None
    if len(label) <= 1:
        return None

    if lower in _DISPLAY_OVERRIDES:
        return _DISPLAY_OVERRIDES[lower]
    if label.isupper():
        return label
    words = label.split()
    normalized_words = [
        word.upper() if word.lower() in _UPPERCASE_WORDS else word
        for word in words
    ]
    normalized = " ".join(normalized_words)
    if normalized.islower():
        return normalized[:1].upper() + normalized[1:]
    if normalized[:1].islower():
        return normalized[:1].upper() + normalized[1:]
    return normalized


def _merge_unique(*groups: Sequence[str], limit: int) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for group in groups:
        for label in group:
            key = label.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(label)
            if len(out) >= limit:
                return out
    return out


def _extract_groups(
    match_debug: Dict[str, Any],
    *,
    profile_effective_skills: Optional[Sequence[str]] = None,
    job_required_skills: Optional[Sequence[str]] = None,
) -> tuple[List[str], List[str], List[str], List[str], List[str], List[str]]:
    skills_debug = match_debug.get("skills", {}) if isinstance(match_debug, dict) else {}

    matched_core = _normalize_skill_values(skills_debug.get("matched_core"))
    missing_core = _normalize_skill_values(skills_debug.get("missing_core"))
    matched_secondary = _normalize_skill_values(skills_debug.get("matched_secondary"))
    missing_secondary = _normalize_skill_values(skills_debug.get("missing_secondary"))
    matched = _normalize_skill_values(skills_debug.get("matched"))
    missing = _normalize_skill_values(skills_debug.get("missing"))

    if matched_core or missing_core or matched_secondary or missing_secondary or matched or missing:
        return matched_core, missing_core, matched_secondary, missing_secondary, matched, missing

    profile_labels = _normalize_skill_values(list(profile_effective_skills or []))
    offer_labels = _normalize_skill_values(list(job_required_skills or []))
    profile_keys = {label.casefold() for label in profile_labels}
    matched_fallback = [label for label in offer_labels if label.casefold() in profile_keys]
    missing_fallback = [label for label in offer_labels if label.casefold() not in profile_keys]
    return [], [], [], [], matched_fallback, missing_fallback


def _fit_label(score: Optional[int], confidence: Optional[str]) -> str:
    numeric = score if isinstance(score, int) else None
    if numeric is not None:
        if numeric >= 75:
            return "Strong fit"
        if numeric >= 60:
            return "Good fit"
        if numeric >= 40:
            return "Partial fit"
        return "Low fit"
    conf = (confidence or "").strip().upper()
    if conf == "HIGH":
        return "Strong fit"
    if conf == "MED":
        return "Good fit"
    return "Low fit"


def _build_summary_reason(strengths: List[str], gaps: List[str], blockers: List[str]) -> str:
    top_strengths = strengths[:2]
    top_gap = (blockers or gaps)[:2]
    if top_strengths and top_gap:
        if len(top_strengths) >= 2:
            return f"Your profile matches this role through {top_strengths[0]} and {top_strengths[1]}, but it still lacks {top_gap[0]}."
        return f"Your profile matches this role through {top_strengths[0]}, but it still lacks {top_gap[0]}."
    if top_strengths:
        if len(top_strengths) >= 2:
            return f"Your profile aligns with this role through {top_strengths[0]} and {top_strengths[1]}."
        return f"Your profile aligns with this role through {top_strengths[0]}."
    if top_gap:
        if len(top_gap) >= 2:
            return f"This role is mainly limited by missing {top_gap[0]} and {top_gap[1]}."
        return f"This role is mainly limited by missing {top_gap[0]}."
    return "This match has limited explainable signal from the current profile."


def _build_next_actions(strengths: List[str], gaps: List[str], blockers: List[str]) -> List[str]:
    actions: List[str] = []
    target_gaps = blockers or gaps
    for label in target_gaps[:2]:
        actions.append(f"Add explicit evidence of {label} in your CV.")
    if strengths:
        actions.append(f"Highlight {strengths[0]} near the top of your CV.")
    if not actions:
        actions.append("Add clearer skill evidence to your profile before targeting this role.")
    return actions[:3]


def build_offer_explanation(
    match_debug: Dict[str, Any],
    *,
    score: Optional[int],
    confidence: Optional[str],
    profile_effective_skills: Optional[Sequence[str]] = None,
    job_required_skills: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    matched_core, missing_core, matched_secondary, missing_secondary, matched, missing = _extract_groups(
        match_debug,
        profile_effective_skills=profile_effective_skills,
        job_required_skills=job_required_skills,
    )

    strengths = _merge_unique(matched_core, matched_secondary, matched, limit=3)
    gaps = _merge_unique(missing_core, missing_secondary, missing, limit=3)

    blockers: List[str] = []
    if missing_core:
        blockers = _merge_unique(missing_core, limit=2)
    elif isinstance(score, int) and score < 60 and gaps:
        blockers = gaps[:2]

    fit_label = _fit_label(score, confidence)
    return {
        "score": score,
        "fit_label": fit_label,
        "summary_reason": _build_summary_reason(strengths, gaps, blockers),
        "strengths": strengths,
        "gaps": gaps,
        "blockers": blockers,
        "next_actions": _build_next_actions(strengths, gaps, blockers),
    }
