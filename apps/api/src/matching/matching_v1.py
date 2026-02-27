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

import logging
import os
import importlib
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .extractors import (
    ExtractedProfile,
    extract_profile,
    canonize_country,
    parse_education_level,
    normalize_skill,
    normalize_language,
)
from .idf import compute_idf

logger = logging.getLogger(__name__)

# Optional ESCO helpers for URI-based scoring
try:
    from ..esco.mapper import map_skill
    from ..esco.uri_collapse import collapse_to_uris
    from ..esco.extract import SKILL_ALIASES as _OFFER_SKILL_ALIASES
except ImportError:
    try:
        _esco_mapper = importlib.import_module("esco.mapper")
        _esco_collapse = importlib.import_module("esco.uri_collapse")
        _esco_extract = importlib.import_module("esco.extract")
        map_skill = _esco_mapper.map_skill
        collapse_to_uris = _esco_collapse.collapse_to_uris
        _OFFER_SKILL_ALIASES = _esco_extract.SKILL_ALIASES
    except ImportError:
        map_skill = None
        collapse_to_uris = None
        _OFFER_SKILL_ALIASES = {}


def _debug_enabled() -> bool:
    value = os.getenv("ELEVIA_DEBUG_MATCHING", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _use_uri_scoring() -> bool:
    value = os.getenv("ELEVIA_SCORE_USE_URIS", "1").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def normalize_skill_uri(uri: str) -> str:
    """Normalize ESCO URI without altering structure (no punctuation stripping)."""
    if not uri:
        return ""
    return uri.strip()


def _normalize_uri_list(raw_skills) -> List[str]:
    if isinstance(raw_skills, str):
        raw_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
    if isinstance(raw_skills, list):
        normalized = [normalize_skill_uri(s) for s in raw_skills if isinstance(s, str) and s.strip()]
        return _dedupe_preserve_order([s for s in normalized if s])
    return []


def _build_offer_label_map(offer: Dict) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    display = offer.get("skills_display")
    if isinstance(display, list):
        for item in display:
            if not isinstance(item, dict):
                continue
            uri = item.get("uri")
            label = item.get("label") or uri
            if uri and uri not in mapping:
                mapping[str(uri)] = str(label)
    return mapping


def _map_offer_skills_to_uris(raw_skills: List[str]) -> Dict[str, object]:
    """
    Map explicit offer skills to ESCO URIs (strict), preserving order.
    Used as fallback when skills_uri is missing.
    """
    if not raw_skills or not map_skill or not collapse_to_uris:
        return {
            "uris": [],
            "label_map": {},
            "collapsed_dupes": 0,
            "unmapped_count": 0,
        }

    mapped_items: List[Dict[str, str]] = []
    unmapped: List[str] = []
    for skill in raw_skills:
        if not skill:
            continue
        s = str(skill)
        mapped_any = False
        if s.startswith("http://data.europa.eu/esco/"):
            mapped_items.append({
                "surface": s,
                "esco_uri": s,
                "esco_label": s,
                "source": "explicit",
            })
            mapped_any = True
        else:
            result = map_skill(s, enable_fuzzy=False)
            if result:
                mapped_items.append({
                    "surface": s,
                    "esco_uri": result.get("esco_id", ""),
                    "esco_label": result.get("label") or result.get("canonical") or s,
                    "source": "explicit",
                })
                mapped_any = True

        # Alias expansion to improve ESCO coverage for explicit skills
        alias_key = s.lower()
        if alias_key in _OFFER_SKILL_ALIASES:
            for alias in _OFFER_SKILL_ALIASES[alias_key]:
                alias_result = map_skill(alias, enable_fuzzy=False)
                if alias_result:
                    mapped_items.append({
                        "surface": alias,
                        "esco_uri": alias_result.get("esco_id", ""),
                        "esco_label": alias_result.get("label") or alias_result.get("canonical") or alias,
                        "source": "alias",
                    })
                    mapped_any = True

        if not mapped_any:
            unmapped.append(s)

    collapsed = collapse_to_uris(mapped_items)
    display = collapsed.get("display") or []
    label_map = {
        item.get("uri"): item.get("label")
        for item in display
        if isinstance(item, dict) and item.get("uri")
    }
    return {
        "uris": collapsed.get("uris") or [],
        "label_map": {str(k): str(v) for k, v in label_map.items()},
        "collapsed_dupes": int(collapsed.get("collapsed_dupes", 0) or 0),
        "unmapped_count": len(_dedupe_preserve_order(unmapped)),
    }

def _offer_skill_field_label(offer: Dict) -> str:
    if "skills_uri" in offer:
        return "skills_uri"
    if "skills" in offer:
        return "skills"
    if isinstance(offer.get("extracted"), dict) and "skills" in offer["extracted"]:
        return "extracted.skills"
    if "required_skills" in offer:
        return "required_skills"
    return "missing"


def _normalize_skill_list(raw_skills) -> List[str]:
    if isinstance(raw_skills, str):
        raw_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
    if isinstance(raw_skills, list):
        return [normalize_skill(s) for s in raw_skills if isinstance(s, str) and s.strip()]
    return []

# ============================================================================
# CONSTANTES (VERROUILLÉES - spec lignes 78-83)
# ============================================================================

WEIGHT_SKILLS = 0.70
WEIGHT_LANGUAGES = 0.15
WEIGHT_EDUCATION = 0.10
WEIGHT_COUNTRY = 0.05

THRESHOLD = 80  # Seuil strict (spec ligne 46)
PARTIAL_MAX_SCORE = 30  # Max score when skills are unavailable

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
    match_debug: Optional[Dict[str, Any]] = None
    score_is_partial: bool = False


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
        skill_field = "skills_uri" if _use_uri_scoring() else "skills"
        self.idf_table = compute_idf(offers, skill_field=skill_field)
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
    ) -> Tuple[float, List[str], List[str], bool]:
        """
        Score skills (signal principal) - spec lignes 100-114.

        Formule: skills_score = matched_skills / required_skills

        Returns:
            (score, matched_skills, missing_skills, skills_missing)
        """
        if _use_uri_scoring():
            raw_uris = offer.get("skills_uri")
            label_map = _build_offer_label_map(offer)
            collapsed_dupes = int(offer.get("skills_uri_collapsed_dupes", 0) or 0)
            unmapped_count = int(offer.get("skills_unmapped_count", 0) or 0)

            if raw_uris is None:
                raw_skills = offer.get("skills", [])
                if isinstance(raw_skills, str):
                    raw_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
                mapped = _map_offer_skills_to_uris(raw_skills if isinstance(raw_skills, list) else [])
                raw_uris = mapped.get("uris") or []
                label_map = label_map or (mapped.get("label_map") or {})
                collapsed_dupes = int(mapped.get("collapsed_dupes", 0) or 0)
                unmapped_count = int(mapped.get("unmapped_count", 0) or 0)
                # Cache for downstream if needed
                offer["skills_uri"] = raw_uris
                offer["skills_display"] = offer.get("skills_display") or [
                    {"uri": uri, "label": label_map.get(uri, uri), "source": "explicit"}
                    for uri in raw_uris
                ]
                offer["skills_uri_collapsed_dupes"] = collapsed_dupes
                offer["skills_unmapped_count"] = unmapped_count

            offer_skills = _normalize_uri_list(raw_uris)
            offer_skills_set = set(offer_skills)

            # Spec ligne 113: "Si l'offre n'a aucune skill → skills_score = 0"
            if not offer_skills:
                return 0.0, [], [], True

            profile_skills_set = getattr(profile, "skills_uri", frozenset()) or frozenset()
            matched_uris = [uri for uri in offer_skills if uri in profile_skills_set]
            missing_uris = [uri for uri in offer_skills if uri not in profile_skills_set]

            matched_labels = [label_map.get(uri, uri) for uri in matched_uris]
            missing_labels = [label_map.get(uri, uri) for uri in missing_uris]

            if not matched_uris:
                return 0.0, [], missing_labels, False

            score = len(matched_uris) / len(offer_skills)
            return score, matched_labels, missing_labels, False

        raw_skills = offer.get("skills", [])
        if isinstance(raw_skills, str):
            raw_skills = [s.strip() for s in raw_skills.split(",") if s.strip()]

        offer_skills_set = set(normalize_skill(s) for s in raw_skills if s)
        offer_skills = sorted(offer_skills_set)

        # Spec ligne 113: "Si l'offre n'a aucune skill → skills_score = 0"
        if not offer_skills:
            return 0.0, [], [], True

        # Intersection profil ∩ offre
        matched_skills_set = profile.skills & offer_skills_set
        matched_skills = sorted(matched_skills_set)
        missing_skills = [s for s in offer_skills if s not in matched_skills_set]

        if not matched_skills:
            return 0.0, [], missing_skills, False

        score = len(matched_skills) / len(offer_skills)
        return score, matched_skills, missing_skills, False

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
        score_is_partial: bool = False,
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
        score = int(round(100 * total))
        if score_is_partial:
            return min(score, PARTIAL_MAX_SCORE)
        return score

    def _build_match_debug(
        self,
        matched_skills: List[str],
        missing_skills: List[str],
        skills_score: float,
        languages_score: float,
        education_score: float,
        country_score: float,
        profile: ExtractedProfile,
        offer: Dict,
    ) -> Dict[str, Any]:
        """Build a transparent debug payload for scoring."""
        total = (
            WEIGHT_SKILLS * skills_score +
            WEIGHT_LANGUAGES * languages_score +
            WEIGHT_EDUCATION * education_score +
            WEIGHT_COUNTRY * country_score
        )

        language_match = languages_score == 1.0
        education_match = education_score == 1.0
        if not profile.preferred_countries:
            country_match = True
        else:
            offer_country = offer.get("country") or offer.get("pays") or ""
            country_match = canonize_country(offer_country) in profile.preferred_countries

        skills_debug: Dict[str, Any] = {
            "matched": matched_skills,
            "missing": missing_skills,
            "weight": int(WEIGHT_SKILLS * 100),
            "score": round(skills_score * WEIGHT_SKILLS * 100, 1),
        }
        if _use_uri_scoring():
            offer_uri_list = offer.get("skills_uri") or []
            skills_debug.update({
                "scoring_unit": "uri",
                "intersection_count": len(matched_skills),
                "offer_skill_uri_count": int(offer.get("skills_uri_count", len(offer_uri_list))),
                "offer_skill_collapsed_dupes": int(offer.get("skills_uri_collapsed_dupes", 0) or 0),
                "offer_unmapped_count": int(offer.get("skills_unmapped_count", 0) or 0),
                "profile_skill_uri_count": int(getattr(profile, "skills_uri_count", 0) or 0),
                "profile_skill_collapsed_dupes": int(getattr(profile, "skills_uri_collapsed_dupes", 0) or 0),
                "profile_unmapped_count": int(getattr(profile, "skills_unmapped_count", 0) or 0),
            })
        else:
            skills_debug.update({
                "scoring_unit": "string",
                "intersection_count": len(matched_skills),
            })

        return {
            "skills": skills_debug,
            "language": {
                "match": language_match,
                "weight": int(WEIGHT_LANGUAGES * 100),
                "score": round(languages_score * WEIGHT_LANGUAGES * 100, 1),
            },
            "education": {
                "match": education_match,
                "weight": int(WEIGHT_EDUCATION * 100),
                "score": round(education_score * WEIGHT_EDUCATION * 100, 1),
            },
            "country": {
                "match": country_match,
                "weight": int(WEIGHT_COUNTRY * 100),
                "score": round(country_score * WEIGHT_COUNTRY * 100, 1),
            },
            "total": round(total * 100, 1),
        }

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
        skills_missing: bool = False,
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
        if skills_missing and len(reasons) < 3:
            reasons.append("Compétences indisponibles pour cette offre")
        if not matched_skills and not skills_missing and len(reasons) < 3:
            reasons.append("Aucune compétence détectée en commun")
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

    def score_offer(
        self,
        profile: ExtractedProfile,
        offer: Dict,
    ) -> MatchResult:
        """
        Score une offre SANS filtrage.

        Retourne toujours un score (même 0 si hard filter échoue).
        Utilisé par l'API pour retourner toutes les offres scorées.
        """
        offer_id = offer.get("id") or offer.get("offer_id") or offer.get("offer_uid", "unknown")

        # Check hard filter (pour info, pas pour filtrer)
        passed_hard, rejection = self._hard_filter(offer)
        if not passed_hard:
            return MatchResult(
                offer_id=str(offer_id),
                score=0,
                breakdown={"skills": 0.0, "languages": 0.0, "education": 0.0, "country": 0.0},
                reasons=[f"Rejeté: {rejection}"],
                match_debug=None,
            )

        # Calcul scores
        skills_score, matched_skills, missing_skills, skills_missing = self._score_skills(profile, offer)
        languages_score = self._score_languages(profile, offer)
        education_score = self._score_education(profile, offer)
        country_score = self._score_country(profile, offer)

        final_score = self._compute_final_score(
            skills_score, languages_score, education_score, country_score, skills_missing
        )

        reasons = self._generate_reasons(
            matched_skills, languages_score, education_score, country_score, skills_missing
        )

        if _debug_enabled():
            if _use_uri_scoring():
                raw_offer_skills = offer.get("skills_uri") or offer.get("skills", [])
                normalized_offer_skills = _normalize_uri_list(raw_offer_skills)
                offer_skills_len = len(normalized_offer_skills)
                profile_skills_len = len(getattr(profile, "skills_uri", []))
            else:
                raw_offer_skills = offer.get("skills", [])
                normalized_offer_skills = _normalize_skill_list(raw_offer_skills)
                offer_skills_len = len(set(normalized_offer_skills))
                profile_skills_len = len(profile.skills)
            logger.info(
                "match_debug offer_id=%s total=%s skills=%s lang=%s edu=%s country=%s "
                "len_offer_skills=%s len_profile_skills=%s intersection=%s "
                "len_profile_matching_skills=%s len_profile_capabilities=%s "
                "offer_skill_field=%s profile_skill_field=%s offer_skills_sample=%s",
                offer_id,
                final_score,
                round(skills_score * 100, 1),
                round(languages_score * 100, 1),
                round(education_score * 100, 1),
                round(country_score * 100, 1),
                offer_skills_len,
                profile_skills_len,
                len(matched_skills),
                getattr(profile, "matching_skills_count", len(profile.skills)),
                getattr(profile, "capabilities_count", 0),
                _offer_skill_field_label(offer),
                getattr(profile, "skill_source", "skills"),
                normalized_offer_skills[:20],
            )

        return MatchResult(
            offer_id=str(offer_id),
            score=final_score,
            breakdown={
                "skills": round(skills_score, 2),
                "languages": round(languages_score, 2),
                "education": round(education_score, 2),
                "country": round(country_score, 2),
            },
            reasons=reasons,
            match_debug=self._build_match_debug(
                matched_skills,
                missing_skills,
                skills_score,
                languages_score,
                education_score,
                country_score,
                profile,
                offer,
            ),
            score_is_partial=skills_missing,
        )

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
            skills_score, matched_skills, missing_skills, skills_missing = self._score_skills(extracted_profile, offer)

            # 4. Early-skip mathématique (spec ligne 63)
            if self._early_skip(skills_score):
                continue

            # 5. Scores complémentaires
            languages_score = self._score_languages(extracted_profile, offer)
            education_score = self._score_education(extracted_profile, offer)
            country_score = self._score_country(extracted_profile, offer)

            # 6. Score final
            final_score = self._compute_final_score(
                skills_score, languages_score, education_score, country_score, skills_missing
            )

            # 7. Seuil strict (spec ligne 46)
            if final_score < THRESHOLD:
                continue

            # 8. Génération explications (uniquement si retenue - spec ligne 159)
            reasons = self._generate_reasons(
                matched_skills, languages_score, education_score, country_score, skills_missing
            )

            # 9. Ajout au résultat
            offer_id = offer.get("id") or offer.get("offer_id") or offer.get("offer_uid", "unknown")
            if _debug_enabled():
                if _use_uri_scoring():
                    raw_offer_skills = offer.get("skills_uri") or offer.get("skills", [])
                    normalized_offer_skills = _normalize_uri_list(raw_offer_skills)
                    offer_skills_len = len(normalized_offer_skills)
                    profile_skills_len = len(getattr(extracted_profile, "skills_uri", []))
                else:
                    raw_offer_skills = offer.get("skills", [])
                    normalized_offer_skills = _normalize_skill_list(raw_offer_skills)
                    offer_skills_len = len(set(normalized_offer_skills))
                    profile_skills_len = len(extracted_profile.skills)
                logger.info(
                    "match_debug offer_id=%s total=%s skills=%s lang=%s edu=%s country=%s "
                    "len_offer_skills=%s len_profile_skills=%s intersection=%s "
                    "len_profile_matching_skills=%s len_profile_capabilities=%s "
                    "offer_skill_field=%s profile_skill_field=%s offer_skills_sample=%s",
                    offer_id,
                    final_score,
                    round(skills_score * 100, 1),
                    round(languages_score * 100, 1),
                    round(education_score * 100, 1),
                    round(country_score * 100, 1),
                    offer_skills_len,
                    profile_skills_len,
                    len(matched_skills),
                    getattr(extracted_profile, "matching_skills_count", len(extracted_profile.skills)),
                    getattr(extracted_profile, "capabilities_count", 0),
                    _offer_skill_field_label(offer),
                    getattr(extracted_profile, "skill_source", "skills"),
                    normalized_offer_skills[:20],
                )
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
                match_debug=self._build_match_debug(
                    matched_skills,
                    missing_skills,
                    skills_score,
                    languages_score,
                    education_score,
                    country_score,
                    extracted_profile,
                    offer,
                ),
                score_is_partial=skills_missing,
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
                    "match_debug": r.match_debug,
                    "score_is_partial": r.score_is_partial,
                }
                for r in output.results
            ],
            "message": output.message,
        }
