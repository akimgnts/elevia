from __future__ import annotations

import os
import re
from typing import List, Tuple

from compass.canonical.canonical_store import normalize_canonical_key

from .contracts import SkillCandidateStageResult

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[\w.-]+\b", re.IGNORECASE)
_URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.IGNORECASE)
_DOMAIN_RE = re.compile(r"\b[\w-]+(?:\.|\s)(com|fr|net|org|io|co|edu|gov)\b", re.IGNORECASE)
_LINKEDIN_RE = re.compile(r"\blinkedin\.com/\S+|\blinkedin\b", re.IGNORECASE)
_GITHUB_RE = re.compile(r"\bgithub\.com/\S+|\bgithub\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
_SHORT_PHONE_RE = re.compile(r"\b\d{2}\s?\d{2}\b")
_DATE_RE = re.compile(r"\b(19|20)\d{2}([-/\s](19|20)?\d{2})?\b")
_NUMERIC_ONLY_RE = re.compile(r"^\d+$")
_BROKEN_TOKEN_RE = re.compile(r"\b[a-z]\s[a-z]{2,}\b|\b[a-z]{2,}\s[a-z]\b", re.I)
_BROKEN_FRAGMENTS = (
    "donn es",
    "activit",
    "compr hension",
    "coh rence",
    "d veloppement",
    "fran ais",
    "d cision",
)
_MULTI_SKILL_MARKERS = {
    "sql", "python", "api", "rest", "power bi", "bi", "ml", "ai",
    "tableau", "dashboard", "dashboards", "etl", "machine learning",
}
_GENERIC_WORDS = {
    "and", "or", "with", "for", "using", "used", "use", "from", "to",
    "de", "des", "du", "pour", "par", "sur", "avec",
    "the", "a", "an", "of", "in", "on",
    "process", "processes", "system", "systems", "tool", "tools",
    "project", "projects", "management", "performance", "analysis",
    "decision", "support", "insights", "data",
}


def _flag_enabled(name: str) -> bool:
    raw = os.getenv(name, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def filter_noise_candidates(candidates: List[str]) -> Tuple[List[str], List[str]]:
    filtered: List[str] = []
    removed: List[str] = []
    seen_removed: set = set()

    for raw in candidates:
        if not isinstance(raw, str):
            continue
        token = raw.strip()
        if not token:
            continue

        reason = None
        token_compact = re.sub(r"\s+", " ", token)
        if _EMAIL_RE.search(token):
            reason = "email"
        elif _URL_RE.search(token):
            reason = "url"
        elif _DOMAIN_RE.search(token_compact):
            reason = "domain"
        elif _LINKEDIN_RE.search(token):
            reason = "linkedin"
        elif _GITHUB_RE.search(token):
            reason = "github"
        elif _PHONE_RE.search(token) or _SHORT_PHONE_RE.search(token):
            reason = "phone"
        elif _DATE_RE.search(token):
            reason = "date"
        elif _NUMERIC_ONLY_RE.match(token.replace(" ", "")):
            reason = "numeric"

        if reason:
            if token not in seen_removed:
                removed.append(token)
                seen_removed.add(token)
            continue

        filtered.append(token)

    return filtered, removed


def is_broken_token(token: str) -> bool:
    lower = token.lower()
    if any(frag in lower for frag in _BROKEN_FRAGMENTS):
        return True
    return bool(_BROKEN_TOKEN_RE.search(lower))


def is_multi_skill_phrase(token: str) -> bool:
    lower = token.lower()
    hits = 0
    for marker in _MULTI_SKILL_MARKERS:
        if marker in lower:
            hits += 1
        if hits >= 2:
            return True
    return False


def classify_unresolved(token: str, is_duplicate: bool) -> str:
    if is_duplicate:
        return "DUPLICATE_FRAGMENT"
    if len(token.split()) > 3:
        return "LONG_PHRASE"
    if is_broken_token(token):
        return "BROKEN_TOKEN"
    words = [w for w in token.lower().split() if w]
    if words and all(w in _GENERIC_WORDS for w in words):
        return "NON_SKILL_PHRASE"
    return "UNKNOWN_SKILL"


def run_skill_candidate_stage(cv_text: str, cluster_key: str | None) -> SkillCandidateStageResult:
    tight_candidates: List[str] = []
    tight_metrics: dict = {}
    noise_removed: List[str] = []
    split_chunks: List[str] = []
    cleaned_chunks: List[str] = []
    mapping_inputs: List[str] = []
    reduced_candidates: List[str] = []
    cleaned_candidates: List[str] = []
    reducer_traces: List[dict] = []
    phrase_length_gt3_tokens = 0
    duplicate_tokens = 0
    broken_tokens = 0
    multi_skill_phrases = 0
    lemmatized_chunks_count = 0
    pos_rejected_count = 0
    enable_phrase_split = _flag_enabled("ELEVIA_ENABLE_PHRASE_SPLITTING")
    enable_chunk_normalizer = _flag_enabled("ELEVIA_ENABLE_CHUNK_NORMALIZER")
    enable_lemmatization = _flag_enabled("ELEVIA_ENABLE_LIGHT_LEMMATIZATION")
    enable_pos_filter = _flag_enabled("ELEVIA_ENABLE_POS_FILTER")

    try:
        from compass.extraction.tight_skill_extractor import extract_tight_skills
        from compass.extraction.phrase_cleaner import split_phrases, clean_chunks
        from compass.extraction.skill_phrase_reducer import reduce_phrases
        from compass.extraction.skill_token_cleaner import clean_skill_token

        _tight = extract_tight_skills(cv_text, cluster=cluster_key)
        tight_candidates, noise_removed = filter_noise_candidates(_tight.skill_candidates)
        phrase_length_gt3_tokens = sum(1 for p in tight_candidates if len(p.split()) > 3)
        broken_tokens = sum(1 for p in tight_candidates if is_broken_token(p))
        multi_skill_phrases = sum(1 for p in tight_candidates if is_multi_skill_phrase(p))
        seen_norm: set = set()
        for p in tight_candidates:
            key = normalize_canonical_key(p)
            if not key:
                continue
            if key in seen_norm:
                duplicate_tokens += 1
            else:
                seen_norm.add(key)

        reduced_candidates, reducer_trace_objs = reduce_phrases(
            tight_candidates, max_candidates_per_phrase=3
        )
        for token in (tight_candidates + reduced_candidates):
            cleaned = clean_skill_token(token)
            if cleaned and cleaned != token:
                cleaned_candidates.append(cleaned)
        reducer_traces = [
            {"source": t.source, "generated": t.generated, "kept": t.kept, "dropped": t.dropped}
            for t in reducer_trace_objs
        ]
        if enable_phrase_split:
            split_chunks = split_phrases(tight_candidates)
        if enable_chunk_normalizer:
            base_chunks = split_chunks if split_chunks else tight_candidates
            _clean = clean_chunks(
                base_chunks,
                enable_lemmatization=enable_lemmatization,
                enable_pos_filter=enable_pos_filter,
            )
            cleaned_chunks = _clean.cleaned_chunks
            lemmatized_chunks_count = _clean.lemmatized_count
            pos_rejected_count = _clean.pos_rejected_count
        tight_metrics = dict(_tight.metrics or {})
        tight_metrics["candidate_count"] = len(tight_candidates)
        tight_metrics["phrase_length_gt3_tokens"] = phrase_length_gt3_tokens
        tight_metrics["duplicate_tokens"] = duplicate_tokens
        tight_metrics["broken_tokens"] = broken_tokens
        tight_metrics["multi_skill_phrases"] = multi_skill_phrases
        tight_metrics["reduced_candidates_count"] = len(reduced_candidates)
        tight_metrics["cleaned_candidates_count"] = len(cleaned_candidates)
    except Exception:
        pass

    return SkillCandidateStageResult(
        tight_candidates=tight_candidates,
        tight_metrics=tight_metrics,
        noise_removed=noise_removed,
        split_chunks=split_chunks,
        cleaned_chunks=cleaned_chunks,
        mapping_inputs=mapping_inputs,
        reduced_candidates=reduced_candidates,
        cleaned_candidates=cleaned_candidates,
        reducer_traces=reducer_traces,
        phrase_length_gt3_tokens=phrase_length_gt3_tokens,
        duplicate_tokens=duplicate_tokens,
        broken_tokens=broken_tokens,
        multi_skill_phrases=multi_skill_phrases,
        lemmatized_chunks_count=lemmatized_chunks_count,
        pos_rejected_count=pos_rejected_count,
        enable_phrase_split=enable_phrase_split,
        enable_chunk_normalizer=enable_chunk_normalizer,
        enable_lemmatization=enable_lemmatization,
        enable_pos_filter=enable_pos_filter,
    )
