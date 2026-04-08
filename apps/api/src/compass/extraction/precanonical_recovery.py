from __future__ import annotations

import re
from typing import Iterable

from compass.canonical.canonical_store import normalize_canonical_key

_NULL_RE = re.compile(r"\x00+")
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")
_HYPHEN_LINEBREAK_RE = re.compile(r"([A-Za-zÀ-ÿ])-\s*\n\s*([A-Za-zÀ-ÿ])")
_SPLIT_ACRONYM_RE = re.compile(r"(?<!\w)(?:[A-Za-zÀ-ÿ](?:[ \t.\-/,]+)){1,7}[A-Za-zÀ-ÿ](?!\w)")
_SPACED_WORD_CHUNK_RE = re.compile(r"^[A-Za-zÀ-ÿ0-9](?: [A-Za-zÀ-ÿ0-9'’/&-])+$")
_SEGMENT_SPLIT_RE = re.compile(r"[\n\r;|•]+")
_STOPWORDS = {
    "a",
    "alors",
    "and",
    "au",
    "aux",
    "avec",
    "ce",
    "ces",
    "dans",
    "de",
    "des",
    "du",
    "en",
    "et",
    "for",
    "la",
    "le",
    "les",
    "of",
    "ou",
    "par",
    "pour",
    "sur",
    "the",
    "to",
    "un",
    "une",
    "via",
    "with",
}
_ALLOWED_PHRASE_CONNECTORS = {"a", "au", "aux", "d", "de", "des", "du", "l", "la", "le"}
_NOISE_TOKENS = {
    "cv",
    "ok",
    "super",
    "profil",
    "profile",
    "contact",
    "telephone",
    "email",
    "mail",
    "linkedin",
    "permis",
    "loisirs",
}
_KNOWN_SHORT_ACRONYMS = {
    "bi",
    "hr",
    "rh",
    "si",
}
_ALLOWED_SINGLE_TOKENS = {
    "adp",
    "analyse",
    "approvisionnement",
    "budget",
    "budgets",
    "conges",
    "consolidation",
    "cpam",
    "forecasting",
    "formation",
    "maladie",
    "negociation",
    "onboarding",
    "paie",
    "power bi",
    "prospection",
    "recrutement",
    "reporting",
    "rh",
    "sirh",
    "sql",
    "stocks",
}
_DOMAIN_PHRASES = {
    "rh": {
        "administration du personnel",
        "adp",
        "documents prealable a l embauche",
        "gestion du temps de travail",
        "integration des salaries",
        "onboarding",
        "plan de formation",
        "recrutement",
        "sirh",
        "suivi des absences",
        "variables de paie",
    },
    "finance": {
        "analyse financiere",
        "budget",
        "consolidation",
        "ecarts budgetaires",
        "gestion de patrimoine",
        "reporting",
        "reporting mensuel",
    },
    "business": {
        "developpement commercial",
        "gestion portefeuille",
        "gestion portefeuille clients",
        "negociation",
        "prospection",
        "relation client",
    },
    "operations": {
        "approvisionnement",
        "coordination transport",
        "gestion des stocks",
        "support exploitation",
    },
    "data": {
        "bi",
        "data analysis",
        "data quality",
        "etl",
        "forecasting",
        "power bi",
        "reporting",
        "sql",
    },
}
_ALL_KNOWN_PHRASES = {
    phrase
    for phrases in _DOMAIN_PHRASES.values()
    for phrase in phrases
}
_ANCHOR_TOKENS = {
    "absences",
    "adp",
    "analyse",
    "approvisionnement",
    "budget",
    "budgets",
    "clients",
    "commercial",
    "commerciale",
    "commerciales",
    "conges",
    "consolidation",
    "cpam",
    "data",
    "developpement",
    "documents",
    "embauche",
    "ecarts",
    "etl",
    "exploitation",
    "financiere",
    "formation",
    "forecasting",
    "maladie",
    "negociation",
    "onboarding",
    "paie",
    "patrimoine",
    "portefeuille",
    "power",
    "prospection",
    "qualite",
    "quality",
    "recrutement",
    "reporting",
    "rh",
    "salaries",
    "sirh",
    "sql",
    "stocks",
    "temps",
    "transport",
    "travail",
    "variables",
}
_HEAD_TOKENS = {
    "administration",
    "analyse",
    "coordination",
    "consolidation",
    "data",
    "developpement",
    "documents",
    "gestion",
    "integration",
    "negociation",
    "plan",
    "power",
    "prospection",
    "recrutement",
    "reporting",
    "support",
    "suivi",
    "variables",
}
_PHRASE_PATTERNS = [
    re.compile(r"\bgestion du temps de travail\b"),
    re.compile(r"\bvariables? de paie\b"),
    re.compile(r"\bplan de formation\b"),
    re.compile(r"\bdocuments? prealable?s? a l embauche\b"),
    re.compile(r"\banalyse financiere\b"),
    re.compile(r"\breporting(?: mensuel| hebdomadaire| weekly)?\b"),
    re.compile(r"\becarts budgetaires\b"),
    re.compile(r"\bconsolidation\b"),
    re.compile(r"\bdeveloppement commercial\b"),
    re.compile(r"\bgestion portefeuille(?: clients)?\b"),
    re.compile(r"\bcoordination transport\b"),
    re.compile(r"\bgestion des stocks\b"),
    re.compile(r"\bapprovisionnement\b"),
    re.compile(r"\bsupport exploitation\b"),
    re.compile(r"\bdata analysis\b"),
    re.compile(r"\bdata quality\b"),
    re.compile(r"\bpower bi\b"),
    re.compile(r"\bsql\b"),
    re.compile(r"\bforecasting\b"),
]


def _dedupe_preserve(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        key = normalize_canonical_key(value)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _repair_split_acronyms(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        letters = re.findall(r"[A-Za-zÀ-ÿ]", match.group(0))
        joined = "".join(letters)
        if len(letters) >= 3 or joined.lower() in _KNOWN_SHORT_ACRONYMS:
            return joined
        return match.group(0)

    return _SPLIT_ACRONYM_RE.sub(repl, text)


def _repair_spaced_chunk(chunk: str) -> str:
    stripped = chunk.strip()
    if not stripped:
        return stripped
    if not _SPACED_WORD_CHUNK_RE.fullmatch(stripped):
        return stripped
    compact = stripped.replace(" ", "").replace("’", "'")
    return compact


def _repair_spaced_words(line: str) -> str:
    parts = re.split(r"( {2,})", line)
    repaired: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("  "):
            repaired.append(" ")
            continue
        repaired.append(_repair_spaced_chunk(part))
    return "".join(repaired)


def clean_text_for_skill_recovery(text: str) -> str:
    cleaned = text or ""
    cleaned = cleaned.replace("ﬁ", "fi").replace("ﬂ", "fl")
    cleaned = cleaned.replace("’", "'")
    cleaned = _NULL_RE.sub(" ", cleaned)
    cleaned = _HYPHEN_LINEBREAK_RE.sub(r"\1\2", cleaned)
    cleaned = "\n".join(
        _repair_split_acronyms(_repair_spaced_words(line))
        for line in cleaned.splitlines()
    )
    cleaned = re.sub(r"[ \t]*([:;,/|•])\s*", r" \1 ", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n[ \t]+", "\n", cleaned)
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned)
    cleaned = _MULTI_NEWLINE_RE.sub("\n\n", cleaned)
    return cleaned.strip()


def _looks_like_relevant_phrase(phrase: str) -> bool:
    key = normalize_canonical_key(phrase)
    if not key:
        return False
    if key in _ALL_KNOWN_PHRASES or key in _ALLOWED_SINGLE_TOKENS:
        return True
    tokens = [token for token in key.split() if token]
    if not tokens:
        return False
    if any(len(token) == 1 for token in tokens):
        return False
    if len(tokens) == 1:
        return tokens[0] in _ANCHOR_TOKENS
    if len(tokens) > 6:
        return False
    if all(token in _STOPWORDS for token in tokens):
        return False
    if tokens[-1] in _STOPWORDS:
        return False
    anchor_hits = [token for token in tokens if token in _ANCHOR_TOKENS]
    if not anchor_hits:
        return False
    if tokens[0] not in _HEAD_TOKENS:
        return False
    if sum(1 for token in tokens if token in _HEAD_TOKENS) > 1:
        return False
    if len(tokens) > 3:
        return False
    internal_stopwords = {token for token in tokens[1:-1] if token in _STOPWORDS}
    if internal_stopwords and not internal_stopwords.issubset(_ALLOWED_PHRASE_CONNECTORS):
        return False
    if len(tokens) == 2 and tokens[1] in _STOPWORDS:
        return False
    return True


def extract_candidate_phrases(text: str) -> list[str]:
    cleaned = clean_text_for_skill_recovery(text)
    candidates: list[str] = []
    for segment in _SEGMENT_SPLIT_RE.split(cleaned):
        normalized_segment = normalize_canonical_key(segment)
        if not normalized_segment:
            continue
        for pattern in _PHRASE_PATTERNS:
            for match in pattern.finditer(normalized_segment):
                candidates.append(match.group(0))

        tokens = [token for token in normalized_segment.split() if token and token not in _NOISE_TOKENS]
        if not tokens:
            continue
        max_ngram = min(len(tokens), 5)
        for size in range(1, max_ngram + 1):
            for index in range(0, len(tokens) - size + 1):
                phrase = " ".join(tokens[index : index + size]).strip()
                if _looks_like_relevant_phrase(phrase):
                    candidates.append(phrase)

    return _dedupe_preserve(candidates)


def filter_relevant_skill_phrases(phrases: list[str]) -> list[str]:
    filtered: list[str] = []
    for phrase in phrases:
        key = normalize_canonical_key(phrase)
        if not key:
            continue
        if key in _NOISE_TOKENS or key in _STOPWORDS:
            continue
        tokens = [token for token in key.split() if token]
        if not tokens:
            continue
        if len(tokens) == 1 and (len(tokens[0]) < 3 and tokens[0] not in _KNOWN_SHORT_ACRONYMS):
            continue
        if any(len(token) == 1 for token in tokens):
            continue
        if _looks_like_relevant_phrase(key):
            filtered.append(key)
    return _dedupe_preserve(filtered)


def build_precanonical_recovery(text: str) -> dict[str, object]:
    cleaned_text = clean_text_for_skill_recovery(text)
    candidate_phrases = extract_candidate_phrases(cleaned_text)
    relevant_phrases = filter_relevant_skill_phrases(candidate_phrases)
    return {
        "cleaned_text": cleaned_text,
        "candidate_phrases": candidate_phrases,
        "relevant_phrases": relevant_phrases,
        "stats": {
            "candidate_phrases_count": len(candidate_phrases),
            "relevant_phrases_count": len(relevant_phrases),
        },
    }
