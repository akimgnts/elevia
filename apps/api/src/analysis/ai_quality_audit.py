"""
analysis/ai_quality_audit.py — Cluster-aware AI recovery quality audit.

This module computes metrics on recovered AI skills without touching matching.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set


def _norm(label: str) -> str:
    return str(label or "").strip().lower()


def _extract_labels(items: Iterable[Any]) -> List[str]:
    labels: List[str] = []
    for item in items or []:
        if isinstance(item, str):
            if item.strip():
                labels.append(item.strip())
        elif isinstance(item, dict):
            label = item.get("label") or item.get("name") or ""
            if isinstance(label, str) and label.strip():
                labels.append(label.strip())
    return labels


def _offer_skills_union(offers: Iterable[Dict[str, Any]]) -> Set[str]:
    union: Set[str] = set()
    for offer in offers or []:
        skills = offer.get("skills_display") or offer.get("skills") or []
        if isinstance(skills, list):
            for s in skills:
                if isinstance(s, str) and s.strip():
                    union.add(_norm(s))
    return union


def audit_ai_quality(
    profile: Dict[str, Any],
    offers: List[Dict[str, Any]],
    recovered_skills: List[Any],
) -> Dict[str, Any]:
    """
    Compute AI recovery quality metrics.

    Returns:
      {
        "validated_esco_count": int,
        "ai_recovered_count": int,
        "ai_overlap_with_offers": int,
        "ai_unique_vs_esco": int,
        "cluster_coherence_score": float,
        "noise_ratio_estimate": float
      }
    """
    validated_esco = (
        profile.get("validated_esco_labels")
        or profile.get("skills_validated_esco")
        or profile.get("validated_labels")
        or []
    )
    validated_set = {_norm(s) for s in validated_esco if isinstance(s, str) and s.strip()}

    recovered_labels = _extract_labels(recovered_skills)
    recovered_set = {_norm(s) for s in recovered_labels if s.strip()}

    offer_skill_set = _offer_skills_union(offers)

    recovered_count = len(recovered_set)
    overlap_count = sum(1 for s in recovered_set if s in offer_skill_set)
    unique_vs_esco = sum(1 for s in recovered_set if s not in validated_set)

    if recovered_count == 0:
        coherence = 0.0
        noise_ratio = 0.0
    else:
        coherence = overlap_count / recovered_count
        noise_ratio = (recovered_count - overlap_count) / recovered_count

    return {
        "validated_esco_count": len(validated_set),
        "ai_recovered_count": recovered_count,
        "ai_overlap_with_offers": overlap_count,
        "ai_unique_vs_esco": unique_vs_esco,
        "cluster_coherence_score": round(coherence, 4),
        "noise_ratio_estimate": round(noise_ratio, 4),
    }
