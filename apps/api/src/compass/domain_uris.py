"""
compass/domain_uris.py — DOMAIN URI helpers for matching.

DOMAIN URI format:
  compass:skill:<cluster>:<token_normalized>

Deterministic, no side effects. No score_core access.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .cluster_library import ClusterLibraryStore, get_library, normalize_token, is_skill_candidate
from .cv_enricher import extract_candidate_tokens

DOMAIN_URI_PREFIX = "compass:skill"


def build_domain_uri(cluster: Optional[str], token: str) -> Optional[str]:
    """Return canonical DOMAIN URI or None when inputs are invalid."""
    if not cluster or not token:
        return None
    cluster_key = str(cluster).strip().upper()
    token_norm = normalize_token(token)
    if not cluster_key or not token_norm:
        return None
    return f"{DOMAIN_URI_PREFIX}:{cluster_key}:{token_norm}"


def build_domain_uris_for_text(
    text: str,
    esco_skills: List[str],
    cluster: Optional[str],
    *,
    extra_tokens: Optional[List[str]] = None,
    library: Optional[ClusterLibraryStore] = None,
) -> Tuple[List[str], List[str], dict]:
    """
    Build DOMAIN URIs from text using active cluster library tokens.

    Returns:
      (domain_tokens_norm, domain_uris)
    """
    if not text or not cluster:
        return [], [], {"candidates_count": 0, "rejected_count": 0, "rejected_tokens": []}

    lib = library or get_library()
    active_tokens = lib.get_active_skills(cluster)
    if not active_tokens:
        return [], [], {"candidates_count": 0, "rejected_count": 0, "rejected_tokens": []}

    active_set = set(active_tokens)
    candidates = extract_candidate_tokens(text, esco_skills or [])
    if extra_tokens:
        candidates.extend([t for t in extra_tokens if t])

    candidates_count = len(candidates)
    rejected: List[str] = []
    filtered_candidates: List[str] = []
    for token in candidates:
        if not is_skill_candidate(token, cluster):
            rejected.append(str(token))
            continue
        filtered_candidates.append(token)

    domain_tokens: List[str] = []
    seen = set()
    for token in filtered_candidates:
        norm = normalize_token(str(token))
        if not norm or norm in seen:
            continue
        seen.add(norm)
        if norm in active_set:
            domain_tokens.append(norm)

    domain_uris: List[str] = []
    for tok in domain_tokens:
        uri = build_domain_uri(cluster, tok)
        if uri:
            domain_uris.append(uri)

    debug = {
        "candidates_count": candidates_count,
        "rejected_count": len(rejected),
        "rejected_tokens": rejected[:50],
    }
    return domain_tokens, domain_uris, debug
