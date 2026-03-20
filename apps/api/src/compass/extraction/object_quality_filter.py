from __future__ import annotations

import re
from typing import List

from compass.canonical.canonical_store import normalize_canonical_key

_GENERIC_OBJECTS = {
    "analyse", "suivi", "gestion", "communication", "organisation", "projet", "projects",
    "project", "tableau", "tableaux", "donnees", "données", "clients", "client", "performances",
    "commercial", "commerciale", "rh", "reporting", "budget", "budgets", "data", "outil", "outils",
}

_TITLE_HINTS = {
    "assistant", "assistante", "chargee", "chargé", "charge", "commerciale", "commercial", "coordinateur",
    "coordinatrice", "gestionnaire", "agent", "stage", "stagiaire", "junior", "senior", "generaliste",
    "generalist", "controller", "controleur", "comptable", "approvisionneuse", "approvisionneur",
}

_WEAK_SINGLE_TOKEN_ALLOWLIST = {
    "recrutement", "onboarding", "budgets", "factures", "livraisons", "expeditions", "approvisionnement",
}

_OBJECT_FRAGMENT_RE = re.compile(r"\b[bcdfghjklmnpqrstvwxz]\b")
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_COMPANY_SUFFIX_HINTS = {"services", "groupe", "sas", "sa", "sarl", "b2b"}
_TOOLISH_HINTS = {"excel", "salesforce", "sap", "power bi", "looker", "mailchimp", "wordpress", "canva", "tableau", "outlook", "teams", "tms"}
_LANGUAGE_HINTS = {"francais", "anglais", "english", "espagnol", "german", "allemand", "italien"}
_WEAK_TRAILING_TOKENS = {"c", "g", "s", "p", "m", "r", "i", "l", "o"}
_METADATA_TOKENS = {
    "cv", "profil", "profile", "resume", "contact", "email", "telephone", "tel", "linkedin",
    "master", "bts", "licence", "universite", "université", "ecole", "école", "stage",
}


def evaluate_object_quality(object_text: str) -> tuple[bool, float, list[str]]:
    normalized = normalize_canonical_key(object_text or "")
    if not normalized:
        return False, 0.0, ["empty"]

    tokens = [token for token in normalized.split() if token]
    reasons: List[str] = []
    score = 1.0

    if len(tokens) == 1:
        if tokens[0] in _WEAK_SINGLE_TOKEN_ALLOWLIST:
            score -= 0.15
        else:
            reasons.append("single_token")
            score -= 0.45
    elif len(tokens) > 6:
        reasons.append("too_long")
        score -= 0.2

    if normalized in _GENERIC_OBJECTS:
        reasons.append("generic_object")
        score -= 0.55
    elif all(token in _GENERIC_OBJECTS for token in tokens):
        reasons.append("generic_tokens_only")
        score -= 0.45

    if _YEAR_RE.search(normalized):
        reasons.append("year_metadata")
        score -= 0.35

    if any(token in _TITLE_HINTS for token in tokens[:3]):
        reasons.append("title_like")
        score -= 0.35

    if any(suffix in tokens for suffix in _COMPANY_SUFFIX_HINTS):
        reasons.append("company_like")
        score -= 0.25

    if any(_OBJECT_FRAGMENT_RE.fullmatch(token) for token in tokens):
        reasons.append("fragment_token")
        score -= 0.45

    tool_hits = 0
    for hint in _TOOLISH_HINTS:
        if hint in normalized:
            tool_hits += 1
    if tool_hits and len(tokens) <= 3:
        reasons.append("tool_like")
        score -= 0.25

    if all(token in _LANGUAGE_HINTS for token in tokens):
        reasons.append("language_metadata")
        score -= 0.55

    if any(token in _METADATA_TOKENS for token in tokens):
        reasons.append("metadata_like")
        score -= 0.2

    if any(token in _WEAK_TRAILING_TOKENS for token in tokens[-2:]):
        reasons.append("weak_trailing_fragment")
        score -= 0.25

    if len(tokens) >= 2 and any(token not in _GENERIC_OBJECTS for token in tokens):
        score += 0.1
    if len(tokens) >= 3:
        score += 0.05

    score = max(0.0, min(score, 1.0))
    accepted = score >= 0.58 and not ({"title_like", "fragment_token", "language_metadata"} & set(reasons))
    return accepted, round(score, 3), reasons


def is_generic_object(value: str) -> bool:
    return normalize_canonical_key(value or "") in _GENERIC_OBJECTS
