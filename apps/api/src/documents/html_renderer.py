"""
html_renderer.py — Deterministic HTML renderer for CV documents.

Single-column ATS-friendly renderer used by Apply Pack.
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Iterable, Optional

from .schemas import CvDocumentPayload

REPO_ROOT = Path(__file__).resolve().parents[4]
_TEMPLATE_MAP = {
    "cv_v1": REPO_ROOT / "templates" / "resume_finance.html",
}


def _safe(text: Optional[str]) -> str:
    return html.escape(str(text or ""))


def _extract_name(profile: Optional[dict]) -> str:
    if not profile:
        return "Candidat"
    for key in ("full_name", "name"):
        value = profile.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    first = profile.get("first_name")
    last = profile.get("last_name")
    joined = " ".join(str(part).strip() for part in (first, last) if isinstance(part, str) and part.strip())
    return joined or "Candidat"


def _experience_html(payload: CvDocumentPayload) -> str:
    experiences = payload.cv.experiences if payload.cv else []
    if not experiences:
        experiences = [
            {
                "role": block.title,
                "company": block.company,
                "dates": block.dates,
                "bullets": block.bullets,
            }
            for block in payload.experience_blocks
        ]
    if not experiences:
        return '<div class="job"><div class="job-head"><h3>Expérience à compléter</h3></div></div>'
    blocks: list[str] = []
    for exp in experiences:
        role = exp.role if hasattr(exp, "role") else exp.get("role")
        company = exp.company if hasattr(exp, "company") else exp.get("company")
        dates_value = exp.dates if hasattr(exp, "dates") else exp.get("dates")
        bullets_list = exp.bullets if hasattr(exp, "bullets") else exp.get("bullets", [])
        bullets = "".join(f"<li>{_safe(bullet)}</li>" for bullet in bullets_list)
        dates = _safe(dates_value) if dates_value else ""
        blocks.append(
            '<div class="job">'
            '<div class="job-head">'
            f'<h3>{_safe(role)}</h3>'
            f'<div class="dates">{dates}</div>'
            '</div>'
            f'<div class="company">{_safe(company)}</div>'
            f'<ul>{bullets}</ul>'
            '</div>'
        )
    return "".join(blocks)


def _education_html(payload: CvDocumentPayload) -> str:
    education = payload.cv.education if payload.cv else []
    if not education:
        return '<div class="edu"><div class="edu-title">Formation à préciser</div></div>'
    return "".join(
        '<div class="edu">'
        f'<div class="edu-title">{_safe(item.split(" — ")[0])}</div>'
        + (f'<div class="edu-sub">{_safe(item.split(" — ", 1)[1])}</div>' if " — " in item else "")
        + '</div>'
        for item in education
    )


def _skills_html(payload: CvDocumentPayload) -> str:
    skills = payload.cv.skills if payload.cv else payload.keywords_injected
    if not skills:
        return '<span class="skill">Compétences à confirmer</span>'
    return "".join(f'<span class="skill">{_safe(skill)}</span>' for skill in skills)


def render_cv_html(
    payload: CvDocumentPayload,
    template_version: str = "cv_v1",
    profile: Optional[dict] = None,
    offer: Optional[dict] = None,
) -> str:
    template_path = _TEMPLATE_MAP.get(template_version)
    if not template_path or not template_path.exists():
        raise ValueError(f"Unknown template_version: {template_version}")

    template = template_path.read_text(encoding="utf-8")
    job_title = payload.cv.title if payload.cv else (offer.get("title") if offer else "CV")
    candidate_name = _extract_name(profile)
    company = offer.get("company") if offer else ""
    country = offer.get("country") if offer else ""
    suffix = " · ".join(part for part in (company, country) if part)
    company_line = f" — {suffix}" if suffix else ""

    return (
        template
        .replace("{{page_title}}", _safe(job_title))
        .replace("{{job_title}}", _safe(job_title))
        .replace("{{candidate_name}}", _safe(candidate_name))
        .replace("{{company_line}}", _safe(company_line))
        .replace("{{experience_html}}", _experience_html(payload))
        .replace("{{education_html}}", _education_html(payload))
        .replace("{{skills_html}}", _skills_html(payload))
    )
