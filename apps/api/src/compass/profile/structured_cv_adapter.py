"""
structured_cv_adapter.py — Convert StructuredCV → ProfileStructuredV1.

Bridges AI extraction to existing profile data format.
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

from compass.contracts import (
    CertificationV1,
    CVQualityV1,
    CVQualityCoverage,
    EducationV1,
    ExperienceV1,
    ProfileStructuredV1,
    ProjectV1,
)

from .structured_cv_schemas import StructuredCV, StructuredExperience

logger = logging.getLogger(__name__)


def structured_to_profile_v1(structured_cv: StructuredCV) -> ProfileStructuredV1:
    """
    Convert StructuredCV (from AI) → ProfileStructuredV1 (existing format).

    Preserves all data, maintains compatibility with existing pipeline.
    """
    # Convert experiences
    experiences: List[ExperienceV1] = []
    for exp in structured_cv.experiences:
        experiences.append(_convert_experience(exp))

    # Convert projects
    projects: List[ProjectV1] = []
    for proj in structured_cv.projects:
        projects.append(ProjectV1(
            title=proj.name,
            description=proj.description or "",
            technologies=proj.tools,
            url=None,
            date=None,
            impact=None,
        ))

    # Convert education
    education: List[EducationV1] = []
    for edu in structured_cv.education:
        education.append(EducationV1(
            institution=edu.institution,
            degree=edu.degree or None,
            field=edu.field or None,
            start_date=_parse_date(edu.dates) if edu.dates else None,
            end_date=None,
            location=edu.location or None,
            cluster_hint=None,
        ))

    # Convert certifications
    certifications: List[CertificationV1] = []
    for cert in structured_cv.certifications:
        certifications.append(CertificationV1(
            name=cert.name,
            bundle_skills=[],
            cluster_hint=None,
            mapped=False,
        ))

    # Aggregate tools across all experiences
    all_tools = set()
    for exp in experiences:
        all_tools.update(exp.tools)
    extracted_tools = sorted(list(all_tools))[:50]

    # Aggregate companies
    extracted_companies = sorted(set(e.company for e in experiences if e.company))

    # Aggregate titles
    extracted_titles = sorted(set(e.title for e in experiences if e.title))

    # Calculate CV quality
    cv_quality = _assess_cv_quality(experiences, education, certifications, extracted_tools)

    return ProfileStructuredV1(
        experiences=experiences,
        education=education,
        certifications=certifications,
        projects=projects,
        extracted_tools=extracted_tools,
        extracted_companies=extracted_companies,
        extracted_titles=extracted_titles,
        inferred_cluster_hints=[],
        cv_quality=cv_quality,
        identity_hint=None,
        extracted_languages=structured_cv.languages,
        extracted_sections=None,
    )


def _convert_experience(exp: StructuredExperience) -> ExperienceV1:
    """Convert StructuredExperience → ExperienceV1."""
    start_date, end_date = _parse_date_range(exp.dates)

    # Calculate duration
    duration_months: Optional[int] = None
    if start_date and end_date:
        try:
            s_parts = start_date.split("/")
            e_parts = end_date.split("/")
            if len(s_parts) == 2 and len(e_parts) == 2:
                s_month = int(s_parts[0])
                s_year = int(s_parts[1])
                e_month = int(e_parts[0])
                e_year = int(e_parts[1])
                duration_months = (e_year - s_year) * 12 + (e_month - s_month)
        except (ValueError, IndexError):
            pass

    return ExperienceV1(
        company=exp.company or None,
        title=exp.title or None,
        start_date=start_date,
        end_date=end_date,
        duration_months=duration_months,
        location=exp.location or None,
        bullets=exp.responsibilities,
        tools=exp.tools,
        skills=exp.skills,
        autonomy_level="MED",  # Default, could enhance with heuristics
        impact_signals=[],
    )


def _parse_date(date_str: str) -> Optional[str]:
    """Extract start date from date range string."""
    if not date_str:
        return None

    # Try to parse "MM/YYYY - MM/YYYY" or similar
    match = re.search(r"(\d{1,2})/(\d{4})", date_str)
    if match:
        month = match.group(1)
        year = match.group(2)
        return f"{month}/{year}"

    # Try just YYYY
    match = re.search(r"\d{4}", date_str)
    if match:
        return match.group(0)

    return None


def _parse_date_range(date_str: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse date range string into (start_date, end_date).

    Handles: "01/2022 - 12/2023", "2022 - 2023", "présent", etc.
    """
    if not date_str:
        return None, None

    date_str = date_str.replace("–", "-").replace("—", "-")

    # Check for "présent" / "present" / "current"
    if any(w in date_str.lower() for w in ("présent", "present", "current", "today")):
        end_date = "présent"
    else:
        end_date = None

    # Extract dates
    matches = re.findall(r"(\d{1,2})?/?(\d{4})", date_str)
    if not matches:
        return None, end_date if end_date else None

    dates = []
    for month, year in matches:
        if month:
            dates.append(f"{month}/{year}")
        else:
            dates.append(year)

    if len(dates) >= 2:
        return dates[0], dates[1] if dates[1] != end_date else None
    elif len(dates) == 1:
        return dates[0], end_date if end_date else None

    return None, end_date if end_date else None


def _assess_cv_quality(
    experiences: List[ExperienceV1],
    education: List[EducationV1],
    certifications: List[CertificationV1],
    extracted_tools: List[str],
) -> CVQualityV1:
    """
    Assess CV quality based on structure and content.

    LOW: no experience, no dates, tools<2, or experiences==0
    MED: partial structure, incomplete dates
    HIGH: sections detected, ≥1 exp with dates, ≥3 tools, ≥1 impact signal
    """
    reasons: List[str] = []
    coverage = CVQualityCoverage(
        experiences_found=len(experiences),
        education_found=len(education),
        certifications_found=len(certifications),
        tools_found=len(extracted_tools),
        date_coverage_ratio=0.0,
    )

    # Check date coverage
    exp_with_dates = sum(1 for e in experiences if e.start_date or e.end_date)
    if experiences:
        coverage.date_coverage_ratio = exp_with_dates / len(experiences)

    # Determine quality level
    if len(experiences) == 0:
        quality_level = "LOW"
        reasons.append("no_experiences")
    elif len(extracted_tools) < 2:
        quality_level = "LOW"
        reasons.append("few_tools")
    elif coverage.date_coverage_ratio < 0.3:
        quality_level = "MED"
        reasons.append("low_date_coverage")
    elif len(extracted_tools) >= 3 and exp_with_dates > 0:
        quality_level = "HIGH"
        reasons.append("structured_with_dates_and_tools")
    else:
        quality_level = "MED"
        reasons.append("partial_structure")

    return CVQualityV1(
        quality_level=quality_level,
        reasons=reasons,
        coverage=coverage,
    )
