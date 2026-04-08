"""
justification_layer.py — AI-powered business-fit justification.

Interprets existing matching signals to produce recruiter-grade analysis:
  - GO / MAYBE / NO_GO decision
  - True gaps vs. pseudo-gaps vs. HR jargon
  - Transferable strengths with evidence
  - CV positioning strategy

Rules (absolute — never violate):
  - NEVER modify scoring/matching core
  - NEVER recalculate or override offer scores
  - Only interprets signals already computed by the pipeline
  - Falls back to deterministic analysis when LLM unavailable
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_JUSTIFY_MODEL = "gpt-4o-mini"
_JUSTIFY_TIMEOUT_S = 45
_JUSTIFY_MAX_TOKENS = 2500
_JUSTIFY_RETRIES = 1


# ---------------------------------------------------------------------------
# LLM call (local wrapper — higher token budget than cv_generator)
# ---------------------------------------------------------------------------

def _get_api_key() -> Optional[str]:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    try:
        from api.utils.env import get_llm_api_key
        key = get_llm_api_key()
        if key:
            return key
    except Exception:
        pass
    for name in ("OPENAI_API_KEY", "OPENAI_KEY", "LLM_API_KEY"):
        v = os.environ.get(name, "").strip()
        if v:
            return v
    return None


def _is_llm_available() -> bool:
    return bool(_get_api_key())


def _call_llm_justify(system_prompt: str, user_prompt: str) -> Tuple[dict, int, int, int]:
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError("LLM_DISABLED: no API key configured")

    try:
        from openai import OpenAI, APITimeoutError, APIConnectionError, APIStatusError
    except ImportError:
        raise RuntimeError("LLM_DISABLED: openai package not installed")

    client = OpenAI(api_key=api_key, timeout=_JUSTIFY_TIMEOUT_S)
    input_chars = len(system_prompt) + len(user_prompt)
    last_error: Optional[Exception] = None
    t0 = time.time()

    for attempt in range(_JUSTIFY_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=_JUSTIFY_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=_JUSTIFY_MAX_TOKENS,
            )
            break
        except (APITimeoutError, APIConnectionError) as exc:
            last_error = exc
            if attempt < _JUSTIFY_RETRIES:
                time.sleep(1.5)
                continue
            raise RuntimeError("LLM_ERROR: timeout/connection") from exc
        except APIStatusError as exc:
            raise RuntimeError(f"LLM_ERROR: status {exc.status_code}") from exc
        except Exception as exc:
            raise RuntimeError(f"LLM_ERROR: {type(exc).__name__}") from exc

    duration_ms = int((time.time() - t0) * 1000)
    raw = (response.choices[0].message.content or "{}").strip()
    output_chars = len(raw)

    logger.info(
        '{"event":"AI_JUSTIFY_LLM_CALL","model":"%s","input_chars":%d,'
        '"output_chars":%d,"duration_ms":%d}',
        _JUSTIFY_MODEL, input_chars, output_chars, duration_ms,
    )

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"LLM_JSON_PARSE_ERROR: {exc}") from exc

    return parsed, input_chars, output_chars, duration_ms


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """Tu es un expert en recrutement et en stratégie de candidature en France, spécialisé dans les profils VIE, junior et mid-level pour les secteurs Data, Finance, Business et IT.

Ton rôle est d'analyser la compatibilité entre un profil candidat et une offre d'emploi, en distinguant :
1. Les VRAIS gaps bloquants (compétences fondamentales absentes et non compensables rapidement)
2. Les pseudo-gaps (outils spécifiques maîtrisables en 1-2 semaines, jargon RH, certifications non-essentielles)
3. Les forces transférables du candidat (compétences qui compensent des gaps apparents)

Règles absolues :
- Ne jamais recalculer le score de matching fourni
- Ne pas pénaliser un outil si le candidat maîtrise un équivalent (Tableau ≈ Power BI ≈ Looker ; Excel ≈ Google Sheets)
- gap "minor" = appris en < 2 semaines
- gap "semi_blocking" = 1-3 mois d'adaptation, mais candidature viable
- gap "blocking" = fondamental et non compensable sans formation longue
- La stratégie de CV doit être factuelle, percutante, positionnante (style "je vous choisis" assumé)
- Répondre uniquement en JSON valide, SANS markdown, SANS backticks

Structure JSON attendue (respecter exactement les clés et les valeurs enum) :
{
  "decision": "GO" | "MAYBE" | "NO_GO",
  "fit_summary": "2-3 phrases résumant l'adéquation (ton analyste senior, pas commercial)",
  "true_gaps": [
    {"skill": "nom du gap", "severity": "blocking|semi_blocking|minor", "why": "pourquoi c'est un gap réel", "mitigation": "comment le compenser (optionnel)"}
  ],
  "non_skill_requirements": [
    {"text": "intitulé de l'exigence", "type": "tool|context|hr_jargon|seniority_marker|soft_skill|domain_knowledge", "why_not_gap": "pourquoi ce n'est pas un vrai gap"}
  ],
  "transferable_strengths": [
    {"strength": "force transférable", "evidence": "preuve concrète dans le profil", "relevance": "pertinence pour ce poste"}
  ],
  "cv_strategy": {
    "angle": "angle de positionnement (ex: Data Analyst orienté impact business)",
    "focus": "2-3 éléments à mettre en avant dans le CV",
    "positioning_phrase": "phrase d'accroche percutante pour la lettre ou le résumé CV (1 phrase, style assumé)"
  },
  "application_effort": "LOW" | "MEDIUM" | "HIGH",
  "confidence": 0.0-1.0,
  "archetype": "archétype du profil pour ce poste (ex: Data Analyst polyvalent, Analyste junior en transition, Profil atypique à fort potentiel)"
}"""


def _build_user_prompt(
    *,
    offer_id: str,
    offer_title: str,
    offer_company: str,
    offer_description: str,
    offer_cluster: str,
    offer_domains: List[str],
    score: Optional[int],
    matched_skills: List[str],
    missing_skills: List[str],
    canonical_skills: List[str],
    enriched_signals: List[str],
    profile_role: str,
    profile_seniority: str,
    profile_domains: List[str],
) -> str:
    score_str = f"{score}/100" if score is not None else "non calculé"
    matched_str = ", ".join(matched_skills[:20]) if matched_skills else "aucune"
    missing_str = ", ".join(missing_skills[:20]) if missing_skills else "aucune"
    canonical_str = ", ".join(canonical_skills[:15]) if canonical_skills else "aucune"
    offer_domains_str = ", ".join(offer_domains) if offer_domains else "non précisé"
    profile_domains_str = ", ".join(profile_domains) if profile_domains else "non précisé"

    desc_snippet = (offer_description or "")[:800].strip()
    if len(offer_description or "") > 800:
        desc_snippet += "..."

    return f"""=== OFFRE ===
ID: {offer_id}
Intitulé: {offer_title}
Entreprise: {offer_company}
Cluster: {offer_cluster}
Domaines offre: {offer_domains_str}
Description:
{desc_snippet}

=== SCORE DE MATCHING ===
Score: {score_str}
Compétences matchées: {matched_str}
Compétences manquantes (selon le moteur): {missing_str}
Compétences canoniques détectées: {canonical_str}

=== PROFIL CANDIDAT ===
Rôle actuel / cible: {profile_role}
Séniorité: {profile_seniority}
Domaines profil: {profile_domains_str}

=== INSTRUCTION ===
Produis l'analyse de compatibilité. Rappel: les "compétences manquantes" peuvent inclure des pseudo-gaps ou du jargon RH — c'est ton rôle de les filtrer.
"""


# ---------------------------------------------------------------------------
# Deterministic fallback (no LLM)
# ---------------------------------------------------------------------------

def _deterministic_justification(
    *,
    offer_id: str,
    offer_title: str,
    score: Optional[int],
    matched_skills: List[str],
    missing_skills: List[str],
    profile_role: str,
    duration_ms: int,
) -> dict:
    """Minimal structured fallback — no LLM required."""
    s = score if score is not None else 50
    blocking_count = len([sk for sk in missing_skills[:5] if s < 50])

    if s >= 65 and not missing_skills:
        decision = "GO"
        effort = "LOW"
        top3 = ", ".join(matched_skills[:3]) if matched_skills else "compétences clés"
        summary = (
            f"Score {s}/100 — couverture forte des exigences du poste. "
            f"{top3} {'sont' if len(matched_skills) > 1 else 'est'} directement aligné{'s' if len(matched_skills) > 1 else ''} avec ce que recherche le recruteur. "
            "Candidature recommandée sans adaptation majeure."
        )
        angle = f"Expert {matched_skills[0]} orienté impact" if matched_skills else "Profil directement aligné"
        phrase = (
            f"Avec {matched_skills[0]} et {matched_skills[1]} déjà opérationnels, "
            f"je suis en mesure d'être productif dès le premier mois."
            if len(matched_skills) >= 2
            else f"Profil directement aligné avec les exigences de {offer_title}."
        )
    elif s >= 65:
        decision = "GO"
        effort = "MEDIUM"
        top3 = ", ".join(matched_skills[:3]) if matched_skills else "compétences clés"
        summary = (
            f"Score {s}/100 — bon fit global malgré {len(missing_skills)} écart(s) détecté(s). "
            f"{top3} couvrent l'essentiel. "
            "Les gaps signalés sont compensables par l'expérience ou un apprentissage rapide."
        )
        angle = f"Spécialiste {matched_skills[0]} avec lacune(s) compensable(s)" if matched_skills else "Bon fit avec adaptation mineure"
        phrase = (
            f"Mon expertise en {matched_skills[0]} compense largement les écarts secondaires identifiés."
            if matched_skills
            else "Mon parcours m'a préparé à combler rapidement les écarts identifiés."
        )
    elif s >= 45:
        decision = "MAYBE"
        effort = "MEDIUM"
        gap_str = f"{missing_skills[0]}" if missing_skills else "certaines compétences"
        summary = (
            f"Score {s}/100 — fit partiel. "
            f"L'écart principal porte sur {gap_str}. "
            "Une lettre de motivation ciblée et la mise en avant des forces transférables peuvent compenser. "
            "Candidature viable avec effort de personnalisation."
        )
        angle = f"Profil {profile_role} en montée en compétences" if profile_role else "Profil en développement avec atouts transférables"
        phrase = (
            f"Mon expérience en {matched_skills[0]} me permet d'aborder {gap_str} avec une courbe d'apprentissage courte."
            if matched_skills and missing_skills
            else f"Mon parcours en {profile_role or 'ce domaine'} m'a préparé à relever rapidement les défis de ce poste."
        )
    else:
        decision = "NO_GO"
        effort = "HIGH"
        gap_str = ", ".join(missing_skills[:2]) if missing_skills else "compétences fondamentales du poste"
        summary = (
            f"Score {s}/100 — écart structurel trop important pour une candidature directe. "
            f"Les éléments manquants ({gap_str}) sont centraux dans la fiche de poste. "
            "Recommandé : développer ces compétences avant de postuler, ou cibler un poste intermédiaire."
        )
        angle = "Profil à repositionner avant candidature"
        phrase = f"Je développe activement {missing_skills[0] if missing_skills else 'les compétences requises'} pour me positionner sur ce type de poste."

    true_gaps = []
    for skill in missing_skills[:5]:
        if s >= 50:
            severity = "minor"
            mitigation = f"Mettre en avant une compétence équivalente à {skill} dans le CV"
        else:
            severity = "semi_blocking"
            mitigation = f"Prévoir une mention dans la lettre expliquant comment vous compensez l'absence de {skill}"
        true_gaps.append({
            "skill": skill,
            "severity": severity,
            "why": f"Absent du matching automatique — non couvert par les compétences détectées dans le profil",
            "mitigation": mitigation,
        })

    strengths = []
    for skill in matched_skills[:3]:
        strengths.append({
            "strength": skill,
            "evidence": f"'{skill}' confirmé dans le profil via le moteur de matching",
            "relevance": f"Compétence attendue pour {offer_title} — met en valeur directement",
        })

    return {
        "decision": decision,
        "fit_summary": summary,
        "true_gaps": true_gaps,
        "non_skill_requirements": [],
        "transferable_strengths": strengths,
        "cv_strategy": {
            "angle": angle,
            "focus": ", ".join(matched_skills[:3]) if matched_skills else "compétences clés du domaine",
            "positioning_phrase": phrase,
        },
        "application_effort": effort,
        "confidence": 0.55,
        "archetype": None,
        "_fallback": True,
        "_meta_duration_ms": duration_ms,
    }


# ---------------------------------------------------------------------------
# Response normalisation — coerce LLM output to safe types
# ---------------------------------------------------------------------------

def _coerce_list(val: Any) -> list:
    return val if isinstance(val, list) else []


def _coerce_str(val: Any, default: str = "") -> str:
    return str(val).strip() if val else default


def _normalise_response(raw: dict, offer_id: str, profile_id: Optional[str], duration_ms: int, llm_used: bool, fallback_used: bool) -> dict:
    """Ensure all required keys exist with correct types."""
    decision = _coerce_str(raw.get("decision"), "MAYBE")
    if decision not in ("GO", "MAYBE", "NO_GO"):
        decision = "MAYBE"

    effort = _coerce_str(raw.get("application_effort"), "MEDIUM")
    if effort not in ("LOW", "MEDIUM", "HIGH"):
        effort = "MEDIUM"

    try:
        confidence = float(raw.get("confidence", 0.7))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.7

    cv_strategy_raw = raw.get("cv_strategy") or {}
    cv_strategy = {
        "angle": _coerce_str(cv_strategy_raw.get("angle"), "Profil à valoriser"),
        "focus": _coerce_str(cv_strategy_raw.get("focus"), "Compétences techniques"),
        "positioning_phrase": _coerce_str(cv_strategy_raw.get("positioning_phrase"), "Candidat motivé et qualifié."),
    }

    true_gaps = []
    for g in _coerce_list(raw.get("true_gaps")):
        if not isinstance(g, dict):
            continue
        sev = _coerce_str(g.get("severity"), "minor")
        if sev not in ("blocking", "semi_blocking", "minor"):
            sev = "minor"
        true_gaps.append({
            "skill": _coerce_str(g.get("skill"), "gap inconnu"),
            "severity": sev,
            "why": _coerce_str(g.get("why"), ""),
            "mitigation": _coerce_str(g.get("mitigation")) or None,
        })

    non_skill_reqs = []
    _valid_types = {"tool", "context", "hr_jargon", "seniority_marker", "soft_skill", "domain_knowledge"}
    for r in _coerce_list(raw.get("non_skill_requirements")):
        if not isinstance(r, dict):
            continue
        t = _coerce_str(r.get("type"), "context")
        if t not in _valid_types:
            t = "context"
        non_skill_reqs.append({
            "text": _coerce_str(r.get("text"), ""),
            "type": t,
            "why_not_gap": _coerce_str(r.get("why_not_gap"), ""),
        })

    strengths = []
    for s in _coerce_list(raw.get("transferable_strengths")):
        if not isinstance(s, dict):
            continue
        strengths.append({
            "strength": _coerce_str(s.get("strength"), ""),
            "evidence": _coerce_str(s.get("evidence"), ""),
            "relevance": _coerce_str(s.get("relevance"), ""),
        })

    return {
        "decision": decision,
        "fit_summary": _coerce_str(raw.get("fit_summary"), "Analyse non disponible."),
        "true_gaps": true_gaps,
        "non_skill_requirements": non_skill_reqs,
        "transferable_strengths": strengths,
        "cv_strategy": cv_strategy,
        "application_effort": effort,
        "confidence": confidence,
        "archetype": _coerce_str(raw.get("archetype")) or None,
        "meta": {
            "offer_id": offer_id,
            "profile_id": profile_id,
            "duration_ms": duration_ms,
            "llm_used": llm_used,
            "fallback_used": fallback_used,
            "model": _JUSTIFY_MODEL if llm_used else None,
        },
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def justify_fit(
    *,
    offer_id: str,
    offer_title: str,
    offer_company: str,
    offer_description: str,
    offer_cluster: str,
    offer_domains: List[str],
    score: Optional[int],
    matched_skills: List[str],
    missing_skills: List[str],
    canonical_skills: List[str],
    enriched_signals: List[str],
    profile_role: str,
    profile_seniority: str,
    profile_domains: List[str],
    profile_id: Optional[str] = None,
) -> dict:
    """
    Produce business-fit justification for one offer × profile pair.

    Returns a normalised dict that maps directly to JustificationPayload.
    Never raises — falls back to deterministic analysis on any error.
    """
    t0 = time.time()
    llm_used = False
    fallback_used = False

    if _is_llm_available():
        try:
            system_prompt = _SYSTEM_PROMPT
            user_prompt = _build_user_prompt(
                offer_id=offer_id,
                offer_title=offer_title,
                offer_company=offer_company,
                offer_description=offer_description,
                offer_cluster=offer_cluster,
                offer_domains=offer_domains,
                score=score,
                matched_skills=matched_skills,
                missing_skills=missing_skills,
                canonical_skills=canonical_skills,
                enriched_signals=enriched_signals,
                profile_role=profile_role,
                profile_seniority=profile_seniority,
                profile_domains=profile_domains,
            )
            raw_dict, _, _, _ = _call_llm_justify(system_prompt, user_prompt)
            llm_used = True
            duration_ms = int((time.time() - t0) * 1000)
            return _normalise_response(raw_dict, offer_id, profile_id, duration_ms, llm_used=True, fallback_used=False)
        except Exception as exc:
            logger.warning('{"event":"AI_JUSTIFY_LLM_FALLBACK","reason":"%s"}', str(exc)[:120])
            fallback_used = True

    # Deterministic fallback
    duration_ms = int((time.time() - t0) * 1000)
    raw_fallback = _deterministic_justification(
        offer_id=offer_id,
        offer_title=offer_title,
        score=score,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        profile_role=profile_role,
        duration_ms=duration_ms,
    )
    return _normalise_response(raw_fallback, offer_id, profile_id, duration_ms, llm_used=False, fallback_used=True)
