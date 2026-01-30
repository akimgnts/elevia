"""
extractors.py
=============
Sprint 6 - Extraction profil (une seule fois)

Conforme à: docs/features/06_MATCHING_MINIMAL_EXPLICABLE.md
"""

from typing import Dict, List, Set, Optional
import re
from dataclasses import dataclass


# Mapping ordinal fixe pour les niveaux d'études (spec ligne 130-132)
EDUCATION_LEVELS: Dict[str, int] = {
    "bac": 1,
    "bac+2": 2,
    "bac+3": 3,
    "bac+5": 4,
    "phd": 5,
}


@dataclass(frozen=True)
class ExtractedProfile:
    """
    Profil pré-extrait (immutable).
    Extrait UNE SEULE FOIS selon spec ligne 153.
    """
    profile_id: str
    skills: frozenset  # Set immuable de skills normalisées
    languages: frozenset  # Set immuable de langues normalisées
    education_level: int  # Niveau ordinal (0 si non spécifié)
    preferred_countries: frozenset  # Set immuable de pays canonisés


_SKILL_WS_RE = re.compile(r"\s+")
_SKILL_PUNCT_RE = re.compile(r"[^\w\s\+#]", flags=re.UNICODE)


def normalize_skill_label(skill: str) -> str:
    """Normalise un label de compétence (lowercase, trim, espace/punct)."""
    if not skill:
        return ""
    value = skill.lower().strip()
    value = _SKILL_PUNCT_RE.sub(" ", value)
    value = _SKILL_WS_RE.sub(" ", value).strip()
    return value


def normalize_skill(skill: str) -> str:
    """Normalise une compétence (lowercase, trim, espace/punct)."""
    return normalize_skill_label(skill)


def normalize_language(lang: str) -> str:
    """Normalise une langue (lowercase, strip)."""
    return lang.lower().strip()


def canonize_country(country: str) -> str:
    """
    Canonise un pays (UNE SEULE FOIS selon spec ligne 154).
    Lowercase, strip, mapping des variantes courantes.
    """
    c = country.lower().strip()

    # Mapping des variantes courantes
    COUNTRY_ALIASES = {
        "france": "france",
        "fr": "france",
        "allemagne": "allemagne",
        "germany": "allemagne",
        "de": "allemagne",
        "espagne": "espagne",
        "spain": "espagne",
        "es": "espagne",
        "italie": "italie",
        "italy": "italie",
        "it": "italie",
        "royaume-uni": "royaume-uni",
        "uk": "royaume-uni",
        "united kingdom": "royaume-uni",
        "gb": "royaume-uni",
        "etats-unis": "etats-unis",
        "usa": "etats-unis",
        "united states": "etats-unis",
        "us": "etats-unis",
        "belgique": "belgique",
        "belgium": "belgique",
        "be": "belgique",
        "suisse": "suisse",
        "switzerland": "suisse",
        "ch": "suisse",
        "pays-bas": "pays-bas",
        "netherlands": "pays-bas",
        "nl": "pays-bas",
        "canada": "canada",
        "ca": "canada",
        "japon": "japon",
        "japan": "japon",
        "jp": "japon",
        "chine": "chine",
        "china": "chine",
        "cn": "chine",
        "singapour": "singapour",
        "singapore": "singapour",
        "sg": "singapour",
        "hong kong": "hong kong",
        "hk": "hong kong",
        "australie": "australie",
        "australia": "australie",
        "au": "australie",
    }

    return COUNTRY_ALIASES.get(c, c)


def parse_education_level(education: Optional[str]) -> int:
    """
    Parse le niveau d'études vers ordinal.
    Retourne 0 si non spécifié ou non reconnu.
    """
    if not education:
        return 0

    e = education.lower().strip()

    # Mapping étendu vers niveaux standards
    EDUCATION_ALIASES = {
        "bac": 1,
        "baccalauréat": 1,
        "baccalaureat": 1,
        "bac+2": 2,
        "bts": 2,
        "dut": 2,
        "deug": 2,
        "bac+3": 3,
        "licence": 3,
        "bachelor": 3,
        "bac+4": 4,
        "maitrise": 4,
        "bac+5": 4,
        "master": 4,
        "ingénieur": 4,
        "ingenieur": 4,
        "phd": 5,
        "doctorat": 5,
        "doctorate": 5,
        "bac+8": 5,
    }

    return EDUCATION_ALIASES.get(e, 0)


def extract_profile(raw_profile: Dict) -> ExtractedProfile:
    """
    Extrait et normalise un profil UNE SEULE FOIS.

    Args:
        raw_profile: Dictionnaire brut du profil

    Returns:
        ExtractedProfile: Profil pré-extrait et immutable

    Spec: "Profil extrait une seule fois" (ligne 153)
    """
    profile_id = raw_profile.get("id", raw_profile.get("profile_id", "unknown"))

    # Skills normalisées
    # Support both formats: "skills": ["str"] and "detected_capabilities": [{name, level}]
    raw_skills = raw_profile.get("skills", [])
    detected_caps = raw_profile.get("detected_capabilities", [])

    if detected_caps and isinstance(detected_caps, list):
        # Extract skill names from detected_capabilities objects
        raw_skills = [
            cap.get("name") if isinstance(cap, dict) else cap
            for cap in detected_caps
        ]
    elif isinstance(raw_skills, str):
        raw_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]

    skills = frozenset(normalize_skill(s) for s in raw_skills if s and isinstance(s, str))

    # Langues normalisées
    # Support both formats: "languages": ["str"] and "languages": [{code, level}]
    raw_languages = raw_profile.get("languages", [])
    if isinstance(raw_languages, str):
        raw_languages = [l.strip() for l in raw_languages.split(",") if l.strip()]
    elif isinstance(raw_languages, list) and raw_languages and isinstance(raw_languages[0], dict):
        # Extract language codes from objects
        raw_languages = [
            lang.get("code") if isinstance(lang, dict) else lang
            for lang in raw_languages
        ]
    languages = frozenset(normalize_language(l) for l in raw_languages if l and isinstance(l, str))

    # Niveau d'études
    # Support both formats: "education": "str" and "education_summary": {level}
    education_raw = raw_profile.get("education")
    if education_raw is None:
        edu_summary = raw_profile.get("education_summary", {})
        if isinstance(edu_summary, dict):
            education_raw = edu_summary.get("level")
    education_level = parse_education_level(education_raw)

    # Pays préférés canonisés
    raw_countries = raw_profile.get("preferred_countries", [])
    if isinstance(raw_countries, str):
        raw_countries = [c.strip() for c in raw_countries.split(",") if c.strip()]
    preferred_countries = frozenset(canonize_country(c) for c in raw_countries if c)

    return ExtractedProfile(
        profile_id=str(profile_id),
        skills=skills,
        languages=languages,
        education_level=education_level,
        preferred_countries=preferred_countries,
    )
