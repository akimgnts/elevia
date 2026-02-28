"""
offer_cluster.py - Deterministic offer macro-cluster detection.

Uses the same cluster taxonomy and keyword lists as profile_cluster.
No external calls. No randomness.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from profile.profile_cluster import CLUSTERS, TIE_BREAK, _KEYWORDS_NORM, _normalize


def _normalize_list(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        if not isinstance(value, str):
            continue
        norm = _normalize(value)
        if norm and norm not in seen:
            seen.add(norm)
            result.append(norm)
    return result


def detect_offer_cluster(
    title: str | None,
    description: str | None,
    skills: Iterable[str] | None,
) -> Tuple[str, float, Dict[str, int]]:
    """
    Detect macro-cluster from offer text + skills.

    Scoring:
      - keyword in text: +1
      - exact keyword match in skills: +2

    Returns:
      (dominant_cluster, confidence, score_map)
    """
    title = title or ""
    description = description or ""
    skills_list = _normalize_list(skills or [])

    combined_text = _normalize(" ".join([title, description, " ".join(skills_list)]))

    scores: Dict[str, int] = {c: 0 for c in CLUSTERS}

    for cluster in CLUSTERS:
        for kw in _KEYWORDS_NORM.get(cluster, []):
            if not kw:
                continue
            if kw in combined_text:
                scores[cluster] += 1

    for skill in skills_list:
        for cluster in CLUSTERS:
            for kw in _KEYWORDS_NORM.get(cluster, []):
                if skill == kw:
                    scores[cluster] += 2

    total = sum(scores.values())
    if total == 0:
        return "OTHER", 0.0, scores

    dominant = max(CLUSTERS, key=lambda c: (scores[c], -TIE_BREAK.index(c)))
    confidence = round(scores[dominant] / total, 2)
    return dominant, confidence, scores
