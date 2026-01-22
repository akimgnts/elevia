"""
matching_v1.py
==============
Sprint 6 - Moteur de Matching VIE Minimal Explicable

Conforme à: docs/features/06_MATCHING_MINIMAL_EXPLICABLE.md

Ce moteur:
- ne prédit rien
- n'invente rien
- n'interprète pas
- explique chaque décision avec des faits observables
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .extractors import (
    ExtractedProfile,
    extract_profile,
    canonize_country,
    parse_education_level,
    normalize_skill,
    normalize_language,
)
from .idf import compute_idf, get_skill_idf


# ============================================================================
# CONSTANTES (VERROUILLÉES - spec lignes 78-83)
# ============================================================================

WEIGHT_SKILLS = 0.70
WEIGHT_LANGUAGES = 0.15
WEIGHT_EDUCATION = 0.10
WEIGHT_COUNTRY = 0.05

THRESHOLD = 80  # Seuil strict (spec ligne 46)

CONTEXT_CLAMP_MIN = 0.8  # Clamp contexte (spec ligne 107)
CONTEXT_CLAMP_MAX = 1.2


# ============================================================================
# STRUCTURES DE DONNÉES
# ============================================================================

@dataclass
class MatchResult:
    """Résultat de matching pour une offre."""
    offer_id: str
    score: int
    breakdown: Dict[str, float]
    reasons: List[str]


@dataclass
class MatchingOutput:
    """Sortie complète du matching."""
    profile_id: str
    threshold: int
    results: List[MatchResult]
    message: Optional[str]


# ============================================================================
# MOTEUR DE MATCHING
# ============================================================================

class MatchingEngine:
    """
    Moteur de matching VIE minimal, déterministe, explicable.

    Pipeline (spec lignes 55-70):
    1. Hard Filter strict (VIE, pays, champs min)
    2. Score skills (signal principal)
    3. Early-skip mathématique
    4. Score langues / études / pays
    5. Score final (round)
    6. Explication (2-3 raisons max)
    """

    def __init__(
        self,
        offers: List[Dict],
        context_coeffs: Optional[Dict[str, float]] = None,
    ):
        """
        Initialise le moteur.

        Args:
            offers: Corpus d'offres pour calcul IDF
            context_coeffs: Coefficients contextuels optionnels (clamp ±20%)
        """
        self.idf_table = compute_idf(offers)
        self.context_coeffs = context_coeffs or {}

    def _hard_filter(self, offer: Dict) -> Tuple[bool, Optional[str]]:
        """
        Hard filter AVANT scoring (spec lignes 29-33).

        Rejette si:
        - is_vie n'est pas True (False ou None)
        - pays manquant
        - titre manquant
        - entreprise manquante

        Returns:
            (passed, rejection_reason)
        """
        # VIE strict: rejet si is_vie n'est pas exactement True
        # Spec ligne 26: "is_vie est False OU None"
        is_vie = offer.get("is_vie")
        if is_vie is not True:
            return False, "is_vie n'est pas True"

        # Pays obligatoire (spec ligne 31)
        country = offer.get("country") or offer.get("pays")
        if not country:
            return False, "pays manquant"

        # Titre obligatoire (spec ligne 32)
        title = offer.get("title") or offer.get("job_title") or offer.get("intitule")
        if not title:
            return False, "titre manquant"

        # Entreprise obligatoire (spec ligne 32)
        company = offer.get("company") or offer.get("company_name") or offer.get("entreprise")
        if not company:
            return False, "entreprise manquante"

        return True, None

    def _check_country_whitelist(
        self, offer: Dict, profile: ExtractedProfile
    ) -> bool:
        """
        Vérifie la whitelist pays du profil (spec ligne 33).

        Returns:
            True si le pays est dans la whitelist ou si pas de whitelist
        """
        if not profile.preferred_countries:
            return True  # Pas de whitelist = tout accepté

        offer_country = offer.get("country") or offer.get("pays") or ""
        canonical_country = canonize_country(offer_country)

        return canonical_country in profile.preferred_countries

    def _get_context_coeff(self, skill: str) -> float:
        """
        Récupère le coefficient contextuel d'une skill avec clamp.

        Spec ligne 107: "Clamp contexte : [0.8 ; 1.2]"
        """
        coeff = self.context_coeffs.get(skill, 1.0)
        return max(CONTEXT_CLAMP_MIN, min(CONTEXT_CLAMP_MAX, coeff))

    def _score_skills(
        self, profile: ExtractedProfile, offer: Dict
    ) -> Tuple[float, List[str]]:
        """
        Score skills (signal principal) - spec lignes 100-114.

        Formule: skills_score = Σ(idf * contexte) / Σ(idf * contexte_offre)

        Returns:
            (score, matched_skills)
        """
        raw_skills = offer.get("skills", [])
        if isinstance(raw_skills, str):
            raw_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]

        offer_skills = set(normalize_skill(s) for s in raw_skills if s)

        # Spec ligne 113: "Si l'offre n'a aucune skill → skills_score = 0"
        if not offer_skills:
            return 0.0, []

        # Intersection profil ∩ offre
        matched_skills = profile.skills & offer_skills

        if not matched_skills:
            return 0.0, []

        # Calcul score pondéré
        numerator = 0.0
        denominator = 0.0

        for skill in offer_skills:
            idf = get_skill_idf(skill, self.idf_table)
            context = self._get_context_coeff(skill)
            weighted = idf * context

            denominator += weighted

            if skill in matched_skills:
                numerator += weighted

        if denominator == 0:
            return 0.0, list(matched_skills)

        score = numerator / denominator
        return score, sorted(matched_skills)

    def _score_languages(
        self, profile: ExtractedProfile, offer: Dict
    ) -> float:
        """
        Score langues - spec lignes 117-124.

        Si aucune langue requise → 1.0
        Sinon: |langues_profil ∩ langues_offre| / |langues_offre|
        """
        raw_languages = offer.get("languages", [])
        if isinstance(raw_languages, str):
            raw_languages = [l.strip() for l in raw_languages.split(",") if l.strip()]

        offer_languages = set(normalize_language(l) for l in raw_languages if l)

        # Spec ligne 119: "Si aucune langue requise → 1.0"
        if not offer_languages:
            return 1.0

        matched = profile.languages & offer_languages
        return len(matched) / len(offer_languages)

    def _score_education(
        self, profile: ExtractedProfile, offer: Dict
    ) -> float:
        """
        Score niveau d'études - spec lignes 128-138.

        Mapping ordinal: bac=1, bac+2=2, bac+3=3, bac+5=4, phd=5
        Si pas de niveau requis → 1.0
        Sinon: 1.0 si profil ≥ requis, 0.0 sinon
        """
        required = offer.get("education") or offer.get("education_required")
        required_level = parse_education_level(required)

        # Spec ligne 133: "Si l'offre n'a pas de niveau requis → 1.0"
        if required_level == 0:
            return 1.0

        # Spec lignes 136-137
        if profile.education_level >= required_level:
            return 1.0
        return 0.0

    def _score_country(
        self, profile: ExtractedProfile, offer: Dict
    ) -> float:
        """
        Score pays (préférence) - spec lignes 141-148.

        Si pas de préférences → 1.0
        Sinon: 1.0 si pays dans préférences, 0.5 sinon
        """
        # Spec ligne 143: "Si le profil n'a pas de préférences → 1.0"
        if not profile.preferred_countries:
            return 1.0

        offer_country = offer.get("country") or offer.get("pays") or ""
        canonical_country = canonize_country(offer_country)

        # Spec lignes 145-147
        if canonical_country in profile.preferred_countries:
            return 1.0
        return 0.5

    def _compute_final_score(
        self,
        skills_score: float,
        languages_score: float,
        education_score: float,
        country_score: float,
    ) -> int:
        """
        Calcule le score final - spec lignes 87-94.

        score = int(round(100 * (
            0.70 * skills_score +
            0.15 * languages_score +
            0.10 * education_score +
            0.05 * country_score
        )))
        """
        total = (
            WEIGHT_SKILLS * skills_score +
            WEIGHT_LANGUAGES * languages_score +
            WEIGHT_EDUCATION * education_score +
            WEIGHT_COUNTRY * country_score
        )
        return int(round(100 * total))

    def _early_skip(self, skills_score: float) -> bool:
        """
        Early-skip mathématique - spec lignes 155-158.

        Si même avec languages=1, education=1, country=1
        le score max < 80 → on skip.
        """
        max_possible = (
            WEIGHT_SKILLS * skills_score +
            WEIGHT_LANGUAGES * 1.0 +
            WEIGHT_EDUCATION * 1.0 +
            WEIGHT_COUNTRY * 1.0
        )
        max_score = int(round(100 * max_possible))
        return max_score < THRESHOLD

    def _generate_reasons(
        self,
        matched_skills: List[str],
        languages_score: float,
        education_score: float,
        country_score: float,
    ) -> List[str]:
        """
        Génère les explications (2-3 max) - spec lignes 163-183.

        Ordre de priorité:
        1. Compétences clés alignées (top 2-4)
        2. Langues
        3. Études ou pays

        Interdits: IA, probabilité, potentiel, recommandation
        """
        reasons = []

        # 1. Compétences (priorité max)
        if matched_skills:
            top_skills = matched_skills[:4]  # Top 2-4
            reasons.append(f"Compétences clés alignées : {', '.join(top_skills)}")

        # 2. Langues
        if languages_score == 1.0 and len(reasons) < 3:
            reasons.append("Langue requise compatible")

        # 3. Études ou pays
        if education_score == 1.0 and len(reasons) < 3:
            reasons.append("Niveau d'études cohérent")
        elif country_score == 1.0 and len(reasons) < 3:
            reasons.append("Pays dans les préférences")

        # Garantir max 3 raisons (spec ligne 163)
        return reasons[:3]

    def match(
        self,
        profile: Dict,
        offers: List[Dict],
    ) -> MatchingOutput:
        """
        Exécute le matching complet.

        Args:
            profile: Profil utilisateur (dict brut)
            offers: Liste des offres à évaluer

        Returns:
            MatchingOutput: Résultats du matching
        """
        # Extraction profil UNE SEULE FOIS (spec ligne 153)
        extracted_profile = extract_profile(profile)

        results: List[MatchResult] = []

        for offer in offers:
            # 1. Hard filter (spec lignes 59)
            passed, _ = self._hard_filter(offer)
            if not passed:
                continue

            # 2. Vérification whitelist pays (spec ligne 33)
            if not self._check_country_whitelist(offer, extracted_profile):
                continue

            # 3. Score skills (signal principal)
            skills_score, matched_skills = self._score_skills(extracted_profile, offer)

            # 4. Early-skip mathématique (spec ligne 63)
            if self._early_skip(skills_score):
                continue

            # 5. Scores complémentaires
            languages_score = self._score_languages(extracted_profile, offer)
            education_score = self._score_education(extracted_profile, offer)
            country_score = self._score_country(extracted_profile, offer)

            # 6. Score final
            final_score = self._compute_final_score(
                skills_score, languages_score, education_score, country_score
            )

            # 7. Seuil strict (spec ligne 46)
            if final_score < THRESHOLD:
                continue

            # 8. Génération explications (uniquement si retenue - spec ligne 159)
            reasons = self._generate_reasons(
                matched_skills, languages_score, education_score, country_score
            )

            # 9. Ajout au résultat
            offer_id = offer.get("id") or offer.get("offer_id") or offer.get("offer_uid", "unknown")
            results.append(MatchResult(
                offer_id=str(offer_id),
                score=final_score,
                breakdown={
                    "skills": round(skills_score, 2),
                    "languages": round(languages_score, 2),
                    "education": round(education_score, 2),
                    "country": round(country_score, 2),
                },
                reasons=reasons,
            ))

        # Tri par score décroissant
        results.sort(key=lambda r: r.score, reverse=True)

        # Message si aucun résultat (spec lignes 218-221)
        message = None
        if not results:
            message = "Aucune offre n'atteint 80% avec les données actuelles (compétences/langues/études/pays)."

        return MatchingOutput(
            profile_id=extracted_profile.profile_id,
            threshold=THRESHOLD,
            results=results,
            message=message,
        )

    def to_dict(self, output: MatchingOutput) -> Dict:
        """
        Convertit la sortie en dictionnaire JSON-compatible.

        Format spec lignes 188-222.
        """
        return {
            "profile_id": output.profile_id,
            "threshold": output.threshold,
            "results": [
                {
                    "offer_id": r.offer_id,
                    "score": r.score,
                    "breakdown": r.breakdown,
                    "reasons": r.reasons,
                }
                for r in output.results
            ],
            "message": output.message,
        }
