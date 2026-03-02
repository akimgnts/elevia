"""
profile_summary_builder.py — Build ProfileSummaryV1 from ProfileStructuredV1.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Optional

from compass.contracts import ProfileStructuredV1, SkillRef
from api.schemas.profile_summary import ProfileSummaryExperience, ProfileSummaryV1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_tokens(values: Iterable[str]) -> List[str]:
    cleaned: List[str] = []
    for value in values:
        if not value:
            continue
        token = str(value).strip()
        if not token:
            continue
        cleaned.append(token)
    return cleaned


def _top_k_by_frequency(values: Iterable[str], limit: int) -> List[str]:
    counts: dict[str, int] = {}
    order: List[str] = []
    for value in values:
        if value not in counts:
            counts[value] = 0
            order.append(value)
        counts[value] += 1
    index = {v: i for i, v in enumerate(order)}
    ranked = sorted(order, key=lambda v: (-counts[v], index[v]))
    return ranked[:limit]


def _format_experience_dates(start: Optional[str], end: Optional[str]) -> Optional[str]:
    if start and end:
        return f"{start} – {end}"
    if start:
        return start
    if end:
        return end
    return None


def _format_education_line(edu) -> Optional[str]:
    parts: List[str] = []
    if getattr(edu, "degree", None):
        parts.append(str(edu.degree))
    if getattr(edu, "field", None):
        parts.append(str(edu.field))
    line = " — ".join(parts).strip()
    if getattr(edu, "institution", None):
        inst = str(edu.institution).strip()
        if inst:
            line = f"{line} · {inst}" if line else inst
    return line or None


def build_profile_summary(
    structured: ProfileStructuredV1,
    *,
    extra_skills: Optional[Iterable[str]] = None,
) -> ProfileSummaryV1:
    skills_pool: List[str] = []
    if extra_skills:
        skills_pool.extend(_normalize_tokens(extra_skills))

    for exp in structured.experiences or []:
        if exp.skills:
            skills_pool.extend(_normalize_tokens(exp.skills))

    top_skills = [
        SkillRef(uri=None, label=label)
        for label in _top_k_by_frequency(skills_pool, 10)
    ]

    tools = _normalize_tokens(structured.extracted_tools or [])[:10]
    certifications = _normalize_tokens([c.name for c in structured.certifications or []])[:5]

    education_lines: List[str] = []
    for edu in structured.education or []:
        line = _format_education_line(edu)
        if line:
            education_lines.append(line)
        if len(education_lines) >= 2:
            break

    experiences: List[ProfileSummaryExperience] = []
    for exp in structured.experiences or []:
        impact = None
        if exp.impact_signals:
            impact = exp.impact_signals[0]
        elif exp.bullets:
            impact = exp.bullets[0]
        experiences.append(
            ProfileSummaryExperience(
                title=exp.title,
                company=exp.company,
                dates=_format_experience_dates(exp.start_date, exp.end_date),
                impact_one_liner=impact,
            )
        )
        if len(experiences) >= 2:
            break

    cluster_hints = _normalize_tokens(structured.inferred_cluster_hints or [])[:2]

    return ProfileSummaryV1(
        cv_quality_level=structured.cv_quality.quality_level,
        cv_quality_reasons=structured.cv_quality.reasons or [],
        top_skills=top_skills,
        tools=tools,
        certifications=certifications,
        education=education_lines,
        experiences=experiences,
        cluster_hints=cluster_hints,
        last_updated=_now_iso(),
    )
