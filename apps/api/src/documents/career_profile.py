"""
career_profile.py — Structured career profile for document generation.

Separate from the matching profile (skills_uri, skills, education level).
Used exclusively for CV and letter generation — never touches score_core.

Separation of concerns:
  matching profile   → skills_uri, languages, education_level (frozen, matching only)
  career profile     → experiences with bullets, achievements, tools (document generation)
  offer strategy     → cv_strategy from justification layer (what to emphasize)

Source: extracted from ProfileStructuredV1 after CV parsing.
Stored as profile["career_profile"] (additive — does not remove existing keys).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class CareerExperience(BaseModel):
    title: str
    company: str
    start_date: Optional[str] = None     # "MM/YYYY" or "YYYY"
    end_date: Optional[str] = None       # "MM/YYYY" | "YYYY" | "présent"
    duration_months: Optional[int] = None
    location: Optional[str] = None
    responsibilities: List[str] = Field(default_factory=list)   # from ExperienceV1.bullets
    achievements: List[str] = Field(default_factory=list)        # from ExperienceV1.impact_signals
    tools: List[str] = Field(default_factory=list)               # from ExperienceV1.tools
    skills: List[str] = Field(default_factory=list)              # from ExperienceV1.skills
    autonomy: Literal["LEAD", "COPILOT", "CONTRIB"] = "COPILOT"


class CareerEducation(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    location: Optional[str] = None


class CareerLanguage(BaseModel):
    language: str
    level: Optional[str] = None   # "Natif", "Courant", "Professionnel", "Scolaire"


class CareerProfile(BaseModel):
    target_title: Optional[str] = None       # most recent experience title
    summary: Optional[str] = None            # generated on demand by LLM/template
    experiences: List[CareerExperience] = Field(default_factory=list)
    education: List[CareerEducation] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    languages: List[CareerLanguage] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    completeness: float = 0.0                # 0.0 – 1.0 heuristic
    source_version: str = "profile_structured_v1"


# ---------------------------------------------------------------------------
# Autonomy mapping
# ---------------------------------------------------------------------------

_AUTONOMY_MAP = {
    "HIGH": "LEAD",
    "MED": "COPILOT",
    "LOW": "CONTRIB",
}


# ---------------------------------------------------------------------------
# Language level heuristics
# ---------------------------------------------------------------------------

_LEVEL_RE = re.compile(
    r"\b(natif|native|bilingue|bilingual|courant|fluent|professionnel|professional"
    r"|intermédiaire|intermediate|scolaire|notions?|débutant|beginner|avancé|advanced"
    r"|C[12]|B[12]|A[12]|DELF|DALF|TOEFL|TOEIC|IELTS)\b",
    re.IGNORECASE,
)

_LEVEL_MAP = {
    "natif": "Natif", "native": "Natif", "bilingue": "Natif", "bilingual": "Natif",
    "courant": "Courant", "fluent": "Courant",
    "professionnel": "Professionnel", "professional": "Professionnel",
    "avancé": "Professionnel", "advanced": "Professionnel",
    "intermédiaire": "Intermédiaire", "intermediate": "Intermédiaire",
    "scolaire": "Scolaire", "notions": "Notions", "notion": "Notions",
    "débutant": "Notions", "beginner": "Notions",
}

_LANG_MAP = {
    "anglais": "Anglais", "english": "Anglais",
    "français": "Français", "francais": "Français", "french": "Français",
    "espagnol": "Espagnol", "spanish": "Espagnol",
    "allemand": "Allemand", "german": "Allemand",
    "italien": "Italien", "italian": "Italien",
    "portugais": "Portugais", "portuguese": "Portugais",
    "chinois": "Chinois", "chinese": "Chinois", "mandarin": "Mandarin",
    "arabe": "Arabe", "arabic": "Arabe",
    "japonais": "Japonais", "japanese": "Japonais",
    "néerlandais": "Néerlandais", "dutch": "Néerlandais",
    "russe": "Russe", "russian": "Russe",
}


def _parse_language_entry(raw: Any) -> Optional[CareerLanguage]:
    """Parse a language entry (string or dict) into CareerLanguage."""
    if isinstance(raw, dict):
        lang = str(raw.get("language") or raw.get("lang") or raw.get("name") or "").strip()
        level = str(raw.get("level") or raw.get("proficiency") or "").strip() or None
        if not lang:
            return None
        canonical = _LANG_MAP.get(lang.lower(), lang.title())
        canonical_level = _LEVEL_MAP.get(level.lower(), level) if level else None
        return CareerLanguage(language=canonical, level=canonical_level)

    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        text_lower = text.lower()
        # Find language name
        lang_name = None
        for key, canonical in _LANG_MAP.items():
            if key in text_lower:
                lang_name = canonical
                break
        if not lang_name:
            lang_name = text.split()[0].title() if text else text

        # Find level
        level_match = _LEVEL_RE.search(text)
        level = None
        if level_match:
            level = _LEVEL_MAP.get(level_match.group(0).lower(), level_match.group(0).title())

        return CareerLanguage(language=lang_name, level=level)

    return None


# ---------------------------------------------------------------------------
# Completeness heuristic
# ---------------------------------------------------------------------------

def _compute_completeness(cp: CareerProfile) -> float:
    score = 0.0
    if cp.experiences:
        score += 0.30
    if any(e.responsibilities for e in cp.experiences):
        score += 0.20
    if any(e.achievements for e in cp.experiences):
        score += 0.10
    if any(e.tools for e in cp.experiences):
        score += 0.10
    if cp.education:
        score += 0.15
    if cp.skills:
        score += 0.10
    if cp.languages:
        score += 0.05
    return round(min(1.0, score), 2)


# ---------------------------------------------------------------------------
# Extractor: ProfileStructuredV1 → CareerProfile
# ---------------------------------------------------------------------------

def from_profile_structured_v1(
    structured: Any,   # compass.contracts.ProfileStructuredV1
    raw_skills: Optional[List[str]] = None,
    raw_languages: Optional[List[Any]] = None,
) -> CareerProfile:
    """
    Build a CareerProfile from an already-computed ProfileStructuredV1.
    Never raises — returns an empty CareerProfile on any error.

    Args:
        structured: ProfileStructuredV1 instance (from compass.profile_structurer)
        raw_skills:   profile["skills"] from the matching profile dict (for top-level skills)
        raw_languages: profile["languages"] from the matching profile dict
    """
    try:
        return _extract(structured, raw_skills or [], raw_languages or [])
    except Exception:
        return CareerProfile()


def _extract(
    structured: Any,
    raw_skills: List[str],
    raw_languages: List[Any],
) -> CareerProfile:
    experiences: List[CareerExperience] = []
    for exp in (getattr(structured, "experiences", None) or []):
        title = str(getattr(exp, "title", None) or "").strip()
        company = str(getattr(exp, "company", None) or "").strip()
        if not title and not company:
            continue  # skip empty blocks

        responsibilities = [
            b for b in (getattr(exp, "bullets", None) or [])
            if isinstance(b, str) and b.strip()
        ]
        achievements = [
            s for s in (getattr(exp, "impact_signals", None) or [])
            if isinstance(s, str) and s.strip()
        ]
        tools = [
            t for t in (getattr(exp, "tools", None) or [])
            if isinstance(t, str) and t.strip()
        ]
        skills = [
            s for s in (getattr(exp, "skills", None) or [])
            if isinstance(s, str) and s.strip()
        ]
        autonomy_raw = str(getattr(exp, "autonomy_level", "MED") or "MED").upper()
        autonomy = _AUTONOMY_MAP.get(autonomy_raw, "COPILOT")

        experiences.append(CareerExperience(
            title=title or "Expérience",
            company=company,
            start_date=str(getattr(exp, "start_date", None) or "").strip() or None,
            end_date=str(getattr(exp, "end_date", None) or "").strip() or None,
            duration_months=getattr(exp, "duration_months", None),
            responsibilities=responsibilities[:8],
            achievements=achievements[:5],
            tools=tools[:12],
            skills=skills[:8],
            autonomy=autonomy,
        ))

    education: List[CareerEducation] = []
    for edu in (getattr(structured, "education", None) or []):
        institution = str(getattr(edu, "institution", None) or "").strip()
        degree = str(getattr(edu, "degree", None) or "").strip()
        if not institution and not degree:
            continue
        education.append(CareerEducation(
            institution=institution or None,
            degree=degree or None,
            field=str(getattr(edu, "field", None) or "").strip() or None,
            start_date=str(getattr(edu, "start_date", None) or "").strip() or None,
            end_date=str(getattr(edu, "end_date", None) or "").strip() or None,
            location=str(getattr(edu, "location", None) or "").strip() or None,
        ))

    certifications = [
        str(cert.name).strip()
        for cert in (getattr(structured, "certifications", None) or [])
        if hasattr(cert, "name") and str(cert.name).strip()
    ]

    languages: List[CareerLanguage] = []
    seen_langs: set = set()
    for raw_lang in raw_languages:
        parsed = _parse_language_entry(raw_lang)
        if parsed and parsed.language.lower() not in seen_langs:
            languages.append(parsed)
            seen_langs.add(parsed.language.lower())

    target_title = experiences[0].title if experiences else None

    cp = CareerProfile(
        target_title=target_title,
        experiences=experiences,
        education=education,
        certifications=certifications,
        languages=languages,
        skills=[str(s).strip() for s in raw_skills if s and str(s).strip()][:20],
        source_version="profile_structured_v1",
    )
    cp.completeness = _compute_completeness(cp)
    return cp


# ---------------------------------------------------------------------------
# Helpers: serialize career_profile experiences to a form compatible with
# the existing apply_pack_cv_engine._normalize_experience() reader.
# The engine already reads: bullets, highlights, tasks, missions, achievements.
# ---------------------------------------------------------------------------

def to_experience_dicts(career_profile: CareerProfile) -> List[Dict[str, Any]]:
    """
    Convert CareerProfile.experiences to the dict format expected by
    apply_pack_cv_engine._normalize_experience().

    The engine reads `bullets` → we map `responsibilities` → `bullets`.
    The engine reads `achievements` → we keep `achievements`.
    """
    result = []
    for exp in career_profile.experiences:
        start = exp.start_date or ""
        end = exp.end_date or ""
        dates = f"{start} - {end}".strip(" -") if (start or end) else ""
        result.append({
            "title": exp.title,
            "company": exp.company,
            "dates": dates,
            "bullets": exp.responsibilities,           # mapped for engine compatibility
            "achievements": exp.achievements,
            "tools": exp.tools,
            "duration_months": exp.duration_months,
            "autonomy": exp.autonomy,
        })
    return result
