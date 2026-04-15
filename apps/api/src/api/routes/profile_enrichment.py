"""
profile_enrichment.py — lightweight profile enrichment helpers.

Read-only support endpoints for the Profile page:
  - GET /profile/skills/suggest

Constraints:
  - deterministic only
  - no writes
  - never modifies skills_uri
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from fastapi import APIRouter, Query
from pydantic import BaseModel

from esco.loader import get_esco_store
from esco.mapper import map_skill
from esco.normalize import canon
from profile.esco_aliases import alias_key, load_alias_map

router = APIRouter(prefix="/profile", tags=["profile"])


class SkillSuggestionItem(BaseModel):
    label: str
    uri: str | None = None
    confidence: float = 0.0
    method: str
    source: str = "esco"


class SkillSuggestionResponse(BaseModel):
    query: str
    suggestions: List[SkillSuggestionItem]


def _score_contains_match(query_key: str, candidate_key: str) -> float:
    if candidate_key == query_key:
        return 0.99
    if candidate_key.startswith(query_key):
        return 0.94
    if f" {query_key}" in candidate_key or f"{query_key} " in candidate_key:
        return 0.89
    return 0.84


def _add_candidate(
    bucket: Dict[str, Tuple[float, SkillSuggestionItem]],
    *,
    uri: str,
    label: str,
    confidence: float,
    method: str,
) -> None:
    current = bucket.get(uri)
    item = SkillSuggestionItem(
        label=label,
        uri=uri,
        confidence=round(confidence, 3),
        method=method,
    )
    if current is None or confidence > current[0]:
        bucket[uri] = (confidence, item)


@router.get("/skills/suggest", response_model=SkillSuggestionResponse)
async def suggest_profile_skills(
    q: str = Query(..., min_length=2, max_length=80),
    limit: int = Query(8, ge=1, le=20),
) -> SkillSuggestionResponse:
    query = q.strip()
    if len(query) < 2:
        return SkillSuggestionResponse(query=query, suggestions=[])

    query_key = alias_key(query)
    store = get_esco_store()
    alias_map = load_alias_map()
    candidates: Dict[str, Tuple[float, SkillSuggestionItem]] = {}

    direct = map_skill(query, store=store, enable_fuzzy=True, fuzzy_threshold=0.84)
    if direct and direct.get("esco_id"):
        _add_candidate(
            candidates,
            uri=str(direct["esco_id"]),
            label=str(direct.get("label") or query),
            confidence=float(direct.get("confidence") or 0.9),
            method=str(direct.get("method") or "direct"),
        )

    for key, entry in alias_map.items():
        if query_key not in key:
            continue
        _add_candidate(
            candidates,
            uri=str(entry["uri"]),
            label=str(entry["label"]),
            confidence=_score_contains_match(query_key, key),
            method="alias_contains",
        )

    for preferred_key, uri in store.preferred_to_uri.items():
        if query_key not in preferred_key:
            continue
        _add_candidate(
            candidates,
            uri=str(uri),
            label=str(store.uri_to_preferred.get(uri, preferred_key)),
            confidence=_score_contains_match(query_key, preferred_key),
            method="preferred_contains",
        )

    words = [part for part in canon(query).split(" ") if len(part) >= 3]
    if words:
        for preferred_key, uri in store.preferred_to_uri.items():
            if not all(word in preferred_key for word in words):
                continue
            _add_candidate(
                candidates,
                uri=str(uri),
                label=str(store.uri_to_preferred.get(uri, preferred_key)),
                confidence=0.82,
                method="preferred_word_overlap",
            )

    ordered = sorted(
        (item for _, item in candidates.values()),
        key=lambda item: (-item.confidence, len(item.label), item.label.lower()),
    )[:limit]

    return SkillSuggestionResponse(query=query, suggestions=ordered)
