"""
skill_phrase_reducer.py — Deterministic reducer for multi-skill phrases.

Goal: extract atomic, canonicalizable candidates from long phrases
without deleting the original phrases.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, List, Tuple

from compass.canonical.canonical_store import get_canonical_store, normalize_canonical_key


_CONNECTORS = {
    "and", "or", "&",
    "for", "using", "used", "use",
    "driven", "based",
    "with", "from", "to",
    "pipeline", "pipelines",
    "model", "models",
    "of", "in", "on",
    "de", "des", "du", "pour", "par", "sur", "avec",
}

_TECH_MARKERS_MULTI = [
    "power bi",
    "machine learning",
    "business intelligence",
    "data analysis",
    "data visualization",
    "data engineering",
    "api rest",
]

_TECH_MARKERS_SINGLE = [
    "sql", "python", "api", "rest", "bi", "ml", "ai",
    "etl", "dashboard", "dashboards", "tableau",
    "kpi", "dax", "power query",
]


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def _normalize_phrase(text: str) -> str:
    text = _strip_accents(text or "")
    text = text.lower()
    text = re.sub(r"[-/|,:;()]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _split_on_connectors(words: List[str]) -> List[str]:
    chunks: List[List[str]] = []
    current: List[str] = []
    for w in words:
        if w in _CONNECTORS:
            if current:
                chunks.append(current)
                current = []
            continue
        current.append(w)
    if current:
        chunks.append(current)
    return [" ".join(chunk).strip() for chunk in chunks if chunk]


def _has_canonical_hit(candidate: str) -> bool:
    store = get_canonical_store()
    if not store.is_loaded():
        return False
    key = normalize_canonical_key(candidate)
    if not key:
        return False
    return key in store.alias_to_id or key in store.tool_to_ids


@dataclass
class PhraseReducerTrace:
    source: str
    generated: List[str] = field(default_factory=list)
    kept: List[str] = field(default_factory=list)
    dropped: List[str] = field(default_factory=list)


def reduce_phrase_to_skill_candidates(token: str, max_candidates: int = 3) -> Tuple[List[str], PhraseReducerTrace]:
    """
    Reduce a phrase into atomic candidates that are likely canonical hits.
    Returns (kept_candidates, trace).
    """
    trace = PhraseReducerTrace(source=token)
    norm = _normalize_phrase(token)
    if not norm:
        return [], trace

    words = norm.split()
    if len(words) < 2:
        return [], trace

    candidates: List[str] = []

    # 1) Detect multi-word technical markers
    for marker in _TECH_MARKERS_MULTI:
        if marker in norm:
            candidates.append(marker)

    # 2) Detect single-word technical markers
    for marker in _TECH_MARKERS_SINGLE:
        if marker in words and marker not in candidates:
            candidates.append(marker)

    # 3) Connector-based splitting
    for chunk in _split_on_connectors(words):
        if 1 <= len(chunk.split()) <= 3 and chunk not in candidates:
            candidates.append(chunk)

    # 4) Specific deterministic reduction rules
    if "ingestion" in words and ("pipeline" in words or "pipelines" in words):
        candidates.append("data pipeline")

    trace.generated = candidates[:]

    # Filter: keep only canonical hits
    kept: List[str] = []
    for cand in candidates:
        if _has_canonical_hit(cand):
            kept.append(cand)
        else:
            trace.dropped.append(cand)

    # Deduplicate & cap
    seen = set()
    for cand in kept:
        key = normalize_canonical_key(cand)
        if key in seen:
            continue
        seen.add(key)
        trace.kept.append(cand)
        if len(trace.kept) >= max_candidates:
            break

    return trace.kept, trace


def reduce_phrases(
    phrases: Iterable[str],
    *,
    max_candidates_per_phrase: int = 3,
) -> Tuple[List[str], List[PhraseReducerTrace]]:
    """
    Reduce a list of phrases and return (added_candidates, traces).
    """
    added: List[str] = []
    traces: List[PhraseReducerTrace] = []
    for phrase in phrases:
        if not isinstance(phrase, str):
            continue
        # Only reduce multi-token phrases (avoid short single tokens)
        if len(phrase.split()) < 3:
            continue
        kept, trace = reduce_phrase_to_skill_candidates(
            phrase, max_candidates=max_candidates_per_phrase
        )
        if trace.generated:
            traces.append(trace)
        for cand in kept:
            added.append(cand)
    return added, traces
