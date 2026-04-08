"""
preview_renderer.py — Deterministic markdown renderer for CvDocumentPayload.

Contract:
  - Same payload → same output (no randomness, no set iteration)
  - No LLM. No external calls. Pure string building.
  - Output: UTF-8 markdown string, ATS-safe (plain headers + bullets)
"""

from __future__ import annotations

from typing import List

from .schemas import CvDocumentPayload


def render_preview_markdown(
    payload: CvDocumentPayload,
    offer_title: str = "",
    offer_company: str = "",
    offer_country: str = "",
) -> str:
    """
    Render a CvDocumentPayload as a markdown string.

    Sections (in order):
      1. Header (job title, company, country)
      2. Expérience
      3. Formation
      4. Compétences

    Returns a single string with newlines. Never empty.
    """
    lines: List[str] = []

    # ── 1. Header ─────────────────────────────────────────────────────────────
    header_title = payload.cv.title if payload.cv else offer_title
    if header_title:
        lines.append(f"# {header_title}")
    if offer_company or offer_country:
        parts = [p for p in [offer_company, offer_country] if p]
        lines.append(f"_{' — '.join(parts)}_")
    if lines:
        lines.append("")

    # ── 2. Expériences ────────────────────────────────────────────────────────
    cv_experiences = payload.cv.experiences if payload.cv else []
    lines.append("## Expériences")
    if cv_experiences:
        for block in cv_experiences:
            lines.append(f"### {block.role}")
            company_line = block.company
            if block.dates:
                company_line = f"{company_line} — {block.dates}" if company_line else block.dates
            if company_line:
                lines.append(f"**{company_line}**")
            for bullet in block.bullets:
                lines.append(f"- {bullet}")
            lines.append("")
    elif payload.experience_blocks:
        for block in payload.experience_blocks:
            lines.append(f"### {block.title}")
            company_line = block.company
            if block.dates:
                company_line = f"{company_line} — {block.dates}" if company_line else block.dates
            if company_line:
                lines.append(f"**{company_line}**")
            for bullet in block.bullets:
                lines.append(f"- {bullet}")
            lines.append("")
    else:
        lines.append("- Aucune expérience suffisamment ciblée pour cette offre.")
        lines.append("")

    # ── 3. Formation ──────────────────────────────────────────────────────────
    education_items = payload.cv.education if payload.cv else []
    lines.append("## Formation")
    if education_items:
        for item in education_items:
            lines.append(f"- {item}")
    else:
        lines.append("- Formation à préciser.")
    lines.append("")

    # ── 4. Compétences ────────────────────────────────────────────────────────
    skills = payload.cv.skills if payload.cv else payload.keywords_injected
    lines.append("## Compétences")
    if skills:
        lines.append(", ".join(skills))
    else:
        lines.append("Compétences à confirmer.")
    lines.append("")

    return "\n".join(lines)
