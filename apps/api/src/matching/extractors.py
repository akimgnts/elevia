"""
extractors.py
=============
Sprint 6 - Extraction profil (une seule fois)

Conforme à: docs/features/06_MATCHING_MINIMAL_EXPLICABLE.md
"""

from typing import Dict, List, Set, Optional
import re
from dataclasses import dataclass

import importlib
import os
import logging

# Import skill aliases for profile expansion (EN→FR translation)
try:
    from ..esco.extract import SKILL_ALIASES
    from ..esco.mapper import map_skill
    from ..esco.uri_collapse import collapse_to_uris
except ImportError:
    try:
        _esco_extract = importlib.import_module("esco.extract")
        _esco_mapper = importlib.import_module("esco.mapper")
        _esco_collapse = importlib.import_module("esco.uri_collapse")
        SKILL_ALIASES = _esco_extract.SKILL_ALIASES
        map_skill = _esco_mapper.map_skill
        collapse_to_uris = _esco_collapse.collapse_to_uris
    except ImportError:
        SKILL_ALIASES = {}
        map_skill = None
        collapse_to_uris = None

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
    skills_uri: frozenset  # Set immuable de skills URIs (ESCO + DOMAIN) pour scoring
    languages: frozenset  # Set immuable de langues normalisées
    education_level: int  # Niveau ordinal (0 si non spécifié)
    preferred_countries: frozenset  # Set immuable de pays canonisés
    skill_source: str = "skills"
    matching_skills_count: int = 0
    capabilities_count: int = 0
    skills_uri_count: int = 0
    skills_uri_collapsed_dupes: int = 0
    skills_unmapped_count: int = 0


_SKILL_WS_RE = re.compile(r"\s+")
_SKILL_PUNCT_RE = re.compile(r"[^\w\s\+#]", flags=re.UNICODE)

logger = logging.getLogger(__name__)


def _debug_matching_enabled() -> bool:
    value = os.getenv("ELEVIA_DEBUG_MATCHING", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _sample_list(values, limit=50):
    sample = []
    for item in values:
        if isinstance(item, str):
            sample.append(item)
        elif isinstance(item, dict):
            if "name" in item:
                sample.append(str(item.get("name")))
            elif "label" in item:
                sample.append(str(item.get("label")))
            elif "raw_skill" in item:
                sample.append(str(item.get("raw_skill")))
            else:
                sample.append(str(item))
        else:
            sample.append(str(item))
        if len(sample) >= limit:
            break
    return sample


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


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _expand_profile_skills(skills: List[str]) -> List[str]:
    """
    Expand profile skills using SKILL_ALIASES, preserving order.

    Adds French ESCO labels for English skills to enable matching.
    Example: 'python' → adds 'python (programmation informatique)'
    """
    expanded: List[str] = []
    seen: set[str] = set()
    for skill in skills:
        if skill not in seen:
            seen.add(skill)
            expanded.append(skill)
        skill_lower = skill.lower()
        if skill_lower in SKILL_ALIASES:
            for alias in SKILL_ALIASES[skill_lower]:
                alias_norm = normalize_skill(alias)
                if alias_norm and alias_norm not in seen:
                    seen.add(alias_norm)
                    expanded.append(alias_norm)
    return expanded


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
    raw_skills = raw_profile.get("matching_skills", None)
    skill_source = "matching_skills"
    detected_caps = raw_profile.get("detected_capabilities", [])

    if raw_skills is None:
        raw_skills = raw_profile.get("skills", [])
        skill_source = "skills"

    if isinstance(raw_skills, str):
        raw_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]

    # If skills provided as list of dicts, extract common fields
    if isinstance(raw_skills, list) and raw_skills and isinstance(raw_skills[0], dict):
        extracted = []
        for s in raw_skills:
            if not isinstance(s, dict):
                continue
            if s.get("name"):
                extracted.append(s.get("name"))
            elif s.get("label"):
                extracted.append(s.get("label"))
            elif s.get("raw_skill"):
                extracted.append(s.get("raw_skill"))
        raw_skills = extracted

    # Fallback to detected capabilities (prefer tools_detected over capability names)
    if (not raw_skills) and detected_caps and isinstance(detected_caps, list):
        skill_source = "detected_capabilities"
        tools = []
        names = []
        for cap in detected_caps:
            if isinstance(cap, dict):
                tools.extend(cap.get("tools_detected") or [])
                if cap.get("name"):
                    names.append(cap.get("name"))
            else:
                names.append(cap)
        raw_skills = tools or names

    normalized_list = _dedupe_preserve_order([
        normalize_skill(s)
        for s in raw_skills
        if s and isinstance(s, str)
    ])
    # Expand EN→FR aliases for matching with ESCO-labeled offers
    expanded_list = _expand_profile_skills(normalized_list)
    skills = frozenset(expanded_list)

    # ESCO URI collapse for scoring (deterministic, strict)
    raw_skills_uri = raw_profile.get("skills_uri")
    skills_uri_list: List[str] = []
    skills_uri_collapsed_dupes = int(raw_profile.get("skills_uri_collapsed_dupes", 0) or 0)
    skills_unmapped_count = int(raw_profile.get("skills_unmapped_count", 0) or 0)

    if isinstance(raw_skills_uri, list) and raw_skills_uri:
        skills_uri_list = _dedupe_preserve_order([
            str(s).strip()
            for s in raw_skills_uri
            if isinstance(s, str) and str(s).strip()
        ])
    elif map_skill and collapse_to_uris:
        mapped_items: List[Dict[str, str]] = []
        unmapped: List[str] = []
        normalized_set = set(normalized_list)
        for skill in expanded_list:
            if not skill:
                continue
            result = map_skill(skill, enable_fuzzy=False)
            if result:
                mapped_items.append({
                    "surface": skill,
                    "esco_uri": result.get("esco_id", ""),
                    "esco_label": result.get("label") or result.get("canonical") or skill,
                    "source": "alias" if skill not in normalized_set else "direct",
                })
            else:
                if skill in normalized_set:
                    unmapped.append(skill)
        collapsed = collapse_to_uris(mapped_items)
        skills_uri_list = collapsed.get("uris") or []
        skills_uri_collapsed_dupes = int(collapsed.get("collapsed_dupes", 0) or 0)
        skills_unmapped_count = len(_dedupe_preserve_order(unmapped))

    raw_domain_uris = raw_profile.get("domain_uris")
    if isinstance(raw_domain_uris, list) and raw_domain_uris:
        domain_uri_list = _dedupe_preserve_order([
            str(s).strip()
            for s in raw_domain_uris
            if isinstance(s, str) and str(s).strip()
        ])
        if domain_uri_list:
            skills_uri_list = _dedupe_preserve_order(skills_uri_list + domain_uri_list)

    skills_uri = frozenset(skills_uri_list)

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

    capabilities_count = len(detected_caps) if isinstance(detected_caps, list) else 0

    if _debug_matching_enabled():
        logger.info(
            "MATCH_INPUT profile_id=%s skill_source=%s raw_count=%s norm_count=%s uri_count=%s "
            "raw_sample=%s norm_sample=%s",
            profile_id,
            skill_source,
            len(raw_skills) if isinstance(raw_skills, list) else (1 if raw_skills else 0),
            len(skills),
            len(skills_uri),
            _sample_list(raw_skills),
            _sample_list(list(skills)),
        )

    return ExtractedProfile(
        profile_id=str(profile_id),
        skills=skills,
        skills_uri=skills_uri,
        languages=languages,
        education_level=education_level,
        preferred_countries=preferred_countries,
        skill_source=skill_source,
        matching_skills_count=len(skills),
        capabilities_count=capabilities_count,
        skills_uri_count=len(skills_uri),
        skills_uri_collapsed_dupes=skills_uri_collapsed_dupes,
        skills_unmapped_count=skills_unmapped_count,
    )
