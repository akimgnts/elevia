from __future__ import annotations

import re
from typing import List

from compass.canonical.canonical_store import normalize_canonical_key

_ROLE_HINTS = {
    "data",
    "analyst",
    "analytics",
    "developer",
    "engineer",
    "project",
    "product",
    "marketing",
    "sales",
    "finance",
    "hr",
    "human resources",
    "supply",
    "operations",
    "consultant",
    "designer",
    "digital",
    "software",
    "web",
    "business",
    "donnees",
    "données",
    "logistics",
    "cybersecurity",
    "security",
    "legal",
    "procurement",
    "quality",
    "maintenance",
    "automation",
    "accounting",
    "controller",
}

_SKIP_LINE_HINTS = {
    "bonjour",
    "cordialement",
    "experience",
    "experiences",
    "education",
    "formation",
    "contact",
    "email",
    "phone",
}

_FRENCH_MARKERS = {
    "chef",
    "de",
    "des",
    "donnees",
    "données",
    "ingenieur",
    "ingénieur",
    "developpeur",
    "développeur",
    "charge",
    "chargé",
    "responsable",
    "projet",
    "analyse",
    "juridique",
    "juriste",
    "rh",
    "sirh",
    "informatique",
    "ingenierie",
    "ingénierie",
    "commerce",
    "comptable",
    "comptabilite",
    "comptabilité",
    "controle",
    "contrôle",
    "controleur",
    "contrôleur",
    "acheteur",
    "achats",
    "qualite",
    "qualité",
    "maintenance",
    "ressources",
    "humaines",
    "supply",
    "chaine",
    "chaîne",
    "logistique",
    "automatisation",
}

_ENGLISH_MARKERS = {
    "software",
    "developer",
    "engineer",
    "project",
    "manager",
    "data",
    "analyst",
    "marketing",
    "sales",
    "product",
    "legal",
    "finance",
    "hr",
    "business",
    "development",
    "automation",
    "quality",
    "maintenance",
    "procurement",
    "accounting",
    "controller",
    "supply",
    "chain",
}

_TITLE_PHRASE_MAP = {
    "chef de projet digital": "digital project manager",
    "chef de projet": "project manager",
    "chef de produit": "product manager",
    "developpeur logiciel": "software developer",
    "développeur logiciel": "software developer",
    "developpeur web": "web developer",
    "développeur web": "web developer",
    "developpeur full stack": "full stack developer",
    "développeur full stack": "full stack developer",
    "ingenieur logiciel": "software engineer",
    "ingénieur logiciel": "software engineer",
    "ingenieur data": "data engineer",
    "ingénieur data": "data engineer",
    "analyste de donnees": "data analyst",
    "analyste de données": "data analyst",
    "analyste data": "data analyst",
    "data analyse de donnees": "data analyst",
    "data analyse de données": "data analyst",
    "consultant data": "data consultant",
    "responsable marketing": "marketing manager",
    "responsable marketing digital": "digital marketing manager",
    "charge de marketing digital": "digital marketing specialist",
    "chargé de marketing digital": "digital marketing specialist",
    "responsable commercial": "sales manager",
    "supply chain": "supply chain specialist",
    "logistique": "logistics specialist",
    "informatique": "software engineering",
    "ingenierie": "engineering",
    "ingénierie": "engineering",
    "commerce": "sales",
    "controleur de gestion": "financial controller",
    "contrôleur de gestion": "financial controller",
    "ingenieur acheteur": "procurement engineer",
    "ingénieur acheteur": "procurement engineer",
    "responsable rh": "hr manager",
    "responsable ressources humaines": "hr manager",
    "responsable juridique": "legal counsel",
    "juriste": "legal counsel",
    "assistant juridique": "legal assistant",
    "comptable": "accountant",
    "responsable comptable": "accounting manager",
    "ingenieur automatisation": "automation engineer",
    "ingénieur automatisation": "automation engineer",
    "ingenieur qualite": "quality engineer",
    "ingénieur qualité": "quality engineer",
    "ingenieur maintenance": "maintenance engineer",
    "ingénieur maintenance": "maintenance engineer",
    "charge d affaires": "business manager",
    "chargé d affaires": "business manager",
    "charge de developpement commercial": "business development manager",
    "chargé de développement commercial": "business development manager",
    "responsable supply chain": "supply chain manager",
    "responsable rh sirh": "hris manager",
    "rh": "human resources",
    "ressources humaines": "human resources",
}

_PHRASE_TRANSLATIONS = {
    "developpement commercial": "business development",
    "développement commercial": "business development",
    "supply chain": "supply chain",
    "chaine logistique": "supply chain",
    "chaîne logistique": "supply chain",
    "controle de gestion": "financial control",
    "contrôle de gestion": "financial control",
    "ressources humaines": "human resources",
}

_TOKEN_TRANSLATIONS = {
    "chef": "manager",
    "projet": "project",
    "digital": "digital",
    "donnees": "data",
    "données": "data",
    "analyse": "analytics",
    "analyste": "analyst",
    "developpeur": "developer",
    "developper": "developer",
    "développeur": "developer",
    "ingenieur": "engineer",
    "ingénieur": "engineer",
    "logiciel": "software",
    "web": "web",
    "produit": "product",
    "marketing": "marketing",
    "commercial": "sales",
    "charge": "specialist",
    "chargé": "specialist",
    "responsable": "manager",
    "logistique": "logistics",
    "supply": "supply",
    "chain": "chain",
    "acheteur": "buyer",
    "achats": "procurement",
    "juridique": "legal",
    "juriste": "legal",
    "rh": "hr",
    "sirh": "hris",
    "controle": "control",
    "contrôle": "control",
    "gestion": "management",
    "controleur": "controller",
    "contrôleur": "controller",
    "comptable": "accountant",
    "comptabilite": "accounting",
    "comptabilité": "accounting",
    "automatisation": "automation",
    "automation": "automation",
    "qualite": "quality",
    "qualité": "quality",
    "maintenance": "maintenance",
    "legal": "legal",
    "finance": "finance",
    "business": "business",
    "development": "development",
    "commerce": "sales",
    "informatique": "software",
    "ingenierie": "engineering",
    "ingénierie": "engineering",
}

_DROP_TOKENS = {
    "candidature",
    "spontanee",
    "spontanée",
    "lettre",
    "motivation",
    "poste",
    "vise",
    "visé",
    "profil",
    "experience",
    "experiences",
    "professional",
    "current",
    "present",
    "stage",
    "internship",
    "intern",
    "h",
    "f",
    "hf",
    "vie",
    "v.i.e",
    "via",
}

_STOP_VIE_SEGMENTS = {
    "allemagne",
    "germany",
    "espagne",
    "spain",
    "chine",
    "china",
    "japon",
    "japan",
    "argentine",
    "mexique",
    "mexico",
    "singapour",
    "singapore",
    "royaume uni",
    "uk",
    "france",
    "lvmh",
    "engie",
    "pernod ricard",
    "business france",
    "bouygues",
    "michelin",
    "axa",
    "decathlon",
}

_HTML_RE = re.compile(r"<[^>]+>")
_SPLIT_RE = re.compile(r"[|:\u2013\u2014-]+")
_NON_WORD_RE = re.compile(r"[^a-z0-9+#./\s]+")
_VIE_PREFIX_RE = re.compile(r"\b(v\.?i\.?e\.?|volontaire international(?: en entreprise)?)\b", re.IGNORECASE)
_HF_RE = re.compile(r"\b[hf](?:/[hf])?\b|\(h/f\)|\(f/h\)|\bh/f\b|\bf/h\b", re.IGNORECASE)


def _strip_html(text: str) -> str:
    return _HTML_RE.sub(" ", text or "")


def _clean_line(line: str) -> str:
    line = _strip_html(line)
    return " ".join(line.split()).strip()


def _apply_phrase_map(norm: str) -> str:
    if norm in _TITLE_PHRASE_MAP:
        return normalize_canonical_key(_TITLE_PHRASE_MAP[norm])
    return norm


def _apply_phrase_translations(norm: str) -> str:
    text = norm
    for source, target in sorted(_PHRASE_TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        text = text.replace(normalize_canonical_key(source), normalize_canonical_key(target))
    return normalize_canonical_key(text)


def _extract_vie_functional_segment(title: str) -> str:
    line = normalize_canonical_key(_HF_RE.sub(" ", title or ""))
    if not line or "vie" not in line.replace(".", ""):
        return ""
    line = _VIE_PREFIX_RE.sub(" ", line)
    for stop in sorted(_STOP_VIE_SEGMENTS, key=len, reverse=True):
        line = line.replace(stop, " ")
    line = normalize_canonical_key(line)
    parts = []
    for chunk in _SPLIT_RE.split(line):
        cleaned = normalize_canonical_key(chunk)
        if not cleaned:
            continue
        cleaned = cleaned.replace("/", " ")
        cleaned = " ".join(cleaned.split())
        if cleaned in _STOP_VIE_SEGMENTS:
            continue
        if cleaned and any(hint in cleaned for hint in _ROLE_HINTS | set(_TOKEN_TRANSLATIONS.keys())):
            parts.append(cleaned)
    if parts:
        best = sorted(parts, key=lambda part: (-sum(2 for hint in _ROLE_HINTS if hint in part), len(part)))[0]
        return best

    words = [w for w in line.split() if w and w not in _DROP_TOKENS]
    for size in (3, 2, 1):
        for idx in range(0, max(0, len(words) - size + 1)):
            phrase = " ".join(words[idx: idx + size])
            if phrase in _STOP_VIE_SEGMENTS:
                continue
            if any(hint in phrase for hint in _ROLE_HINTS | set(_TOKEN_TRANSLATIONS.keys())):
                return phrase
    return ""


def is_vie_or_noisy_title(title: str) -> bool:
    norm = normalize_canonical_key(title)
    if not norm:
        return True
    if _VIE_PREFIX_RE.search(title or ""):
        return True
    if norm in {"profil polyvalent", "experience professionnelle", "candidature spontanee", "manager"}:
        return True
    if len(norm.split()) > 8:
        return True
    return False


def _score_line(line: str) -> tuple[int, str]:
    norm = normalize_canonical_key(line)
    if not norm or norm in _SKIP_LINE_HINTS:
        return (0, "")
    if any(ch.isdigit() for ch in norm) and len(norm.split()) <= 2:
        return (0, "")

    vie_candidate = _extract_vie_functional_segment(line)
    if vie_candidate:
        return (12, vie_candidate)

    best = norm
    best_score = sum(2 for hint in _ROLE_HINTS if hint in best)
    if any(sep in line for sep in (":", "-", "–", "—", "|", "/")):
        role_parts: list[tuple[str, int]] = []
        for part in re.split(r"[|:/\u2013\u2014-]+", line):
            part_norm = normalize_canonical_key(part).replace("/", " ").strip()
            part_norm = " ".join(part_norm.split())
            if not part_norm:
                continue
            part_score = sum(2 for hint in _ROLE_HINTS if hint in part_norm)
            if part_score > 0:
                role_parts.append((part_norm, part_score))
            if part_score > best_score or (part_score == best_score and len(part_norm) < len(best)):
                best = part_norm
                best_score = part_score
        if "/" in line and len(role_parts) >= 2:
            combined = normalize_canonical_key(" ".join(part for part, _ in role_parts[:2]))
            combined_score = sum(2 for hint in _ROLE_HINTS if hint in combined)
            if combined_score >= best_score:
                best = combined
                best_score = combined_score

    score = sum(2 for hint in _ROLE_HINTS if hint in best)
    if len(best.split()) <= 8:
        score += 1
    else:
        score -= 3
    if 2 <= len(best) <= 80:
        score += 1
    if any(mark in line for mark in (".", ",", ";")):
        score -= 2
    return (score, best)


def extract_title(text: str) -> str:
    lines = [_clean_line(line) for line in (text or "").splitlines()]
    lines = [line for line in lines if line and not ({"{", "}", ";"} & set(line))]

    best_title = ""
    best_score = -1
    for line in lines[:30]:
        score, candidate = _score_line(line)
        if score > best_score:
            best_score = score
            best_title = candidate

    return normalize_canonical_key(best_title)


def detect_language(title: str) -> str:
    norm = normalize_canonical_key(title)
    if not norm:
        return "unknown"
    tokens = set(norm.split())
    fr_markers = {normalize_canonical_key(t) for t in _FRENCH_MARKERS}
    en_markers = {normalize_canonical_key(t) for t in _ENGLISH_MARKERS}
    fr_score = len(tokens & fr_markers)
    en_score = len(tokens & en_markers)
    if fr_score > en_score:
        return "fr"
    if en_score > fr_score:
        return "en"
    if fr_score == en_score and fr_score > 0:
        return "fr"
    return "en"


def translate_title_if_needed(title: str) -> str:
    norm = normalize_canonical_key(title)
    if not norm:
        return ""

    vie_segment = _extract_vie_functional_segment(norm)
    if vie_segment:
        norm = vie_segment
        if detect_language(norm) != "fr":
            return norm

    norm = _apply_phrase_map(norm)
    if detect_language(norm) != "fr":
        return norm

    norm = _apply_phrase_translations(norm)
    norm = _apply_phrase_map(norm)
    if norm in _TITLE_PHRASE_MAP:
        return normalize_canonical_key(_TITLE_PHRASE_MAP[norm])

    translated: List[str] = []
    for token in norm.split():
        if token in {"de", "du", "des", "la", "le", "les", "et", "en", "d", "l"}:
            continue
        translated.append(_TOKEN_TRANSLATIONS.get(token, token))
    return normalize_canonical_key(" ".join(translated))


def tokenize_title(title: str) -> List[str]:
    norm = normalize_title(title)
    if not norm:
        return []
    tokens: List[str] = []
    for token in _NON_WORD_RE.sub(" ", norm).split():
        if token in _DROP_TOKENS:
            continue
        tokens.append(token)
    return tokens


def normalize_title(title: str) -> str:
    base = normalize_canonical_key(_HF_RE.sub(" ", title or ""))
    if not base:
        return ""
    vie_segment = _extract_vie_functional_segment(title)
    if vie_segment:
        base = vie_segment
    if is_vie_or_noisy_title(title) or any(sep in (title or "") for sep in ("/", "-", "–", "—", "|")):
        extracted = extract_title(title)
        if extracted:
            base = extracted
    if vie_segment and detect_language(vie_segment) != "fr":
        translated = normalize_canonical_key(vie_segment)
    else:
        translated = translate_title_if_needed(base)
    tokens = []
    for token in translated.split():
        if token in _DROP_TOKENS:
            continue
        tokens.append(token)
    return normalize_canonical_key(" ".join(tokens))


def normalize_title_payload(title: str) -> dict[str, object]:
    normalized_title = normalize_title(title)
    return {
        "normalized_title": normalized_title,
        "language": detect_language(title),
        "title_tokens": tokenize_title(normalized_title),
    }
