from __future__ import annotations

import re
from typing import Dict, Iterable, List, Sequence

from compass.canonical.canonical_store import normalize_canonical_key

from .domain_rules import infer_domain
from .object_normalizer import normalize_object_phrase

_METADATA_HEADERS = {
    "contact",
    "contacts",
    "coordonnees",
    "coordonnees personnelles",
    "langues",
    "languages",
    "language",
    "interests",
    "centres d interet",
    "interets",
    "profile",
    "profil",
    "professional experience",
    "experience",
    "experiences",
    "education",
    "formation",
    "skills",
    "competences",
    "technical stack",
    "creative tools",
    "business skills",
    "marketing skills",
    "data capabilities",
    "soft skills",
    "what i bring",
    "projects",
}
_LANGUAGE_TOKENS = {
    "francais",
    "anglais",
    "english",
    "espagnol",
    "spanish",
    "allemand",
    "german",
    "italien",
    "italian",
    "natif",
    "native",
    "professionnel",
    "professionnelle",
    "professional",
    "courant",
    "bilingue",
    "bilingual",
    "intermediate",
}
_NOISE_TOKENS = {
    "and",
    "de",
    "des",
    "du",
    "la",
    "le",
    "les",
    "the",
    "with",
    "for",
    "sur",
    "dans",
    "via",
    "et",
    "en",
    "d",
    "l",
}
_TOOL_TOKENS = {
    "sap",
    "sql",
    "excel",
    "python",
    "power",
    "bi",
    "power bi",
    "power query",
    "tableau",
    "dataiku",
    "figma",
    "photoshop",
    "illustrator",
    "premiere",
    "premiere pro",
    "crm",
    "erp",
    "api",
    "apis",
    "rest api",
    "rest apis",
    "git",
    "vba",
}
_ACTION_PREFIXES = {
    "analyse",
    "analyser",
    "analysis",
    "gestion",
    "gerer",
    "manage",
    "management",
    "suivi",
    "pilotage",
    "reporting",
    "developpement",
    "prospection",
    "coordination",
    "support",
}
_COMPOUND_PHRASES = {
    "data analysis",
    "business analysis",
    "data cleaning",
    "anomaly detection",
    "data integration",
    "multi source analysis",
    "signal extraction",
    "customer understanding",
    "systems thinking",
    "problem solving",
    "process analysis",
    "data quality",
    "email campaigns",
    "email campaign",
    "campaign analysis",
    "content creation",
    "content design",
    "offer structuring",
    "commercial follow up",
    "customer journey",
    "sales logic",
    "needs analysis",
    "power bi",
    "power query",
    "rest api",
    "rest apis",
    "machine learning",
    "financial analysis",
    "internal control",
    "gestion portefeuille",
    "portefeuille clients",
}
_LEVEL_TOKEN_RE = re.compile(r"^[abc][12]$", re.IGNORECASE)
_EMAIL_OR_URL_RE = re.compile(r"@|https?://|www\.", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}")
_SPLIT_RE = re.compile(r"[\n,;|•·]+")


def _dedupe_signals(items: Iterable[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[str] = set()
    for item in items:
        key = normalize_canonical_key(item.get("normalized") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _is_language_line(key: str) -> bool:
    tokens = [token for token in key.split() if token]
    if not tokens:
        return False
    filtered = [token for token in tokens if token not in {"-", "—"}]
    if not filtered:
        return False
    return all(
        token in _LANGUAGE_TOKENS or _LEVEL_TOKEN_RE.fullmatch(token) is not None
        for token in filtered
    )


def _is_metadata_line(text: str) -> bool:
    key = normalize_canonical_key(text or "")
    if not key:
        return True
    if key in _METADATA_HEADERS:
        return True
    if _EMAIL_OR_URL_RE.search(text) or _PHONE_RE.search(text):
        return True
    if _is_language_line(key):
        return True
    tokens = key.split()
    if len(tokens) <= 3 and " ".join(tokens) in _METADATA_HEADERS:
        return True
    return False


def _segment_line(text: str) -> list[str]:
    cleaned = str(text or "").strip()
    if not cleaned:
        return []
    if ":" in cleaned:
        left, right = cleaned.split(":", 1)
        if normalize_canonical_key(left) in _METADATA_HEADERS:
            cleaned = right.strip()
    if not cleaned:
        return []
    return [part.strip(" -\t") for part in _SPLIT_RE.split(cleaned) if part.strip(" -\t")]


def _atomic_phrases(text: str) -> list[str]:
    key = normalize_canonical_key(text or "")
    tokens = [token for token in key.split() if token]
    if not tokens:
        return []
    if len(tokens) <= 4 and tokens[0] in _ACTION_PREFIXES:
        return [" ".join(tokens)]

    phrases: list[str] = []
    index = 0
    while index < len(tokens):
        matched = None
        for size in (3, 2):
            if index + size > len(tokens):
                continue
            candidate = " ".join(tokens[index : index + size])
            if candidate in _COMPOUND_PHRASES:
                matched = candidate
                index += size
                break
        if matched:
            phrases.append(matched)
            continue
        token = tokens[index]
        index += 1
        if token in _NOISE_TOKENS or len(token) <= 2:
            continue
        if token in _TOOL_TOKENS or len(tokens) <= 3 or bool(phrases):
            phrases.append(token)

    if not phrases and len(tokens) <= 4:
        phrases.append(" ".join(tokens))
    return phrases


def _make_signal(*, raw: str, normalized: str, domain_hint: str = "", confidence: float) -> dict | None:
    raw_text = str(raw or "").strip()
    normalized_text = normalize_canonical_key(normalized or raw_text)
    if not normalized_text:
        return None
    domain, domain_weight, _ = infer_domain(raw_text, normalized_text, domain_hint)
    if domain == "unknown" and domain_hint:
        domain = domain_hint
    light_normalized = normalize_object_phrase(
        normalized_text,
        domain=domain if domain != "unknown" else "",
    )
    final_normalized = normalize_canonical_key(light_normalized or normalized_text)
    if not final_normalized:
        return None
    tokens = [token for token in final_normalized.split() if token and token not in _NOISE_TOKENS]
    if not tokens:
        return None
    if len(tokens) == 1 and tokens[0] in _LANGUAGE_TOKENS:
        return None
    final_confidence = max(confidence, 0.52)
    if domain != "unknown":
        final_confidence += min(domain_weight, 1.0) * 0.08
    return {
        "raw": raw_text or final_normalized,
        "normalized": final_normalized,
        "tokens": tokens,
        "domain": domain,
        "confidence": round(min(final_confidence, 0.95), 4),
    }


def _signals_from_structured_units(structured_units: Sequence[dict]) -> list[dict]:
    signals: list[dict] = []
    for unit in list(structured_units or []):
        if not isinstance(unit, dict):
            continue
        domain = str(unit.get("domain") or "")
        ranking_score = float(unit.get("ranking_score") or unit.get("specificity_score") or 0.0)
        confidence = 0.72 + min(max(ranking_score, 0.0), 2.0) * 0.1
        primary_raw = str(unit.get("action_object_text") or unit.get("object") or unit.get("raw_text") or "")
        object_text = str(unit.get("object") or "")
        action = str(unit.get("action") or "")
        tools = list(unit.get("tools") or [])
        if primary_raw:
            normalized = normalize_object_phrase(
                object_text or primary_raw,
                action=action,
                domain=domain,
                tools=tools,
            ) or primary_raw
            signal = _make_signal(raw=primary_raw, normalized=normalized, domain_hint=domain, confidence=confidence)
            if signal:
                signals.append(signal)
        if object_text and normalize_canonical_key(object_text) != normalize_canonical_key(primary_raw):
            signal = _make_signal(
                raw=object_text,
                normalized=normalize_object_phrase(object_text, action=action, domain=domain, tools=tools) or object_text,
                domain_hint=domain,
                confidence=max(confidence - 0.08, 0.62),
            )
            if signal:
                signals.append(signal)
    return signals


def _signals_from_raw_text(raw_text: str) -> list[dict]:
    signals: list[dict] = []
    for line in (raw_text or "").splitlines():
        if _is_metadata_line(line):
            continue
        for segment in _segment_line(line):
            if _is_metadata_line(segment):
                continue
            phrases = _atomic_phrases(segment)
            if not phrases:
                phrases = [normalize_canonical_key(segment)] if len(normalize_canonical_key(segment).split()) <= 4 else []
            if not phrases:
                continue
            segment_key = normalize_canonical_key(segment)
            inferred_domain, _, _ = infer_domain(segment_key)
            for phrase in phrases:
                phrase_key = normalize_canonical_key(phrase)
                if not phrase_key:
                    continue
                base_confidence = 0.64
                if phrase_key in _COMPOUND_PHRASES:
                    base_confidence = 0.74
                elif phrase_key in _TOOL_TOKENS:
                    base_confidence = 0.7
                elif len(phrase_key.split()) >= 2:
                    base_confidence = 0.68
                signal = _make_signal(
                    raw=phrase,
                    normalized=phrase,
                    domain_hint=inferred_domain if inferred_domain != "unknown" else "",
                    confidence=base_confidence,
                )
                if signal:
                    signals.append(signal)
    return signals


def build_enriched_signals(structured_units: Sequence[dict], raw_text: str) -> Dict[str, List[dict]]:
    enriched_signals = _dedupe_signals(
        [
            *_signals_from_structured_units(structured_units),
            *_signals_from_raw_text(raw_text),
        ]
    )
    return {"enriched_signals": enriched_signals}
