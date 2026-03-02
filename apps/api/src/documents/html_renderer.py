"""
html_renderer.py — Deterministic HTML renderer for CV documents.

Uses a versioned HTML template with placeholders. Escapes all values.
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Iterable, List, Optional

from .schemas import CvDocumentPayload

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_TEMPLATE_MAP = {
    "cv_v1": _TEMPLATE_DIR / "cv_template_v1.html",
}

_MAX_SUMMARY_CHARS = 600
_MAX_SKILLS = 8
_MAX_TOOLS = 10


def _safe(text: Optional[str]) -> str:
    if not text:
        return ""
    return html.escape(str(text))


def _safe_url(url: Optional[str]) -> Optional[str]:
    if not url or not isinstance(url, str):
        return None
    cleaned = url.strip()
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        return cleaned
    return None


def _safe_image_url(url: Optional[str]) -> Optional[str]:
    if not url or not isinstance(url, str):
        return None
    cleaned = url.strip()
    if cleaned.startswith("http://") or cleaned.startswith("https://"):
        return cleaned
    if cleaned.startswith("data:image/"):
        return cleaned
    return None


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _normalize_list(values: Iterable[str]) -> List[str]:
    ordered: List[str] = []
    seen = set()
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered


def _extract_profile_name(profile: Optional[dict]) -> str:
    if not profile:
        return "Candidat"
    for key in ("full_name", "name"):
        value = profile.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    first = profile.get("first_name")
    last = profile.get("last_name")
    if isinstance(first, str) or isinstance(last, str):
        joined = " ".join([str(v).strip() for v in [first, last] if isinstance(v, str) and v.strip()])
        if joined:
            return joined
    return "Candidat"


def _extract_profile_subtitle(profile: Optional[dict], offer: Optional[dict]) -> str:
    if profile:
        for key in ("title", "headline", "role"):
            value = profile.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if offer and isinstance(offer.get("title"), str) and offer.get("title").strip():
        return offer.get("title").strip()
    return "Profil"


def _build_contact_html(profile: Optional[dict]) -> str:
    if not profile:
        return "<li><span style=\"opacity:.6;font-size:.8em;text-transform:uppercase;\">Contact</span><span>Non renseigné</span></li>"

    fields = []
    phone = profile.get("phone") or profile.get("telephone")
    email = profile.get("email")
    linkedin = profile.get("linkedin")
    github = profile.get("github")
    location = profile.get("location")
    if not location:
        city = profile.get("city")
        country = profile.get("country")
        if city or country:
            location = ", ".join([str(v).strip() for v in [city, country] if v])

    if phone:
        fields.append(("Téléphone", _safe(phone)))
    if email:
        email_safe = _safe(email)
        fields.append(("Email", f'<a href="mailto:{email_safe}">{email_safe}</a>'))
    if linkedin:
        linkedin_url = _safe_url(str(linkedin))
        if linkedin_url:
            linkedin_safe = _safe(linkedin_url)
            fields.append(("LinkedIn", f'<a href="{linkedin_safe}">{linkedin_safe}</a>'))
        else:
            fields.append(("LinkedIn", _safe(linkedin)))
    if github:
        github_url = _safe_url(str(github))
        if github_url:
            github_safe = _safe(github_url)
            fields.append(("GitHub", f'<a href="{github_safe}">{github_safe}</a>'))
        else:
            fields.append(("GitHub", _safe(github)))
    if location:
        fields.append(("Localisation", _safe(location)))

    if not fields:
        fields.append(("Contact", "Non renseigné"))

    rows = []
    for label, value in fields:
        rows.append(
            "<li><span style=\"opacity:.6;font-size:.8em;text-transform:uppercase;\">"
            f"{_safe(label)}</span><span>{value}</span></li>"
        )
    return "".join(rows)


def _build_skills_html(skills: List[str], strong: int = 3) -> str:
    if not skills:
        return '<span class="skill-tag">Non renseigné</span>'
    tags = []
    for idx, skill in enumerate(skills):
        label = _safe(skill)
        cls = "skill-tag strong" if idx < strong else "skill-tag"
        tags.append(f'<span class="{cls}">{label}</span>')
    return "".join(tags)


def _build_languages_html(profile: Optional[dict]) -> str:
    if not profile:
        return "<li><strong>Non renseigné</strong></li>"
    langs = profile.get("languages") or profile.get("langues") or []
    items: List[str] = []
    if isinstance(langs, list):
        for entry in langs:
            if isinstance(entry, dict):
                name = entry.get("label") or entry.get("name") or entry.get("code") or "Langue"
                level = entry.get("level") or entry.get("niveau") or ""
                items.append(
                    f"<li><strong>{_safe(name)}</strong> <span style=\"opacity:.8\">{_safe(level)}</span></li>"
                )
            elif isinstance(entry, str):
                items.append(f"<li><strong>{_safe(entry)}</strong></li>")
    elif isinstance(langs, str):
        items.append(f"<li><strong>{_safe(langs)}</strong></li>")

    if not items:
        items.append("<li><strong>Non renseigné</strong></li>")
    return "".join(items)


def _build_experience_html(payload: CvDocumentPayload, offer: Optional[dict]) -> str:
    blocks = payload.experience_blocks
    if not blocks:
        title = offer.get("title") if offer else "Projet / Missions"
        company = offer.get("company") if offer else "—"
        bullet = _truncate(payload.summary or "", 180) or "Expérience à compléter."
        return (
            '<div class="job-block">'
            '<div class="job-top">'
            f'<span class="job-role">{_safe(title)}</span>'
            '<span class="job-date">—</span>'
            '</div>'
            f'<span class="job-company">{_safe(company)}</span>'
            '<div class="job-desc"><ul>'
            f'<li>{_safe(bullet)}</li>'
            '</ul></div>'
            '</div>'
        )

    html_blocks: List[str] = []
    for block in blocks:
        bullets = "".join(f"<li>{_safe(b)}</li>" for b in block.bullets)
        html_blocks.append(
            '<div class="job-block">'
            '<div class="job-top">'
            f'<span class="job-role">{_safe(block.title)}</span>'
            '<span class="job-date">—</span>'
            '</div>'
            f'<span class="job-company">{_safe(block.company)}</span>'
            f'<div class="job-desc"><ul>{bullets}</ul></div>'
            '</div>'
        )
    return "".join(html_blocks)


def _build_education_html(profile: Optional[dict]) -> str:
    if not profile:
        return '<div class="edu-block"><div class="edu-degree">Non renseigné</div></div>'
    edu_list = profile.get("education") or profile.get("education_history") or []
    blocks: List[str] = []
    if isinstance(edu_list, list):
        for entry in edu_list:
            if isinstance(entry, dict):
                degree = entry.get("degree") or entry.get("title") or "Formation"
                school = entry.get("school") or entry.get("institution") or ""
                blocks.append(
                    '<div class="edu-block">'
                    f'<div class="edu-degree">{_safe(degree)}</div>'
                    f'<div class="edu-school">{_safe(school)}</div>'
                    '</div>'
                )
            elif isinstance(entry, str):
                blocks.append(
                    '<div class="edu-block">'
                    f'<div class="edu-degree">{_safe(entry)}</div>'
                    '</div>'
                )
    if not blocks:
        blocks.append('<div class="edu-block"><div class="edu-degree">Non renseigné</div></div>')
    return "".join(blocks)


def _build_certifications_html(profile: Optional[dict]) -> str:
    if not profile:
        return "Non renseigné"
    certs = profile.get("certifications") or profile.get("certificates") or []
    items: List[str] = []
    if isinstance(certs, list):
        for cert in certs:
            if isinstance(cert, str) and cert.strip():
                items.append(f"• {_safe(cert)}")
            elif isinstance(cert, dict):
                label = cert.get("name") or cert.get("title")
                if label:
                    items.append(f"• {_safe(label)}")
    if not items and isinstance(certs, str) and certs.strip():
        items.append(f"• {_safe(certs)}")
    if not items:
        return "Non renseigné"
    return "<br>".join(items)


def _build_photo_html(profile: Optional[dict]) -> str:
    if not profile:
        return ""
    photo = profile.get("photo_url") or profile.get("photo")
    if not isinstance(photo, str) or not photo.strip():
        return ""
    safe_url_raw = _safe_image_url(photo)
    if not safe_url_raw:
        return ""
    safe_url = _safe(safe_url_raw)
    return (
        '<div class="photo-area">'
        f'<img src="{safe_url}" alt="Photo">'
        '</div>'
    )


def render_cv_html(
    payload: CvDocumentPayload,
    template_version: str = "cv_v1",
    profile: Optional[dict] = None,
    offer: Optional[dict] = None,
) -> str:
    """
    Render CV HTML from payload and optional profile/offer info.
    Deterministic. Escapes all user values.
    """
    template_path = _TEMPLATE_MAP.get(template_version)
    if not template_path or not template_path.exists():
        raise ValueError(f"Unknown template_version: {template_version}")

    template = template_path.read_text(encoding="utf-8")

    full_name = _safe(_extract_profile_name(profile))
    subtitle = _safe(_extract_profile_subtitle(profile, offer))

    summary = payload.summary or ""
    summary = _truncate(summary, _MAX_SUMMARY_CHARS)
    summary_html = _safe(summary)

    skills = _normalize_list(payload.keywords_injected)[:_MAX_SKILLS]
    tools = _normalize_list([t for b in payload.experience_blocks for t in b.tools])[:_MAX_TOOLS]

    html_output = template
    html_output = html_output.replace("{{page_title}}", full_name or "CV")
    html_output = html_output.replace("{{photo_html}}", _build_photo_html(profile))
    html_output = html_output.replace("{{contact_html}}", _build_contact_html(profile))
    html_output = html_output.replace("{{signal_skills_html}}", _build_skills_html(skills, strong=min(3, len(skills))))
    html_output = html_output.replace("{{tools_html}}", _build_skills_html(tools, strong=0))
    html_output = html_output.replace("{{languages_html}}", _build_languages_html(profile))
    html_output = html_output.replace("{{full_name}}", full_name)
    html_output = html_output.replace("{{subtitle}}", subtitle)
    html_output = html_output.replace("{{summary_html}}", summary_html)
    html_output = html_output.replace("{{experience_html}}", _build_experience_html(payload, offer))
    html_output = html_output.replace("{{education_html}}", _build_education_html(profile))
    html_output = html_output.replace("{{certifications_html}}", _build_certifications_html(profile))

    return html_output
