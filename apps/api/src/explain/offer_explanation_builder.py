"""offer_explanation_builder — Transform ExplainBlock into user-friendly OfferExplanation.

No scoring changes. No matching changes. Pure formatting layer.
Deterministic only (no LLM, no fuzzy logic).
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
from api.schemas.inbox import ExplainBlock, SkillExplainItem, OfferExplanation


def _get_core_skills_summary(
    matched_core: List[SkillExplainItem],
    missing_core: List[SkillExplainItem],
    skill_overlap: int,
) -> str:
    """Generate summary reason based on core skills (French).

    Example:
      "Vous avez 5 sur 8 compétences clés (62%). Bon match."
      "Vous avez 2 sur 6 compétences clés (33%). À développer."
    """
    if not matched_core and not missing_core:
        return "Correspond au domaine et à votre expérience."

    total_core = len(matched_core) + len(missing_core)
    if total_core == 0:
        return "Correspond à votre profil global."

    matched_count = len(matched_core)
    pct = int((matched_count / total_core) * 100) if total_core > 0 else 0

    if pct >= 80:
        strength = "excellent match"
    elif pct >= 60:
        strength = "bon match"
    elif pct >= 40:
        strength = "match moyen"
    else:
        strength = "potentiel intéressant"

    core_list = ", ".join(s.label for s in matched_core[:3])
    if len(matched_core) > 3:
        core_list += f", +{len(matched_core) - 3} autres"

    return f"Vous avez {matched_count} sur {total_core} compétences clés ({pct}%) — {strength}. Matched: {core_list}."


def _extract_strengths(matched_core: List[SkillExplainItem], matched_secondary: List[SkillExplainItem]) -> List[str]:
    """Extract top 3-5 matching strengths (French).

    Examples:
      "Maîtrise Python"
      "Expérience SQL/analytics"
      "3+ ans d'ingénierie données"
    """
    strengths = []

    # Top 3 core matched skills
    if matched_core:
        top_core = matched_core[:3]
        for skill in top_core:
            # Convert skill label to strength statement
            label = skill.label.lower()
            if "python" in label:
                strengths.append("Maîtrise Python")
            elif "sql" in label or "database" in label:
                strengths.append("Expérience SQL & bases de données")
            elif "java" in label:
                strengths.append("Expertise Java/POO")
            elif "react" in label or "javascript" in label:
                strengths.append("Expérience frameworks frontend")
            elif "excel" in label:
                strengths.append("Maîtrise Excel")
            elif "analytics" in label or "data" in label:
                strengths.append("Compétences en analyse de données")
            elif "project" in label:
                strengths.append("Capacité de gestion de projet")
            elif "sales" in label or "crm" in label:
                strengths.append("Expérience ventes & CRM")
            elif "sap" in label or "erp" in label:
                strengths.append("Connaissance des systèmes entreprise")
            else:
                # Fallback: use skill name directly
                strengths.append(f"Compétence {label}")

    # Add secondary if short on strengths
    if len(strengths) < 4 and matched_secondary:
        for skill in matched_secondary[:2]:
            label = skill.label.lower()
            strengths.append(f"Connaissance {label}")

    # Limit to top 5
    return strengths[:5]


def _extract_gaps(missing_core: List[SkillExplainItem], missing_secondary: List[SkillExplainItem]) -> List[str]:
    """Extract missing skills as gaps (French).

    Priority:
      1. Missing CORE skills (required for role)
      2. Missing SECONDARY skills (nice-to-haves)
    """
    gaps = []

    # Core missing (MUST address)
    if missing_core:
        for skill in missing_core[:4]:
            label = skill.label.lower()
            gaps.append(f"Maîtriser {label}")

    # Secondary missing (nice-to-have) — only if room
    if len(gaps) < 3 and missing_secondary:
        for skill in missing_secondary[:2]:
            label = skill.label.lower()
            gaps.append(f"Bénéficierait de {label}")

    return gaps[:4]


def _extract_blockers(missing_core: List[SkillExplainItem]) -> List[str]:
    """Extract critical missing CORE skills as blockers (French).

    These are "must-haves" that might disqualify candidate.
    """
    blockers = []

    # Only flag if >3 core missing (suggests not ready yet)
    if len(missing_core) >= 3:
        blocker_msg = f"Manquent {len(missing_core)} compétences clés: {', '.join(s.label for s in missing_core[:3])}"
        blockers.append(blocker_msg)

    return blockers


def _generate_next_actions(missing_core: List[SkillExplainItem], missing_secondary: List[SkillExplainItem]) -> List[str]:
    """Generate actionable next steps (French).

    Priority:
      1. Top 1-2 CORE skills to learn
      2. Top 1-2 SECONDARY skills to learn
      3. Generic actions
    """
    actions = []

    # Priority 1: Top core missing (will have biggest impact)
    if missing_core:
        priority_skill = missing_core[0].label.lower()
        actions.append(f"Apprendre les bases de {priority_skill}")
        if len(missing_core) > 1:
            second_skill = missing_core[1].label.lower()
            actions.append(f"Acquérir de l'expérience en {second_skill}")

    # Priority 2: Top secondary missing
    if len(actions) < 3 and missing_secondary:
        secondary_skill = missing_secondary[0].label.lower()
        actions.append(f"Explorer des projets {secondary_skill}")

    # Priority 3: Generic upskilling
    if len(actions) < 2:
        actions.append("Constituer un portfolio avec des projets réels")

    # Limit to 3 actions
    return actions[:3]


def build_offer_explanation(
    score: int,
    skill_overlap: int,
    title: str,
    explain_block: Optional[ExplainBlock],
    domain_affinity: Optional[str] = None,
) -> OfferExplanation:
    """Build user-friendly explanation from ExplainBlock.

    Transforms technical ExplainBlock into narrative OfferExplanation.
    No scoring changes. No new data sources.

    Args:
        score: 0-100 match score
        skill_overlap: Count of matched skills
        title: Offer title/role name
        explain_block: Technical ExplainBlock with matched/missing skills
        domain_affinity: "aligned", "related", or "out"

    Returns:
        OfferExplanation with narrative summary_reason, strengths, gaps, next_actions
    """
    if not explain_block:
        # Fallback if no explain data
        return OfferExplanation(
            score=score,
            fit_label=_score_to_label(score),
            summary_reason=f"Matched on {title} role profile.",
            strengths=[],
            gaps=[],
            blockers=[],
            next_actions=[],
        )

    # Extract components
    matched_core = explain_block.matched_core or []
    matched_secondary = explain_block.matched_secondary or []
    missing_core = explain_block.missing_core or []
    missing_secondary = explain_block.missing_secondary or []

    # Generate narrative
    summary_reason = _get_core_skills_summary(matched_core, missing_core, skill_overlap)

    # Add domain affinity context if present
    if domain_affinity == "aligned":
        summary_reason += f" Votre profil s'aligne avec le domaine {title}."
    elif domain_affinity == "related":
        summary_reason += f" Votre profil a une convergence de domaine pertinente avec ce rôle."

    strengths = _extract_strengths(matched_core, matched_secondary)
    gaps = _extract_gaps(missing_core, missing_secondary)
    blockers = _extract_blockers(missing_core)
    next_actions = _generate_next_actions(missing_core, missing_secondary)

    return OfferExplanation(
        score=score,
        fit_label=_score_to_label(score),
        summary_reason=summary_reason,
        strengths=strengths,
        gaps=gaps,
        blockers=blockers,
        next_actions=next_actions,
    )


def _score_to_label(score: int) -> str:
    """Convert score (0-100) to fit label (French).

    Examples:
      80-100: "Excellent match"
      60-79: "Bon match"
      40-59: "Match moyen"
      20-39: "Match faible"
      0-19: "Peu pertinent"
    """
    if score >= 80:
        return "Excellent match"
    elif score >= 60:
        return "Bon match"
    elif score >= 40:
        return "Match moyen"
    elif score >= 20:
        return "Match faible"
    else:
        return "Peu pertinent"


def format_explanation_for_display(explanation: OfferExplanation) -> Dict[str, Any]:
    """Format OfferExplanation for JSON response.

    Cleans up formatting, removes empty lists, structures for UI.
    """
    return {
        "score": explanation.score,
        "fit_label": explanation.fit_label,
        "summary_reason": explanation.summary_reason,
        "strengths": [s for s in explanation.strengths if s],
        "gaps": [g for g in explanation.gaps if g],
        "blockers": [b for b in explanation.blockers if b],
        "next_actions": [a for a in explanation.next_actions if a],
    }
