"""
cover_letter_generator.py — Deterministic cover letter generator (v0).

No LLM. Uses InboxContext for matched skills when available.
"""
from __future__ import annotations

from typing import List, Tuple

from .schemas import CoverLetterBlock, CoverLetterMeta, CoverLetterPayload, LETTER_TEMPLATE_VERSION

_MAX_PREVIEW_CHARS = 1200
_MAX_SKILLS = 3


def _safe_company(company: str | None) -> str:
    return company.strip() if isinstance(company, str) and company.strip() else "votre entreprise"


def _safe_title(title: str | None) -> str:
    return title.strip() if isinstance(title, str) and title.strip() else "ce poste"


def _normalize_skills(skills: List[str]) -> List[str]:
    cleaned = [s.strip() for s in skills if isinstance(s, str) and s.strip()]
    # deterministic order: keep first occurrences, no set iteration
    seen = set()
    ordered: List[str] = []
    for s in cleaned:
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(s.lower())
    return ordered


def _render_preview(title: str, company: str, blocks: List[CoverLetterBlock]) -> str:
    lines: List[str] = []
    lines.append("# Lettre de motivation")
    if title or company:
        parts = [p for p in [title, company] if p]
        lines.append(f"_{' — '.join(parts)}_")
    lines.append("")

    for block in blocks:
        label = block.label
        if label == "hook":
            heading = "Accroche"
        elif label == "match":
            heading = "Adéquation"
        elif label == "value":
            heading = "Valeur"
        else:
            heading = "Conclusion"
        lines.append(f"## {heading}")
        lines.append(block.text)
        lines.append("")

    preview = "\n".join(lines).strip()
    if len(preview) > _MAX_PREVIEW_CHARS:
        return preview[: _MAX_PREVIEW_CHARS - 1].rstrip() + "…"
    return preview


def generate_cover_letter(
    offer_id: str,
    offer_title: str | None,
    offer_company: str | None,
    matched_skills: List[str],
    context_used: bool,
) -> Tuple[CoverLetterPayload, str]:
    """
    Build deterministic cover letter payload + preview_text.
    """
    title = _safe_title(offer_title)
    company = _safe_company(offer_company)

    skills = _normalize_skills(matched_skills)
    skills = skills[:_MAX_SKILLS]

    hook = f"Je vous propose ma candidature pour le poste {title} au sein de {company}."

    if skills:
        skills_str = ", ".join(skills)
        match = f"Les compétences suivantes présentes dans mon profil correspondent aux attentes : {skills_str}."
    else:
        match = "Mon profil couvre des compétences alignées avec les attentes du poste."

    value = (
        "Je privilégie une contribution concrète, structurée et mesurable, "
        "avec une attention particulière à la qualité et à la collaboration."
    )

    closing = "Je serais ravi·e d'échanger sur cette opportunité. Bien cordialement,"

    blocks = [
        CoverLetterBlock(label="hook", text=hook),
        CoverLetterBlock(label="match", text=match),
        CoverLetterBlock(label="value", text=value),
        CoverLetterBlock(label="closing", text=closing),
    ]

    payload = CoverLetterPayload(
        blocks=blocks,
        meta=CoverLetterMeta(
            offer_id=offer_id,
            template_version=LETTER_TEMPLATE_VERSION,
            context_used=context_used,
        ),
    )

    preview = _render_preview(title, company, blocks)
    return payload, preview
