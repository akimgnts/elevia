"""
phrase_cleaner.py — Deterministic phrase splitting + chunk normalization.

Goal: clean tight_candidates before canonical mapping (no scoring impact).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple

from compass.canonical.canonical_store import normalize_canonical_key


# ── Split rules ─────────────────────────────────────────────────────────────

_SPLIT_RE = re.compile(r"[|/;:,()\[\]{}]+")
_MULTI_SPACE_RE = re.compile(r"\s{2,}")


# ── Allowlists ──────────────────────────────────────────────────────────────

_PHRASE_ALLOWLIST = [
    "power bi",
    "machine learning",
    "data analysis",
    "data visualization",
    "business intelligence",
    "api rest",
    "rest api",
    "data engineering",
    "data science",
]

_TOKEN_ALLOWLIST = {
    "sql", "python", "api", "rest", "etl", "bi", "ml", "r",
    "kpi", "dashboard", "dashboards", "reporting", "powerbi",
}

_SHORT_KEEP = {"bi", "ml", "ai", "r", "sql", "api", "etl", "kpi", "ux", "ui"}


# ── Lemmatization ───────────────────────────────────────────────────────────

_LEMMA_MAP = {
    "apis": "api",
    "dashboards": "dashboard",
    "analyses": "analyse",
    "donnees": "donnee",
}

_LEMMA_EXCEPTIONS = {"business", "analysis", "analytics"}


# ── POS-guided heuristic (light, deterministic) ─────────────────────────────

_VERB_PREFIXES = {
    "produire", "realiser", "ameliorer", "optimiser", "mettre", "mettre en",
    "assurer", "coordonner", "piloter", "participer", "orienter",
}
_CONNECTORS = {"pour", "des", "du", "de", "et", "avec", "sans", "afin", "par"}


@dataclass
class CleanResult:
    split_chunks: List[str]
    cleaned_chunks: List[str]
    lemmatized_count: int
    pos_rejected_count: int


def split_phrases(candidates: Iterable[str]) -> List[str]:
    """Split noisy phrases on separators and repeated spaces."""
    out: List[str] = []
    seen = set()
    for cand in candidates or []:
        if not isinstance(cand, str):
            continue
        raw = cand.strip()
        if not raw:
            continue
        parts = _SPLIT_RE.split(raw)
        for part in parts:
            for sub in _MULTI_SPACE_RE.split(part):
                chunk = sub.strip()
                if not chunk:
                    continue
                key = chunk.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(chunk)
    return out


def lemmatize_token(token: str) -> str:
    """Very light lemmatization (deterministic)."""
    if token in _LEMMA_MAP:
        return _LEMMA_MAP[token]
    if token in _LEMMA_EXCEPTIONS:
        return token
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _repair_split_words(tokens: List[str]) -> List[str]:
    repaired: List[str] = []
    for tok in tokens:
        if repaired and len(tok) <= 2 and repaired[-1] not in _SHORT_KEEP and tok not in _SHORT_KEEP:
            repaired[-1] = f"{repaired[-1]}{tok}"
        else:
            repaired.append(tok)
    return repaired


def _pos_reject(chunk: str) -> bool:
    words = chunk.split()
    if not words:
        return True
    if len(words) >= 3 and any(w in _CONNECTORS for w in words):
        ratio = sum(1 for w in words if w in _CONNECTORS) / len(words)
        if ratio >= 0.34:
            return True
    first = " ".join(words[:2])
    if words[0] in _VERB_PREFIXES or first in _VERB_PREFIXES:
        return True
    return False


def pos_guided_reject(chunk: str) -> bool:
    """Public wrapper for tests."""
    return _pos_reject(chunk)


def clean_chunks(
    chunks: Iterable[str],
    *,
    enable_lemmatization: bool = True,
    enable_pos_filter: bool = True,
) -> CleanResult:
    """
    Normalize + split composite chunks into cleaner skill candidates.
    Returns CleanResult with stats for DevPanel.
    """
    split_chunks = list(chunks or [])
    cleaned: List[str] = []
    seen = set()
    lemmatized = 0
    pos_rejected = 0

    for chunk in split_chunks:
        if not isinstance(chunk, str):
            continue
        norm = normalize_canonical_key(chunk)
        if not norm:
            continue

        words = _repair_split_words(norm.split())
        if enable_lemmatization:
            lemmatized_tokens: List[str] = []
            for w in words:
                lw = lemmatize_token(w)
                if lw != w:
                    lemmatized += 1
                lemmatized_tokens.append(lw)
            norm = " ".join(lemmatized_tokens).strip()
        else:
            norm = " ".join(words).strip()
        if not norm:
            continue

        # Extract known phrases if present
        extracted: List[str] = []
        for phrase in _PHRASE_ALLOWLIST:
            if phrase in norm:
                extracted.append(phrase)
        # Extract known tokens
        for w in norm.split():
            if w in _TOKEN_ALLOWLIST:
                extracted.append(w)

        if extracted:
            for item in extracted:
                if item not in seen:
                    seen.add(item)
                    cleaned.append(item)
            continue

        # POS-guided reject (narrative chunks)
        if enable_pos_filter and _pos_reject(norm):
            pos_rejected += 1
            continue

        # Reduce long chunks
        words = norm.split()
        if len(words) > 6:
            norm = " ".join(words[:6])

        if len(norm) < 2:
            continue

        if norm not in seen:
            seen.add(norm)
            cleaned.append(norm)

    return CleanResult(
        split_chunks=split_chunks,
        cleaned_chunks=cleaned,
        lemmatized_count=lemmatized,
        pos_rejected_count=pos_rejected,
    )
