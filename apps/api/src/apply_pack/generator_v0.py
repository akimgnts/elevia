"""
generator_v0.py — Deterministic baseline Apply Pack generator.

Produces CV + cover letter in markdown from profile + offer data.
No LLM required. Same inputs → same outputs.

Rules:
- Never invent PII: uses "Candidat(e)" placeholders when name is absent.
- matched_core displayed first in CV (max 12 shown).
- missing_core shown as learning / dev axis (max 8 shown).
- Skill lists capped at 25.
- Sections are fixed — no creative variation.
"""
from __future__ import annotations

import textwrap
from datetime import datetime, timezone
from typing import List, Dict, Any

_MAX_MATCHED = 12
_MAX_MISSING = 8
_MAX_SKILLS = 25


def _skill_list(skills: List[str], limit: int) -> str:
    """Return a markdown bullet list of skills, capped at limit."""
    shown = skills[:limit]
    if not shown:
        return "- (aucune compétence identifiée)\n"
    return "".join(f"- {s}\n" for s in shown)


def build_cv_markdown(
    profile: Dict[str, Any],
    offer: Dict[str, Any],
    matched: List[str],
    missing: List[str],
) -> str:
    """
    Build a plain-text CV in markdown tailored to the offer.

    Args:
        profile: profile dict with at least 'skills'.
        offer:   offer dict with at least 'title' and optionally 'company'.
        matched: intersection of profile skills and offer skills.
        missing: offer skills not in profile.

    Returns: markdown string.
    """
    candidate_name = profile.get("name") or profile.get("candidate_name") or "Candidat(e)"
    offer_title = offer.get("title") or "Poste non spécifié"
    company = offer.get("company") or "Entreprise non spécifiée"

    all_skills: List[str] = list(profile.get("skills") or profile.get("matching_skills") or [])
    shown_matched = matched[:_MAX_MATCHED]
    # Other skills = all skills minus matched (to avoid repetition)
    matched_set = set(shown_matched)
    other_skills = [s for s in all_skills if s not in matched_set][:_MAX_SKILLS]

    lines: List[str] = []

    lines.append(f"# CV — {candidate_name}")
    lines.append(f"**Poste visé :** {offer_title} — {company}\n")

    lines.append("---\n")

    lines.append("## Compétences clés pour le poste")
    if shown_matched:
        lines.append(_skill_list(shown_matched, _MAX_MATCHED))
    else:
        lines.append("- (aucune correspondance directe détectée — voir compétences générales)\n")

    if other_skills:
        lines.append("## Outils & technologies")
        lines.append(_skill_list(other_skills, _MAX_SKILLS))

    if missing[:_MAX_MISSING]:
        lines.append("## Axes de développement (compétences de l'offre à renforcer)")
        lines.append(_skill_list(missing, _MAX_MISSING))

    lines.append("## Résumé de candidature")
    summary_bullets = []
    if shown_matched:
        top3 = ", ".join(shown_matched[:3])
        summary_bullets.append(
            f"Maîtrise confirmée de {top3} — compétences directement requises pour ce poste."
        )
    else:
        summary_bullets.append(
            f"Profil orienté {offer_title}, avec une forte capacité d'adaptation."
        )
    summary_bullets.append(
        f"Intérêt pour le poste {offer_title} chez {company} — motivé(e) à contribuer dès la prise de poste."
    )
    if missing[:2]:
        axis = " et ".join(missing[:2])
        summary_bullets.append(
            f"En cours de montée en compétences sur {axis} — axe de développement identifié."
        )
    for b in summary_bullets:
        lines.append(f"- {b}")
    lines.append("")

    lines.append("---")
    lines.append(
        "_CV généré automatiquement par Elevia Compass (mode baseline). "
        "À compléter avec vos informations personnelles._"
    )

    return "\n".join(lines)


def build_letter_markdown(
    profile: Dict[str, Any],
    offer: Dict[str, Any],
    matched: List[str],
    missing: List[str],
) -> str:
    """
    Build a plain-text cover letter in markdown.

    Args:
        profile: profile dict with at least 'skills'.
        offer:   offer dict with at least 'title' and optionally 'company'.
        matched: intersection of profile skills and offer skills.
        missing: offer skills not in profile.

    Returns: markdown string.
    """
    candidate_name = profile.get("name") or profile.get("candidate_name") or "Candidat(e)"
    offer_title = offer.get("title") or "Poste non spécifié"
    company = offer.get("company") or "votre entreprise"
    country = offer.get("country") or ""

    top_matched = matched[:5]
    top_missing = missing[:3]

    location_str = f" ({country})" if country else ""
    role_str = f"**{offer_title}**{location_str}"

    lines: List[str] = []

    lines.append(f"# Lettre de motivation — {candidate_name}")
    lines.append(f"**Candidature :** {offer_title} — {company}\n")
    lines.append("---\n")

    # Intro
    lines.append("## Objet de la candidature\n")
    lines.append(
        f"Je me permets de vous adresser ma candidature pour le poste de {role_str} "
        f"au sein de {company}. "
        f"Votre annonce a retenu toute mon attention car elle correspond à mes aspirations "
        f"professionnelles et à mon profil de compétences."
    )
    lines.append("")

    # Body — matched skills
    lines.append("## Mon profil au regard de vos besoins\n")
    if top_matched:
        skills_str = ", ".join(top_matched)
        lines.append(
            f"Au cours de mes expériences, j'ai développé des compétences solides notamment en "
            f"{skills_str}. "
            f"Ces compétences correspondent directement aux exigences du poste {offer_title} "
            f"et me permettraient d'être opérationnel(le) rapidement."
        )
    else:
        lines.append(
            f"Mon parcours m'a permis de développer des compétences polyvalentes, "
            f"que je souhaite mettre au service de {company} dans le cadre de ce poste."
        )
    lines.append("")

    # Body — development
    if top_missing:
        axis_str = " et ".join(top_missing[:2])
        lines.append(
            f"Je suis également conscient(e) des axes de progression liés à ce poste, "
            f"notamment en {axis_str}. "
            f"Je suis motivé(e) à approfondir ces domaines afin de répondre pleinement aux attentes du poste."
        )
        lines.append("")

    # Closing
    lines.append("## Disponibilité et contact\n")
    lines.append(
        f"Disponible rapidement, je serais ravi(e) d'échanger avec vous sur ma candidature "
        f"pour le poste {offer_title}. "
        f"Je reste à votre disposition pour tout entretien à votre convenance."
    )
    lines.append("")
    lines.append(f"Dans l'attente de votre retour, veuillez agréer, Madame, Monsieur, l'expression de mes cordiales salutations.")
    lines.append("")
    lines.append(f"*{candidate_name}*")

    lines.append("\n---")
    lines.append(
        "_Lettre générée automatiquement par Elevia Compass (mode baseline). "
        "À personnaliser avec vos expériences et coordonnées._"
    )

    return "\n".join(lines)


def compute_matched_missing(
    profile_skills: List[str],
    offer_skills: List[str],
) -> tuple[List[str], List[str]]:
    """
    Compute matched and missing skills from profile and offer skill lists.
    Returns (matched, missing) — both sorted for determinism.
    """
    profile_set = {s.lower() for s in profile_skills}
    offer_set = {s.lower() for s in offer_skills}

    matched = sorted(profile_set & offer_set)
    missing = sorted(offer_set - profile_set)
    return matched, missing
