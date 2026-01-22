"""
matching.py - Route FastAPI pour le matching
Sprint 7

Expose le moteur Sprint 6 via POST /v1/match
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from ..schemas.matching import MatchingRequest, MatchingResponse, ResultItem

# Import moteur Sprint 6
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from matching import MatchingEngine
from matching.extractors import extract_profile


router = APIRouter(tags=["matching"])


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
"""
)
async def match_profile(request: MatchingRequest) -> MatchingResponse:
    """
    Match un profil candidat contre une liste d'offres.

    Retourne TOUTES les offres scorées (pas de filtrage côté API).
    Le filtrage (>=80, 70-79) est un choix d'affichage côté front.
    """
    try:
        # Construire le moteur avec IDF sur les offres fournies
        engine = MatchingEngine(
            offers=request.offers,
            context_coeffs=request.context_coeffs
        )

        # Extraire le profil une seule fois
        extracted_profile = extract_profile(request.profile)

        # Scorer TOUTES les offres (sans filtrage)
        results = []
        for offer in request.offers:
            match_result = engine.score_offer(extracted_profile, offer)
            results.append(ResultItem(
                offer_id=match_result.offer_id,
                score=match_result.score,
                breakdown=match_result.breakdown,
                reasons=match_result.reasons
            ))

        # Tri par score décroissant
        results.sort(key=lambda r: r.score, reverse=True)

        return MatchingResponse(
            profile_id=extracted_profile.profile_id,
            threshold=80,
            received_offers=len(request.offers),
            results=results,
            message=None
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur matching: {str(e)}"
        )
