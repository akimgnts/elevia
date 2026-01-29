"""
diagnostic.py - Moteur de diagnostic factuel
Sprint 9 - Conforme à docs/specs/diagnostic.md

Produit un diagnostic (OK / PARTIAL / KO) pour chaque offre
SANS modifier le calcul du score existant.
"""

from typing import Dict, List

from .models import (
    Verdict,
    VERDICT_PRIORITY,
    CriterionResult,
    MatchingDiagnostic,
)
from .constants import (
    HARD_SKILL_KO_RATIO,
    PILLAR_ORDER,
    EU_COUNTRIES,
    VIE_MAX_AGE,
)
from .extractors import (
    normalize_skill,
    normalize_language,
    parse_education_level,
    canonize_country,
)


def get_worst_verdict(verdicts: List[Verdict]) -> Verdict:
    """
    Retourne le verdict le plus grave selon la hiérarchie.
    Spec: KO > PARTIAL > OK
    """
    return max(verdicts, key=lambda v: VERDICT_PRIORITY[v])


def _diagnose_hard_skills(profile: Dict, offer: Dict) -> CriterionResult:
    """
    Diagnostic Hard Skills.
    - KO si (missing / total) > HARD_SKILL_KO_RATIO
    - PARTIAL si missing > 0
    - OK sinon
    """
    # Extraction skills profil (support both formats)
    raw_profile_skills = profile.get("skills", [])
    detected_caps = profile.get("detected_capabilities", [])

    if detected_caps and isinstance(detected_caps, list):
        # Extract skill names from detected_capabilities objects
        raw_profile_skills = [
            cap.get("name") if isinstance(cap, dict) else cap
            for cap in detected_caps
        ]
    elif isinstance(raw_profile_skills, str):
        raw_profile_skills = [s.strip() for s in raw_profile_skills.split(",") if s.strip()]

    profile_skills = set(normalize_skill(s) for s in raw_profile_skills if s and isinstance(s, str))

    # Extraction skills offre
    raw_offer_skills = offer.get("skills", [])
    if isinstance(raw_offer_skills, str):
        raw_offer_skills = [s.strip() for s in raw_offer_skills.split(",") if s.strip()]
    offer_skills = set(normalize_skill(s) for s in raw_offer_skills if s)

    # Si offre n'a pas de skills requises → OK
    if not offer_skills:
        return CriterionResult(
            status=Verdict.OK,
            details="Aucune compétence requise",
            missing=[],
        )

    # Calcul missing
    missing = offer_skills - profile_skills
    total = len(offer_skills)
    missing_ratio = len(missing) / total if total > 0 else 0

    if missing_ratio > HARD_SKILL_KO_RATIO:
        return CriterionResult(
            status=Verdict.KO,
            details=f"{len(missing)} compétences manquantes sur {total}",
            missing=sorted(missing),
        )
    elif len(missing) > 0:
        return CriterionResult(
            status=Verdict.PARTIAL,
            details=f"{len(missing)} compétences manquantes sur {total}",
            missing=sorted(missing),
        )
    else:
        return CriterionResult(
            status=Verdict.OK,
            details="Toutes les compétences requises présentes",
            missing=[],
        )


def _diagnose_languages(profile: Dict, offer: Dict) -> CriterionResult:
    """
    Diagnostic Languages.
    - KO si au moins une langue requise est manquante
    - OK sinon
    """
    # Extraction langues profil (support both formats)
    raw_profile_langs = profile.get("languages", [])
    if isinstance(raw_profile_langs, str):
        raw_profile_langs = [l.strip() for l in raw_profile_langs.split(",") if l.strip()]
    elif isinstance(raw_profile_langs, list) and raw_profile_langs and isinstance(raw_profile_langs[0], dict):
        # Extract language codes from objects
        raw_profile_langs = [
            lang.get("code") if isinstance(lang, dict) else lang
            for lang in raw_profile_langs
        ]
    profile_langs = set(normalize_language(l) for l in raw_profile_langs if l and isinstance(l, str))

    # Extraction langues offre
    raw_offer_langs = offer.get("languages", [])
    if isinstance(raw_offer_langs, str):
        raw_offer_langs = [l.strip() for l in raw_offer_langs.split(",") if l.strip()]
    offer_langs = set(normalize_language(l) for l in raw_offer_langs if l)

    # Si offre n'a pas de langues requises → OK
    if not offer_langs:
        return CriterionResult(
            status=Verdict.OK,
            details="Aucune langue requise",
            missing=[],
        )

    # Calcul missing
    missing = offer_langs - profile_langs

    if len(missing) > 0:
        return CriterionResult(
            status=Verdict.KO,
            details=f"Langue(s) requise(s) manquante(s)",
            missing=sorted(missing),
        )
    else:
        return CriterionResult(
            status=Verdict.OK,
            details="Toutes les langues requises présentes",
            missing=[],
        )


def _diagnose_education(profile: Dict, offer: Dict) -> CriterionResult:
    """
    Diagnostic Education.
    - PARTIAL si profile < required
    - OK sinon
    - JAMAIS KO (expérience compensatoire possible)
    """
    # Support both formats: "education" and "education_summary": {level}
    profile_edu = profile.get("education")
    if profile_edu is None:
        edu_summary = profile.get("education_summary", {})
        if isinstance(edu_summary, dict):
            profile_edu = edu_summary.get("level")
    profile_level = parse_education_level(profile_edu)
    required_level = parse_education_level(
        offer.get("education") or offer.get("education_required") or offer.get("education_level")
    )

    # Si offre n'a pas de niveau requis → OK
    if required_level == 0:
        return CriterionResult(
            status=Verdict.OK,
            details="Aucun niveau d'études requis",
            missing=[],
        )

    if profile_level < required_level:
        return CriterionResult(
            status=Verdict.PARTIAL,
            details=f"Niveau requis non atteint",
            missing=[],
        )
    else:
        return CriterionResult(
            status=Verdict.OK,
            details="Niveau d'études suffisant",
            missing=[],
        )


def _diagnose_soft_skills(profile: Dict, offer: Dict) -> CriterionResult:
    """
    Diagnostic Soft Skills.
    - PARTIAL si manquants
    - OK sinon
    - JAMAIS KO (trop subjectif)
    """
    # Extraction soft skills profil
    raw_profile_soft = profile.get("soft_skills", [])
    if isinstance(raw_profile_soft, str):
        raw_profile_soft = [s.strip() for s in raw_profile_soft.split(",") if s.strip()]
    profile_soft = set(normalize_skill(s) for s in raw_profile_soft if s)

    # Extraction soft skills offre
    raw_offer_soft = offer.get("soft_skills", [])
    if isinstance(raw_offer_soft, str):
        raw_offer_soft = [s.strip() for s in raw_offer_soft.split(",") if s.strip()]
    offer_soft = set(normalize_skill(s) for s in raw_offer_soft if s)

    # Si offre n'a pas de soft skills requises → OK
    if not offer_soft:
        return CriterionResult(
            status=Verdict.OK,
            details="Aucun soft skill requis",
            missing=[],
        )

    # Calcul missing
    missing = offer_soft - profile_soft

    if len(missing) > 0:
        return CriterionResult(
            status=Verdict.PARTIAL,
            details=f"{len(missing)} soft skill(s) manquant(s)",
            missing=sorted(missing),
        )
    else:
        return CriterionResult(
            status=Verdict.OK,
            details="Tous les soft skills présents",
            missing=[],
        )


def _diagnose_vie_eligibility(profile: Dict, offer: Dict) -> CriterionResult:
    """
    Diagnostic VIE Eligibility.
    - KO si age > 28 ou nationalité hors UE
    - OK sinon
    """
    reasons = []

    # Vérification âge
    age = profile.get("age")
    if age is not None:
        try:
            age_int = int(age)
            if age_int > VIE_MAX_AGE:
                reasons.append(f"âge supérieur à {VIE_MAX_AGE} ans")
        except (ValueError, TypeError):
            pass

    # Vérification nationalité
    nationality = profile.get("nationality") or profile.get("nationalite")
    if nationality:
        norm_nationality = canonize_country(nationality)
        if norm_nationality not in EU_COUNTRIES:
            reasons.append("nationalité hors UE")

    if reasons:
        return CriterionResult(
            status=Verdict.KO,
            details=f"Inéligible VIE : {', '.join(reasons)}",
            missing=[],
        )
    else:
        return CriterionResult(
            status=Verdict.OK,
            details="Éligible VIE",
            missing=[],
        )


def _format_blocking_reason(pillar: str, result: CriterionResult) -> str:
    """
    Formate une raison bloquante pour l'UI.
    """
    if pillar == "vie_eligibility":
        return result.details or "Inéligible VIE"
    elif pillar == "languages":
        if result.missing:
            return f"Langue requise manquante : {', '.join(result.missing)}"
        return result.details or "Langue manquante"
    elif pillar == "hard_skills":
        if result.missing:
            return f"Compétences clés manquantes : {', '.join(result.missing[:4])}"
        return result.details or "Compétences manquantes"
    elif pillar == "education":
        return result.details or "Niveau d'études insuffisant"
    elif pillar == "soft_skills":
        if result.missing:
            return f"Soft skills manquants : {', '.join(result.missing[:4])}"
        return result.details or "Soft skills manquants"
    return result.details or "Critère non satisfait"


def compute_diagnostic(profile: Dict, offer: Dict) -> MatchingDiagnostic:
    """
    Génère un diagnostic factuel du matching
    SANS toucher au score existant.

    Fonction pure, zéro effet de bord.
    Comparaisons factuelles uniquement.
    """
    # Diagnostics par pilier
    hard_skills = _diagnose_hard_skills(profile, offer)
    soft_skills = _diagnose_soft_skills(profile, offer)
    languages = _diagnose_languages(profile, offer)
    education = _diagnose_education(profile, offer)
    vie_eligibility = _diagnose_vie_eligibility(profile, offer)

    # Mapping pilier → résultat
    pillar_results = {
        "vie_eligibility": vie_eligibility,
        "languages": languages,
        "hard_skills": hard_skills,
        "education": education,
        "soft_skills": soft_skills,
    }

    # Calcul global_verdict
    all_verdicts = [
        hard_skills.status,
        soft_skills.status,
        languages.status,
        education.status,
        vie_eligibility.status,
    ]
    global_verdict = get_worst_verdict(all_verdicts)

    # Sélection top_blocking_reasons (max 3)
    # 1. Collecter KO dans l'ordre des piliers
    # 2. Ajouter PARTIAL si < 3
    # 3. Tronquer à 3
    blocking_reasons: List[str] = []

    # D'abord les KO
    for pillar in PILLAR_ORDER:
        if len(blocking_reasons) >= 3:
            break
        result = pillar_results[pillar]
        if result.status == Verdict.KO:
            blocking_reasons.append(_format_blocking_reason(pillar, result))

    # Puis les PARTIAL si < 3
    for pillar in PILLAR_ORDER:
        if len(blocking_reasons) >= 3:
            break
        result = pillar_results[pillar]
        if result.status == Verdict.PARTIAL:
            blocking_reasons.append(_format_blocking_reason(pillar, result))

    return MatchingDiagnostic(
        hard_skills=hard_skills,
        soft_skills=soft_skills,
        languages=languages,
        education=education,
        vie_eligibility=vie_eligibility,
        global_verdict=global_verdict,
        top_blocking_reasons=blocking_reasons[:3],
    )
