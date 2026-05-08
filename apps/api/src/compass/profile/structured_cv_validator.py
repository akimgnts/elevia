"""
structured_cv_validator.py — Validation rules for structured CV extraction.

Checks:
1. projects ≠ experiences
2. no contamination of responsibilities
3. skills properly contextualized
4. no invention
"""
from __future__ import annotations

import logging
import re
from typing import List, Set

from .structured_cv_schemas import StructuredCV, StructuredExperience

logger = logging.getLogger(__name__)


def validate_structured_cv(cv: StructuredCV) -> tuple[bool, List[str]]:
    """
    Validate structured CV for contamination and quality.

    Returns:
        (is_valid, warnings)
        is_valid=False means critical issue (use fallback parser).
    """
    warnings: List[str] = []

    # Check 1: Projects separation
    if not _validate_projects_separation(cv, warnings):
        logger.warning("[structured-cv-validator] Projects contamination detected")
        return False, warnings

    # Check 2: Experience contamination
    if not _validate_experience_contamination(cv, warnings):
        logger.warning("[structured-cv-validator] Experience contamination detected")
        return False, warnings

    # Check 3: Skills contextualization (warning only)
    _validate_skills_context(cv, warnings)

    return True, warnings


def _validate_projects_separation(cv: StructuredCV, warnings: List[str]) -> bool:
    """Check projects are truly separate from experiences."""
    if not cv.projects:
        return True

    project_names_lower = {p.name.lower() for p in cv.projects if p.name}
    if not project_names_lower:
        return True

    for exp in cv.experiences:
        if not exp.responsibilities:
            continue

        for resp in exp.responsibilities:
            resp_lower = resp.lower()

            # Check if project name appears in responsibility
            for proj_name in project_names_lower:
                if len(proj_name) > 3 and proj_name in resp_lower:
                    warnings.append(
                        f"Project '{proj_name}' found in experience responsibilities: "
                        f"possible contamination"
                    )
                    return False

    return True


def _validate_experience_contamination(cv: StructuredCV, warnings: List[str]) -> bool:
    """Check responsibilities don't contain other job titles, companies, or sections."""
    if not cv.experiences:
        return True

    # Collect all company names and titles
    all_companies = {e.company.lower() for e in cv.experiences if e.company}
    all_titles = {e.title.lower() for e in cv.experiences if e.title}

    # Patterns for section headers
    section_pattern = re.compile(
        r"\b(experience|formation|education|certification|projet|projet personnel|"
        r"skill|competence|langue|language)\b",
        re.IGNORECASE
    )

    for i, exp in enumerate(cv.experiences):
        if not exp.responsibilities:
            continue

        for j, resp in enumerate(exp.responsibilities):
            resp_lower = resp.lower()

            # Check for other company names
            for company in all_companies:
                if company != exp.company.lower() and len(company) > 2:
                    if company in resp_lower and _is_suspicious_context(resp_lower, company):
                        warnings.append(
                            f"Experience {i}: Company '{company}' found in responsibility {j} "
                            f"(possible contamination)"
                        )
                        return False

            # Check for section headers
            if section_pattern.search(resp):
                warnings.append(
                    f"Experience {i}: Section header pattern found in responsibility {j} "
                    f"(possible contamination)"
                )
                return False

            # Check for job title-like patterns (title + dates/company)
            if _looks_like_job_title(resp):
                warnings.append(
                    f"Experience {i}: Job title pattern in responsibility {j} "
                    f"(possible contamination)"
                )
                return False

    return True


def _validate_skills_context(cv: StructuredCV, warnings: List[str]) -> None:
    """Check if skills are properly contextualized (warning only)."""
    if not cv.experiences:
        return

    exp_skills: Set[str] = set()
    for exp in cv.experiences:
        exp_skills.update(s.lower() for s in exp.skills)

    global_skills = {s.lower() for s in cv.global_skills}

    # Warn if same skill appears in both contextual and global
    overlap = exp_skills & global_skills
    if overlap and len(overlap) <= 3:
        warnings.append(
            f"Skills appear in both experiences and global: {', '.join(sorted(overlap))} "
            f"(check contextualization)"
        )


def _is_suspicious_context(text_lower: str, keyword: str) -> bool:
    """
    Check if keyword appears in suspicious context (i.e., looks like a job listing).
    Returns True if keyword seems to be a company name in a new job.
    """
    # Look for patterns like "Company — Title" or "Company: Title" or "Company | Date"
    patterns = [
        rf"{re.escape(keyword)}\s*(?:—|–|-|:|\|)",
        rf"{re.escape(keyword)}\s+\d{{4}}",
        rf"{re.escape(keyword)}\s+(?:2\d{{3}}|janvier|février|mars|april|mai|juin|juillet)",
    ]

    return any(re.search(p, text_lower) for p in patterns)


def _looks_like_job_title(text: str) -> bool:
    """
    Check if text looks like a job title line (title — company — dates).
    Patterns like: "Data Engineer — Acme Corp — 2022-2023"

    Note: Uses word boundaries to avoid false positives on words like
    "marketing" (which contains "mar"). Checks for:
    1. Multiple dashes (title — company — dates)
    2. Dash + year (title – YYYY)
    3. Month + year (Title, March 2022 or Title, Feb 2020)
    """
    # Look for multiple em-dashes or em-dash with year
    if text.count("—") >= 2 or (text.count("—") >= 1 and re.search(r"\d{4}", text)):
        return True

    # Pattern: Dash (en-dash or hyphen) + year, e.g., "DevOps Engineer – 2023"
    if re.search(r"[A-Z][a-z\s]+(?:–|-)\s*\d{4}", text):
        return True

    # Pattern: Title, Month/Year, Company
    # Word boundaries prevent "mar" in "marketing" from matching month names
    if re.search(
        r"^[A-Z][a-z\s]+(?:—|–|,)\s*"
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|"
        r"january|february|march|april|may|june|july|august|september|october|november|december|"
        r"janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\b"
        r"(?:\s+\d{4}|,\s*\d{4}|\.)",
        text,
        re.IGNORECASE
    ):
        return True

    return False
