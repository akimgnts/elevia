"""
html_renderer.py — Deterministic HTML renderer for CV documents.

v1: single-column ATS renderer (resume_finance.html)
v2: two-page structured renderer (resume_cv_v2.html) fed from CareerProfile v2
    Placeholders: {{full_name}}, {{target_title}}, {{contact_line}}, {{cv_summary}},
    {{experience_items}}, {{project_items}}, {{core_skills}}, {{business_skills}},
    {{tools_stack}}, {{languages_text}}, {{education_items}}, {{certifications_text}},
    {{key_strength_tags}}, {{additional_info}}
    Conditional class: {{*_section_class}} → "" | "hidden"
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import List, Optional

from .schemas import CvDocumentPayload
from .apply_pack_cv_engine import (
    AdaptedExperience,
    _build_skill_link_bullets,
    adapt_career_experiences,
    score_projects,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
_TEMPLATE_MAP = {
    "cv_v1": REPO_ROOT / "templates" / "resume_finance.html",
    "cv_v2": REPO_ROOT / "templates" / "resume_cv_v2.html",
    "cv_v3": REPO_ROOT / "templates" / "resume_manrope.html",
}

# Tool-like terms to route to the tools column in the v2 skills split
_TOOL_TERMS = {
    "excel", "power bi", "powerbi", "sql", "python", "sap", "tableau", "etl",
    "crm", "salesforce", "hubspot", "canva", "wordpress", "r", "matlab",
    "google analytics", "jira", "erp", "looker", "dbt", "airflow", "spark",
    "docker", "git", "github", "gitlab", "figma", "notion", "trello", "asana",
    "qlik", "metabase", "streamlit", "pandas", "scikit-learn", "tensorflow",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(text: Optional[str]) -> str:
    return html.escape(str(text or ""))


def _show(content: str) -> str:
    """Return '' (visible) or 'hidden' based on whether content has real text."""
    return "" if content.strip() else "hidden"


def _extract_name(profile: Optional[dict]) -> str:
    if not profile:
        return "Candidat"
    identity = (profile.get("career_profile") or {}).get("identity") or {}
    if identity.get("full_name"):
        return str(identity["full_name"]).strip()
    for key in ("full_name", "name"):
        value = profile.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    first = profile.get("first_name")
    last = profile.get("last_name")
    joined = " ".join(str(p).strip() for p in (first, last) if isinstance(p, str) and p.strip())
    return joined or "Candidat"


def _extract_contact_line(profile: Optional[dict]) -> str:
    """Build contact line: location · email · phone · linkedin"""
    if not profile:
        return ""
    identity = (profile.get("career_profile") or {}).get("identity") or {}
    parts: List[str] = []
    if identity.get("location"):
        parts.append(str(identity["location"]))
    if identity.get("email"):
        parts.append(str(identity["email"]))
    if identity.get("phone"):
        parts.append(str(identity["phone"]))
    if identity.get("linkedin"):
        parts.append(str(identity["linkedin"]))
    if identity.get("github"):
        parts.append(str(identity["github"]))
    return " · ".join(parts)


def _build_summary(
    payload: CvDocumentPayload,
    profile: Optional[dict],
    offer: Optional[dict],
) -> str:
    """
    Summary priority:
      1. payload.summary (from build_cv_summary — candidate-facing, deterministic)
      2. Terse fallback built from target_title

    The old tier 2 (offer quick_read) is removed: it described the job, not the candidate.
    cv_strategy.positioning is kept only if manually set (rare, explicit override).
    Always 2–4 lines max. Never blank.
    """
    # 0. Manual override: cv_strategy.positioning (only if explicitly populated)
    cv_strategy = (offer or {}).get("cv_strategy") or {}
    if isinstance(cv_strategy, dict) and cv_strategy.get("positioning"):
        return str(cv_strategy["positioning"]).strip()

    # 1. payload summary from build_cv_summary (candidate-facing)
    if payload.summary and len(payload.summary.strip()) > 10:
        return payload.summary.strip()

    # 2. terse fallback
    career = (profile or {}).get("career_profile") or {}
    target = str((offer or {}).get("title") or career.get("base_title") or career.get("target_title") or "").strip()
    return f"{target}." if target else "CV généré automatiquement."


# ---------------------------------------------------------------------------
# v1 rendering helpers (unchanged)
# ---------------------------------------------------------------------------

def _experience_html(payload: CvDocumentPayload) -> str:
    experiences = payload.cv.experiences if payload.cv else []
    if not experiences:
        experiences = [
            {"role": block.title, "company": block.company, "dates": block.dates, "bullets": block.bullets}
            for block in payload.experience_blocks
        ]
    if not experiences:
        return '<div class="job"><div class="job-head"><h3>Expérience à compléter</h3></div></div>'
    blocks: List[str] = []
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


# ---------------------------------------------------------------------------
# v2 rendering helpers
# ---------------------------------------------------------------------------

def _v2_experience_items(
    profile: Optional[dict],
    payload: CvDocumentPayload,
    adapted: Optional[List[AdaptedExperience]] = None,
) -> str:
    """
    Priority:
      1. adapted (pre-scored AdaptedExperience list):
         - "keep": full render (bullets + tools)
         - "compress": minimal render (title + company + dates only)
         - "drop": excluded
      2. career_profile.experiences (raw rich dicts)
      3. payload.experience_blocks (legacy fallback)
    """
    # 1. Adapted experiences (from content adaptation engine)
    if adapted is not None:
        blocks: List[str] = []
        for ae in adapted:
            if ae.decision == "drop":
                continue
            title = _safe(ae.title)
            company = _safe(ae.company)
            location = _safe(ae.location)
            start = ae.start_date.strip()
            end = ae.end_date.strip()
            dates = _safe(f"{start} – {end}".strip(" –") if (start or end) else "")
            company_loc = " · ".join(part for part in (company, location) if part)
            if ae.decision == "keep":
                bullets_html = "".join(f"<li>{_safe(b)}</li>" for b in ae.bullets)
                tools_html = ""
                if ae.tools:
                    tags = "".join(f'<span class="tag">{_safe(t)}</span>' for t in ae.tools[:6])
                    tools_html = f'<div class="tag-list" style="margin-top:5px">{tags}</div>'
                blocks.append(
                    '<div class="job">'
                    '<div class="job-head">'
                    f'<div class="job-left"><div class="job-title">{title}</div>'
                    f'<div class="job-company">{company_loc}</div></div>'
                    f'<div class="job-date">{dates}</div>'
                    '</div>'
                    + (f'<ul>{bullets_html}</ul>' if bullets_html else "")
                    + tools_html
                    + '</div>'
                )
            else:
                # COMPRESS: minimal entry — title + company + dates, no bullets
                blocks.append(
                    '<div class="job" style="margin-bottom:8px">'
                    '<div class="job-head">'
                    f'<div class="job-left"><div class="job-title">{title}</div>'
                    f'<div class="job-company" style="color:#777">{company_loc}</div></div>'
                    f'<div class="job-date">{dates}</div>'
                    '</div>'
                    '</div>'
                )
        if blocks:
            return "".join(blocks)

    # 2. Raw career_profile.experiences
    career = (profile or {}).get("career_profile") or {}
    career_exps = career.get("experiences") or []
    if career_exps:
        blocks = []
        for exp in career_exps:
            if not isinstance(exp, dict):
                continue
            title = _safe(exp.get("title") or "")
            company = _safe(exp.get("company") or "")
            location = _safe(exp.get("location") or "")
            start = str(exp.get("start_date") or "").strip()
            end = str(exp.get("end_date") or "").strip()
            dates = _safe(f"{start} – {end}".strip(" –") if (start or end) else (exp.get("dates") or ""))
            company_loc = " · ".join(part for part in (company, location) if part)

            skill_link_bullets, _, skill_link_tools = _build_skill_link_bullets(exp, [])
            responsibilities = skill_link_bullets or (exp.get("responsibilities") or [])
            achievements = exp.get("achievements") or []
            tools_list = skill_link_tools or (exp.get("tools") or [])

            bullets_html = ""
            for resp in responsibilities[:4]:
                bullets_html += f"<li>{_safe(resp)}</li>"
            for ach in achievements[:2]:
                bullets_html += f"<li>→ {_safe(ach)}</li>"

            tools_html = ""
            if tools_list:
                tags = "".join(f'<span class="tag">{_safe(t)}</span>' for t in tools_list[:6])
                tools_html = f'<div class="tag-list" style="margin-top:5px">{tags}</div>'

            blocks.append(
                '<div class="job">'
                '<div class="job-head">'
                f'<div class="job-left"><div class="job-title">{title}</div>'
                f'<div class="job-company">{company_loc}</div></div>'
                f'<div class="job-date">{dates}</div>'
                '</div>'
                + (f'<ul>{bullets_html}</ul>' if bullets_html else "")
                + tools_html
                + '</div>'
            )
        return "".join(blocks) if blocks else ""

    # 3. Fallback: payload.experience_blocks
    if not payload.experience_blocks:
        return ""
    blocks = []
    for block in payload.experience_blocks:
        bullets_html = "".join(f"<li>{_safe(b)}</li>" for b in block.bullets)
        blocks.append(
            '<div class="job">'
            '<div class="job-head">'
            f'<div class="job-left"><div class="job-title">{_safe(block.title)}</div>'
            f'<div class="job-company">{_safe(block.company)}</div></div>'
            f'<div class="job-date">{_safe(block.dates or "")}</div>'
            '</div>'
            f'<ul>{bullets_html}</ul>'
            '</div>'
        )
    return "".join(blocks)


def _v2_project_items(
    profile: Optional[dict],
    scored: Optional[List[dict]] = None,
) -> str:
    """
    Render career_profile.projects as project blocks.
    Priority: scored (pre-filtered, decision="show") → career_profile.projects (raw).
    """
    # Use scored projects when available (only "show" decisions)
    if scored is not None:
        projects = [p for p in scored if p.get("decision") == "show"]
    else:
        career = (profile or {}).get("career_profile") or {}
        projects = career.get("projects") or []
    if not projects:
        return ""
    blocks: List[str] = []
    for proj in projects:
        if not isinstance(proj, dict):
            continue
        title = _safe(proj.get("title") or "")
        if not title:
            continue
        techs = proj.get("technologies") or []
        url = str(proj.get("url") or "").strip()
        date = str(proj.get("date") or "").strip()
        impact = str(proj.get("impact") or "").strip()
        desc = str(proj.get("description") or "").strip()

        meta_parts: List[str] = []
        if date:
            meta_parts.append(_safe(date))
        if url:
            meta_parts.append(_safe(url))
        meta_line = " · ".join(meta_parts)

        tags_html = ""
        if techs:
            tags = "".join(f'<span class="tag">{_safe(t)}</span>' for t in techs[:8])
            tags_html = f'<div class="tag-list" style="margin-top:4px">{tags}</div>'

        desc_html = ""
        if desc:
            desc_html = f'<div class="project-desc">{_safe(desc)}</div>'
        if impact and impact not in (desc or ""):
            desc_html += f'<div class="project-desc" style="color:#555">→ {_safe(impact)}</div>'

        blocks.append(
            '<div class="project-item">'
            f'<div class="project-title">{title}</div>'
            + (f'<div class="project-meta">{meta_line}</div>' if meta_line else "")
            + desc_html
            + tags_html
            + '</div>'
        )
    return "".join(blocks)


# ESCO occupation descriptions that leak into profile.skills — filter them out
# They start with French infinitive verbs and are typically ≥ 3 words
_ESCO_VERB_RE = re.compile(
    r"^(?:conseiller|gérer|gerer|analyser|coordonner|réaliser|realiser|mettre|assurer|"
    r"participer|contribuer|développer|developper|travailler|rédiger|rediger|"
    r"effectuer|établir|etablir|gérer|gérer|identifier|planifier|préparer|preparer|"
    r"superviser|organiser|accompagner|communiquer|former|évaluer|evaluer)\b",
    re.IGNORECASE,
)


def _is_esco_description(s: str) -> bool:
    """Return True if the string looks like an ESCO occupation task (verb phrase ≥ 3 words)."""
    return bool(_ESCO_VERB_RE.match(s.strip())) and len(s.split()) >= 3


def _extract_skill_link_skills_and_tools(profile: Optional[dict]) -> tuple[List[str], List[str]]:
    career = (profile or {}).get("career_profile") or {}
    skills: List[str] = []
    tools: List[str] = []
    seen_skills: set[str] = set()
    seen_tools: set[str] = set()

    for exp in (career.get("experiences") or []):
        if not isinstance(exp, dict):
            continue
        for raw_link in (exp.get("skill_links") or []):
            if not isinstance(raw_link, dict):
                continue
            raw_skill = raw_link.get("skill")
            if isinstance(raw_skill, dict):
                skill_label = str(raw_skill.get("label") or "").strip()
            else:
                skill_label = str(raw_skill or "").strip()
            skill_key = skill_label.lower()
            if skill_label and skill_key not in seen_skills and not _is_esco_description(skill_label):
                seen_skills.add(skill_key)
                skills.append(skill_label)

            for raw_tool in (raw_link.get("tools") or []):
                if isinstance(raw_tool, dict):
                    tool_label = str(raw_tool.get("label") or "").strip()
                else:
                    tool_label = str(raw_tool or "").strip()
                tool_key = tool_label.lower()
                if tool_label and tool_key not in seen_tools:
                    seen_tools.add(tool_key)
                    tools.append(tool_label)

    return skills, tools


def _v2_split_skills(
    profile: Optional[dict],
    payload: CvDocumentPayload,
) -> tuple[str, str, str]:
    """
    Split skills into (core_skills, business_skills, tools_stack).

    Sources (in priority order):
    1. profile["skills"] — primary raw skills from ESCO pipeline
    2. career_profile.experiences[*].tools — tools found in each experience block
    3. career_profile.experiences[*].skills — short structurer keyword phrases
    4. ATS matched_keywords — offer-matched terms (boost core)

    core_skills     — hard competencies matched by ATS or closest to offer
    business_skills — domain/soft skills not matched as tools
    tools_stack     — tool-like skills from experience tools
    """
    career = (profile or {}).get("career_profile") or {}
    linked_skills, linked_tools = _extract_skill_link_skills_and_tools(profile)

    # Pull from all sources: career.skills + profile.skills (same data) + exp skills
    raw_profile_skills: List[str] = linked_skills + list(
        career.get("skills") or (profile or {}).get("skills") or []
    )
    # Experience-level short keyword phrases from structurer
    exp_skill_phrases: List[str] = []
    for exp in (career.get("experiences") or []):
        if isinstance(exp, dict):
            for s in (exp.get("skills") or []):
                if isinstance(s, str) and s.strip() and len(s.split()) <= 4:
                    exp_skill_phrases.append(s.strip())

    # Merge: profile skills first, then structurer phrases (deduplicated at the end)
    all_candidate_skills: List[str] = raw_profile_skills + exp_skill_phrases

    # Filter ESCO occupation descriptions (verb phrases ≥3 words)
    all_candidate_skills = [s for s in all_candidate_skills if not _is_esco_description(s)]

    # All profile tools (from career_profile.experiences)
    all_tools: List[str] = list(linked_tools)
    for exp in (career.get("experiences") or []):
        if isinstance(exp, dict):
            all_tools.extend(str(t) for t in (exp.get("tools") or []))

    tool_norm = {t.lower().strip() for t in all_tools}
    tool_norm |= _TOOL_TERMS

    # ATS matched keywords — also filtered
    ats_matched = [
        k for k in (list(payload.ats_notes.matched_keywords) if payload.ats_notes else [])
        if not _is_esco_description(k)
    ]
    ats_norm = {s.lower().strip() for s in ats_matched}

    # Tools: from experience tools first (deduped)
    tools: List[str] = list(dict.fromkeys(all_tools))[:12]
    tools_norm = {t.lower().strip() for t in tools}

    # Split skills into core (ATS-matched) vs business (rest)
    core: List[str] = []
    business: List[str] = []
    core_norm: set = set()

    # First pass: ATS-matched skills → core
    for skill in all_candidate_skills:
        sk = skill.strip()
        sk_norm = sk.lower()
        if sk_norm in tools_norm:
            continue
        if sk_norm in tool_norm:
            if sk_norm not in tools_norm and len(tools) < 12:
                tools.append(sk)
                tools_norm.add(sk_norm)
        elif sk_norm in ats_norm and sk_norm not in core_norm:
            core.append(sk)
            core_norm.add(sk_norm)
            if len(core) >= 8:
                break

    # Second pass: remaining skills → business
    seen_all = core_norm | tools_norm | tool_norm
    for skill in all_candidate_skills:
        sk = skill.strip()
        sk_norm = sk.lower()
        if sk_norm in seen_all:
            continue
        business.append(sk)
        seen_all.add(sk_norm)
        if len(business) >= 10:
            break

    # Fallback: if core is empty, promote top non-tool business skills
    if not core and business:
        core = business[:4]
        business = business[4:]

    core_text = ", ".join(_safe(s) for s in core[:8]) if core else "—"
    business_text = ", ".join(_safe(s) for s in business[:10]) if business else "—"
    tools_text = ", ".join(_safe(t) for t in tools[:12]) if tools else "—"

    return core_text, business_text, tools_text


_LANG_LEVEL_RE = re.compile(
    r"\b(natif|native|bilingue|bilingual|courant|fluent|professionnel|professional"
    r"|intermédiaire|intermediate|scolaire|notions?|débutant|beginner|avancé|advanced"
    r"|C[12]|B[12]|A[12])\b",
    re.IGNORECASE,
)
_LANG_NAMES = {
    "anglais": "Anglais", "english": "Anglais",
    "français": "Français", "francais": "Français", "french": "Français",
    "espagnol": "Espagnol", "spanish": "Espagnol",
    "allemand": "Allemand", "german": "Allemand",
    "arabe": "Arabe", "arabic": "Arabe",
    "italien": "Italien", "italian": "Italien",
    "portugais": "Portugais", "portuguese": "Portugais",
    "chinois": "Chinois", "chinese": "Chinois",
}


def _v2_languages_text(profile: Optional[dict]) -> str:
    career = (profile or {}).get("career_profile") or {}
    languages = career.get("languages") or []

    # Fallback: try raw profile.languages (may be a list of strings like "Anglais — C1")
    if not languages:
        raw = (profile or {}).get("languages") or []
        if isinstance(raw, list):
            languages = raw

    if not languages:
        return ""
    parts: List[str] = []
    seen: set = set()
    for lang in languages:
        if isinstance(lang, dict):
            name = str(lang.get("language") or "").strip()
            level = str(lang.get("level") or "").strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            parts.append(f"{_safe(name)} ({_safe(level)})" if level else _safe(name))
        elif isinstance(lang, str):
            text = lang.strip()
            if not text:
                continue
            # Parse "Anglais — C1" or "Anglais C1" patterns
            text_lower = text.lower()
            lang_name = next((v for k, v in _LANG_NAMES.items() if k in text_lower), None)
            if not lang_name:
                lang_name = text.split()[0].title() if text else text
            if lang_name.lower() in seen:
                continue
            seen.add(lang_name.lower())
            level_m = _LANG_LEVEL_RE.search(text)
            level_str = level_m.group(0) if level_m else ""
            parts.append(f"{_safe(lang_name)} ({_safe(level_str)})" if level_str else _safe(lang_name))
    return ", ".join(parts)


def _v2_education_items(profile: Optional[dict], payload: CvDocumentPayload) -> str:
    career = (profile or {}).get("career_profile") or {}
    edu_list = career.get("education") or []

    if edu_list:
        blocks: List[str] = []
        for edu in edu_list:
            if not isinstance(edu, dict):
                continue
            degree = _safe(edu.get("degree") or "")
            institution = _safe(edu.get("institution") or "")
            field = _safe(edu.get("field") or "")
            start = str(edu.get("start_date") or "").strip()
            end = str(edu.get("end_date") or "").strip()
            dates = _safe(f"{start} – {end}".strip(" –") if (start or end) else "")
            location = _safe(edu.get("location") or "")

            title_parts = [p for p in (degree, field) if p]
            title = " — ".join(title_parts) or "Formation"
            meta_parts = [p for p in (institution, location, dates) if p]
            meta = " · ".join(meta_parts)

            blocks.append(
                '<div class="edu-item">'
                f'<div class="edu-title">{title}</div>'
                + (f'<div class="edu-meta">{meta}</div>' if meta else "")
                + '</div>'
            )
        return "".join(blocks)

    # Fallback: from payload.cv.education (string list)
    edu_strings = payload.cv.education if payload.cv else []
    if not edu_strings:
        return ""
    return "".join(
        '<div class="edu-item">'
        f'<div class="edu-title">{_safe(item.split(" — ")[0])}</div>'
        + (f'<div class="edu-meta">{_safe(item.split(" — ", 1)[1])}</div>' if " — " in item else "")
        + '</div>'
        for item in edu_strings
    )


def _v2_certifications_text(profile: Optional[dict]) -> str:
    career = (profile or {}).get("career_profile") or {}
    certs = career.get("certifications") or []
    if not certs:
        return ""
    return ", ".join(_safe(c) for c in certs if c)


def _v3_certifications_items(profile: Optional[dict]) -> str:
    """Render certifications as <li> tags for the .certif-list pill style (v3 template)."""
    career = (profile or {}).get("career_profile") or {}
    certs = career.get("certifications") or []
    if not certs:
        return ""
    return "".join(f"<li>{_safe(c)}</li>" for c in certs if c)


def _v3_education_items(profile: Optional[dict], payload: CvDocumentPayload) -> str:
    """
    Render education as flex rows: left block (title + meta) and right-aligned date.
    Matches the edu-item flex layout in resume_manrope.html.
    """
    career = (profile or {}).get("career_profile") or {}
    edu_list = career.get("education") or []

    if edu_list:
        blocks: List[str] = []
        for edu in edu_list:
            if not isinstance(edu, dict):
                continue
            degree = _safe(edu.get("degree") or "")
            institution = _safe(edu.get("institution") or "")
            field = _safe(edu.get("field") or "")
            start = str(edu.get("start_date") or "").strip()
            end = str(edu.get("end_date") or "").strip()
            dates = _safe(f"{start} – {end}".strip(" –") if (start or end) else "")
            location = _safe(edu.get("location") or "")

            title_parts = [p for p in (degree, field) if p]
            title = " — ".join(title_parts) or "Formation"
            meta_parts = [p for p in (institution, location) if p]
            meta = " · ".join(meta_parts)

            blocks.append(
                '<div class="edu-item">'
                '<div>'
                f'<div class="edu-title">{title}</div>'
                + (f'<div class="edu-meta">{meta}</div>' if meta else "")
                + '</div>'
                + (f'<div class="job-date">{dates}</div>' if dates else "")
                + '</div>'
            )
        return "".join(blocks)

    # Fallback: payload.cv.education (string list)
    edu_strings = payload.cv.education if payload.cv else []
    if not edu_strings:
        return ""
    return "".join(
        '<div class="edu-item">'
        f'<div><div class="edu-title">{_safe(item.split(" — ")[0])}</div>'
        + (f'<div class="edu-meta">{_safe(item.split(" — ", 1)[1])}</div>' if " — " in item else "")
        + '</div></div>'
        for item in edu_strings
    )


def _v2_strength_tags(payload: CvDocumentPayload, profile: Optional[dict]) -> str:
    """Key strengths: top matched keywords + ATS score badge."""
    matched = (payload.ats_notes.matched_keywords if payload.ats_notes else [])[:6]
    if not matched:
        return ""
    return "".join(f'<span class="tag">{_safe(k)}</span>' for k in matched)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_cv_html(
    payload: CvDocumentPayload,
    template_version: str = "cv_v1",
    profile: Optional[dict] = None,
    offer: Optional[dict] = None,
    adapted_experiences: Optional[List[AdaptedExperience]] = None,
    scored_projects: Optional[List[dict]] = None,
) -> str:
    template_path = _TEMPLATE_MAP.get(template_version)
    if not template_path or not template_path.exists():
        raise ValueError(f"Unknown template_version: {template_version}")

    template = template_path.read_text(encoding="utf-8")

    if template_version == "cv_v2":
        return _render_v2(template, payload, profile, offer, adapted_experiences, scored_projects)
    if template_version == "cv_v3":
        return _render_v3(template, payload, profile, offer, adapted_experiences, scored_projects)
    return _render_v1(template, payload, profile, offer)


def _render_v1(
    template: str,
    payload: CvDocumentPayload,
    profile: Optional[dict],
    offer: Optional[dict],
) -> str:
    job_title = payload.cv.title if payload.cv else ((offer or {}).get("title") or "CV")
    candidate_name = _extract_name(profile)
    contact_line = _extract_contact_line(profile)
    company = (offer or {}).get("company") or ""
    country = (offer or {}).get("country") or ""
    suffix = " · ".join(part for part in (company, country) if part)
    company_line = f" — {suffix}" if suffix else ""

    return (
        template
        .replace("{{page_title}}", _safe(job_title))
        .replace("{{job_title}}", _safe(job_title))
        .replace("{{candidate_name}}", _safe(candidate_name))
        .replace("{{contact_line}}", _safe(contact_line))
        .replace("{{company_line}}", _safe(company_line))
        .replace("{{experience_html}}", _experience_html(payload))
        .replace("{{education_html}}", _education_html(payload))
        .replace("{{skills_html}}", _skills_html(payload))
    )


def _render_v3(
    template: str,
    payload: CvDocumentPayload,
    profile: Optional[dict],
    offer: Optional[dict],
    adapted_experiences: Optional[List[AdaptedExperience]] = None,
    scored_projects: Optional[List[dict]] = None,
) -> str:
    """Render using the Manrope layout (resume_manrope.html / cv_v3)."""
    career = (profile or {}).get("career_profile") or {}

    _adapted: Optional[List[AdaptedExperience]] = adapted_experiences
    _scored_projs: Optional[List[dict]] = scored_projects
    if _adapted is None and career and offer:
        _adapted = adapt_career_experiences(profile, offer)
        _scored_projs = score_projects(profile, offer, adapted_exps=_adapted)
    elif _scored_projs is None and _adapted is not None and offer:
        _scored_projs = score_projects(profile, offer, adapted_exps=_adapted)

    full_name = _extract_name(profile)
    target_title = _safe(
        (offer or {}).get("title")
        or career.get("base_title")
        or career.get("target_title")
        or full_name
    )
    contact_line = _safe(_extract_contact_line(profile))
    cv_summary = _safe(_build_summary(payload, profile, offer))

    experience_items = _v2_experience_items(profile, payload, adapted=_adapted)
    project_items = _v2_project_items(profile, scored=_scored_projs)
    core_skills, business_skills, tools_stack = _v2_split_skills(profile, payload)
    languages_text = _v2_languages_text(profile)
    education_items = _v3_education_items(profile, payload)
    certifications_items = _v3_certifications_items(profile)
    strength_tags = _v2_strength_tags(payload, profile)

    experience_section_class = _show(experience_items)
    projects_section_class = _show(project_items)
    education_section_class = _show(education_items)
    certifications_section_class = _show(certifications_items)
    strengths_section_class = _show(strength_tags)
    languages_block_class = _show(languages_text)
    additional_section_class = "hidden"

    return (
        template
        .replace("{{full_name}}", _safe(full_name))
        .replace("{{target_title}}", target_title)
        .replace("{{contact_line}}", contact_line)
        .replace("{{cv_summary}}", cv_summary)
        .replace("{{experience_items}}", experience_items)
        .replace("{{project_items}}", project_items)
        .replace("{{core_skills}}", core_skills)
        .replace("{{business_skills}}", business_skills)
        .replace("{{tools_stack}}", tools_stack)
        .replace("{{languages_text}}", languages_text)
        .replace("{{education_items}}", education_items)
        .replace("{{certifications_items}}", certifications_items)
        .replace("{{key_strength_tags}}", strength_tags)
        .replace("{{additional_info}}", "")
        .replace("{{experience_section_class}}", experience_section_class)
        .replace("{{projects_section_class}}", projects_section_class)
        .replace("{{education_section_class}}", education_section_class)
        .replace("{{certifications_section_class}}", certifications_section_class)
        .replace("{{strengths_section_class}}", strengths_section_class)
        .replace("{{languages_block_class}}", languages_block_class)
        .replace("{{additional_section_class}}", additional_section_class)
    )


def _render_v2(
    template: str,
    payload: CvDocumentPayload,
    profile: Optional[dict],
    offer: Optional[dict],
    adapted_experiences: Optional[List[AdaptedExperience]] = None,
    scored_projects: Optional[List[dict]] = None,
) -> str:
    career = (profile or {}).get("career_profile") or {}

    _adapted: Optional[List[AdaptedExperience]] = adapted_experiences
    _scored_projs: Optional[List[dict]] = scored_projects
    if _adapted is None and career and offer:
        _adapted = adapt_career_experiences(profile, offer)
        _scored_projs = score_projects(profile, offer, adapted_exps=_adapted)
    elif _scored_projs is None and _adapted is not None and offer:
        _scored_projs = score_projects(profile, offer, adapted_exps=_adapted)

    full_name = _extract_name(profile)
    target_title = _safe(
        (offer or {}).get("title")
        or career.get("base_title")
        or career.get("target_title")
        or full_name
    )
    contact_line = _safe(_extract_contact_line(profile))
    cv_summary = _safe(_build_summary(payload, profile, offer))

    experience_items = _v2_experience_items(profile, payload, adapted=_adapted)
    project_items = _v2_project_items(profile, scored=_scored_projs)
    core_skills, business_skills, tools_stack = _v2_split_skills(profile, payload)
    languages_text = _v2_languages_text(profile)
    education_items = _v2_education_items(profile, payload)
    certifications_text = _v2_certifications_text(profile)
    strength_tags = _v2_strength_tags(payload, profile)

    # Conditional section visibility
    experience_section_class = _show(experience_items)
    projects_section_class = _show(project_items)
    education_section_class = _show(education_items)
    certifications_section_class = _show(certifications_text)
    strengths_section_class = _show(strength_tags)
    languages_block_class = _show(languages_text)
    # additional_info: always hidden (no source yet)
    additional_section_class = "hidden"

    return (
        template
        .replace("{{full_name}}", _safe(full_name))
        .replace("{{target_title}}", target_title)
        .replace("{{contact_line}}", contact_line)
        .replace("{{cv_summary}}", cv_summary)
        .replace("{{experience_items}}", experience_items)
        .replace("{{project_items}}", project_items)
        .replace("{{core_skills}}", core_skills)
        .replace("{{business_skills}}", business_skills)
        .replace("{{tools_stack}}", tools_stack)
        .replace("{{languages_text}}", languages_text)
        .replace("{{education_items}}", education_items)
        .replace("{{certifications_text}}", certifications_text)
        .replace("{{key_strength_tags}}", strength_tags)
        .replace("{{additional_info}}", "")
        # Conditional class injections
        .replace("{{experience_section_class}}", experience_section_class)
        .replace("{{projects_section_class}}", projects_section_class)
        .replace("{{education_section_class}}", education_section_class)
        .replace("{{certifications_section_class}}", certifications_section_class)
        .replace("{{strengths_section_class}}", strengths_section_class)
        .replace("{{languages_block_class}}", languages_block_class)
        .replace("{{additional_section_class}}", additional_section_class)
    )
