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
      1. Header (offer title, company, country)
      2. Profil (summary)
      3. Compétences clés (keywords_injected, already reordered)
      4. Expériences (experience_blocks, bullets + tools)
      5. ATS (score + matched + missing keywords)

    Returns a single string with newlines. Never empty.
    """
    lines: List[str] = []

    # ── 1. Header ─────────────────────────────────────────────────────────────
    if offer_title:
        lines.append(f"# {offer_title}")
    if offer_company or offer_country:
        parts = [p for p in [offer_company, offer_country] if p]
        lines.append(f"_{' — '.join(parts)}_")
    if lines:
        lines.append("")

    # ── 2. Profil ─────────────────────────────────────────────────────────────
    lines.append("## Profil")
    lines.append(payload.summary)
    lines.append("")

    # ── 3. Compétences clés ───────────────────────────────────────────────────
    if payload.keywords_injected:
        lines.append("## Compétences clés")
        lines.append(", ".join(payload.keywords_injected))
        lines.append("")

    # ── 4. Expériences ────────────────────────────────────────────────────────
    if payload.experience_blocks:
        lines.append("## Expériences")
        for block in payload.experience_blocks:
            lines.append(f"### {block.title}")
            lines.append(f"**{block.company}**")
            for bullet in block.bullets:
                lines.append(f"- {bullet}")
            if block.tools:
                lines.append(f"_Outils : {', '.join(block.tools)}_")
            if block.impact:
                lines.append(f"_{block.impact}_")
            lines.append("")

    # ── 5. ATS ────────────────────────────────────────────────────────────────
    lines.append("## ATS")
    lines.append(f"Score estimé : **{payload.ats_notes.ats_score_estimate}%**")
    if payload.ats_notes.matched_keywords:
        lines.append(f"Mots-clés présents : {', '.join(payload.ats_notes.matched_keywords)}")
    if payload.ats_notes.missing_keywords:
        lines.append(f"À renforcer : {', '.join(payload.ats_notes.missing_keywords)}")

    return "\n".join(lines)
