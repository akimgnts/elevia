"""
ats_keywords.py — Deterministic ATS keyword extraction.

Strategy:
  1. Concatenate title + description
  2. Normalize (lowercase, strip accents, remove punctuation)
  3. Tokenize, filter stopwords + short tokens
  4. Count frequency
  5. Sort by freq DESC then alpha (stable, deterministic)
  6. Return top MAX_KEYWORDS

No ML, no randomness — same input always produces same output.
"""

import re
import unicodedata
from collections import Counter
from typing import List

MAX_KEYWORDS = 12
MIN_TOKEN_LEN = 3

# FR + EN stopwords specific to job offers
_STOPWORDS = frozenset({
    # French articles/prepositions
    "les", "des", "une", "pour", "par", "sur", "dans", "avec", "sans",
    "que", "qui", "est", "son", "ses", "notre", "votre", "leur", "leurs",
    "vous", "nous", "ils", "elle", "elles", "tout", "tous", "toute",
    "cette", "cet", "ces", "son", "mais", "aux", "aux", "car",
    "sont", "avoir", "etre", "faire", "tres", "plus", "moins", "bien",
    # Job-offer noise
    "chez", "mois", "mission", "vie", "poste", "profil", "candidat",
    "entreprise", "equipe", "sein", "cadre", "contrat", "cdi", "cdd",
    "stage", "emploi", "annee", "ans", "debutant", "vos", "nos",
    "rejoindre", "integrer", "evoluer", "participer", "contribuer",
    "assurer", "garantir", "gerer", "mettre", "oeuvre", "place",
    "sein", "equipes", "travail", "poste", "offre", "candidature",
    # English filler
    "the", "and", "for", "with", "this", "that", "from", "will",
    "your", "our", "their", "have", "has", "are", "was", "were",
    "been", "being", "can", "may", "must", "shall", "should", "would",
    "could", "not", "but", "all", "any", "his", "her", "its", "they",
    # Generic noise
    "etc", "niveau", "requis", "souhaite", "exige", "experience",
    "annees", "years", "minimum", "maximum", "lieu", "ville", "pays",
})


def _strip_accents(text: str) -> str:
    """Remove diacritics for normalization."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalize(text: str) -> str:
    """Lowercase + strip accents + punctuation → spaces."""
    t = _strip_accents(text.lower())
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def extract_ats_keywords(
    title: str,
    description: str,
    max_kw: int = MAX_KEYWORDS,
) -> List[str]:
    """
    Extract ATS keywords deterministically from offer title + description.

    Args:
        title: Offer title
        description: Offer description (can be long, truncated internally to 1200)
        max_kw: Maximum keywords to return (default 12)

    Returns:
        List of keywords sorted by freq DESC, then alpha — deterministic.
    """
    # Truncate description to keep extraction fast and focused
    desc_trunc = (description or "")[:1200]
    combined = f"{title or ''} {desc_trunc}"

    normalized = _normalize(combined)
    tokens = normalized.split()

    filtered = [
        t for t in tokens
        if len(t) >= MIN_TOKEN_LEN
        and t not in _STOPWORDS
        and not t.isdigit()
    ]

    freq = Counter(filtered)
    # Stable sort: freq DESC, then alpha ASC
    sorted_kw = sorted(freq.keys(), key=lambda k: (-freq[k], k))

    return sorted_kw[:max_kw]


def keywords_overlap(
    profile_skills: List[str],
    offer_keywords: List[str],
) -> tuple[List[str], List[str]]:
    """
    Compute (matched, missing) between profile skills and offer keywords.

    Both sides are normalized for comparison. Deterministic.
    """
    norm_skills = {_normalize(s) for s in profile_skills if s}
    matched = [k for k in offer_keywords if _normalize(k) in norm_skills]
    missing = [k for k in offer_keywords if _normalize(k) not in norm_skills]
    return matched, missing
