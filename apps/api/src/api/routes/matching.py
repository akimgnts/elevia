"""
matching.py - Route FastAPI pour le matching
Sprint 7 + Sprint 11 (filtrage légal V.I.E)

Expose le moteur Sprint 6 via POST /v1/match
Applique le filtrage légal V.I.E (Sprint 11)
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from ..schemas.matching import (
    MatchingRequest,
    MatchingResponse,
    ResultItem,
    DiagnosticResult,
    DiagnosticCriterion,
)

# Import moteur Sprint 6 + diagnostic Sprint 9
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from matching import MatchingEngine, compute_diagnostic, Verdict
from matching.extractors import extract_profile


router = APIRouter(tags=["matching"])


# ============================================================================
# FILTRE LÉGAL V.I.E (Sprint 11)
# ============================================================================

def filter_legal_vie_offers(results: List[ResultItem]) -> List[ResultItem]:
    """
    Filtre les offres légalement inaccessibles (KO V.I.E Eligibility).

    Règle produit (docs/strategy/matching_product_rules.md):
    - Si diagnostic.vie_eligibility.status == KO → offre MASQUÉE
    - Aucun fallback, aucune trace côté client

    Cette fonction est une barrière légale, pas un choix UX.
    """
    return [
        r for r in results
        if r.diagnostic is None or r.diagnostic.vie_eligibility.status != "KO"
    ]


# ============================================================================
# ENDPOINT
# ============================================================================

@router.post(
    "/match",
    response_model=MatchingResponse,
    summary="Match un profil contre des offres VIE",
    description="""
Exécute le matching V1 déterministe et explicable.

**Règles métier (Sprint 6 - VERROUILLÉ):**
- Seules les offres avec `is_vie=True` sont considérées
- Seuil par défaut: 80%
- Pondérations: skills=70%, languages=15%, education=10%, country=5%
- Maximum 3 raisons par offre
- Aucun mot IA/probabilité dans les explications

**Filtrage légal (Sprint 11):**
- Les offres KO V.I.E Eligibility sont automatiquement exclues
- Un candidat ne verra jamais une offre pour laquelle il est légalement inéligible
"""
)
async def match_profile(request: MatchingRequest) -> MatchingResponse:
    """
    Match un profil candidat contre une liste d'offres.

    Pipeline:
    1. Score toutes les offres
    2. Calcule le diagnostic pour chaque offre
    3. Filtre les offres KO V.I.E (barrière légale)
    4. Retourne les offres autorisées avec leur diagnostic
    """
    try:
        # Construire le moteur avec IDF sur les offres fournies
        engine = MatchingEngine(
            offers=request.offers,
            context_coeffs=request.context_coeffs
        )

        # Extraire le profil une seule fois
        extracted_profile = extract_profile(request.profile)

        # Scorer et diagnostiquer TOUTES les offres
        results = []
        for offer in request.offers:
            # 1. Score
            match_result = engine.score_offer(extracted_profile, offer)

            # 2. Diagnostic (Sprint 9)
            diag = compute_diagnostic(request.profile, offer)

            # 3. Convertir en schema
            diagnostic_result = DiagnosticResult(
                global_verdict=diag.global_verdict.value,
                top_blocking_reasons=diag.top_blocking_reasons,
                hard_skills=DiagnosticCriterion(
                    status=diag.hard_skills.status.value,
                    details=diag.hard_skills.details,
                    missing=diag.hard_skills.missing,
                ),
                soft_skills=DiagnosticCriterion(
                    status=diag.soft_skills.status.value,
                    details=diag.soft_skills.details,
                    missing=diag.soft_skills.missing,
                ),
                languages=DiagnosticCriterion(
                    status=diag.languages.status.value,
                    details=diag.languages.details,
                    missing=diag.languages.missing,
                ),
                education=DiagnosticCriterion(
                    status=diag.education.status.value,
                    details=diag.education.details,
                    missing=diag.education.missing,
                ),
                vie_eligibility=DiagnosticCriterion(
                    status=diag.vie_eligibility.status.value,
                    details=diag.vie_eligibility.details,
                    missing=diag.vie_eligibility.missing,
                ),
            )

            results.append(ResultItem(
                offer_id=match_result.offer_id,
                score=match_result.score,
                breakdown=match_result.breakdown,
                reasons=match_result.reasons,
                diagnostic=diagnostic_result,
            ))

        # Tri par score décroissant (AVANT filtrage)
        results.sort(key=lambda r: r.score, reverse=True)

        # FILTRAGE LÉGAL V.I.E (Sprint 11)
        # Les offres KO V.I.E sont retirées définitivement
        legal_results = filter_legal_vie_offers(results)

        return MatchingResponse(
            profile_id=extracted_profile.profile_id,
            threshold=80,
            received_offers=len(request.offers),
            results=legal_results,
            message=None
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur matching: {str(e)}"
        )
