"""
matching.py - Route FastAPI pour le matching
Sprint 7

Expose le moteur Sprint 6 via POST /v1/match
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from ..schemas.matching import MatchingRequest, MatchingResponse, ResultItem

# Import moteur Sprint 6 (LECTURE SEULE - ne pas modifier)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from matching import MatchingEngine


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

    Le moteur Sprint 6 est appelé tel quel, sans modification.
    """
    try:
        # Construire le moteur avec IDF sur les offres fournies
        engine = MatchingEngine(
            offers=request.offers,
            context_coeffs=request.context_coeffs
        )

        # Exécuter le matching
        output = engine.match(
            profile=request.profile,
            offers=request.offers
        )

        # Convertir en réponse Pydantic
        results = [
            ResultItem(
                offer_id=r.offer_id,
                score=r.score,
                breakdown=r.breakdown,
                reasons=r.reasons
            )
            for r in output.results
        ]

        return MatchingResponse(
            profile_id=output.profile_id,
            threshold=output.threshold,
            results=results,
            message=output.message
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur matching: {str(e)}"
        )
