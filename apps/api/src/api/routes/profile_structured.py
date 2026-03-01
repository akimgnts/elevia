"""
profile_structured.py — Deterministic profile structurer endpoint.

GET /profile/structured  (query param: cv_text)
POST /profile/structured (body: cv_text)

No LLM. No IO beyond certifications_registry.json (loaded at import).
Delegates to compass.profile_structurer.structure_profile_text_v1.

Debug: set ELEVIA_DEBUG_PROFILE_STRUCT=1 to include extracted_sections.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from compass.profile_structurer import structure_profile_text_v1

logger = logging.getLogger(__name__)
router = APIRouter(tags=["profile"])


class ProfileStructuredRequest(BaseModel):
    cv_text: str = Field(..., min_length=1, description="Raw CV text to structure (may contain HTML)")
    debug: bool = Field(False, description="Include extracted_sections (overrides ELEVIA_DEBUG_PROFILE_STRUCT)")


@router.post(
    "/profile/structured",
    summary="Structure un CV de façon déterministe (v1)",
    description="""
Transforme un CV brut en capital professionnel structuré.

**Pas de LLM. Pas de ML. Déterministe.**

Extrait :
- Expériences (entreprise, titre, dates, durée, bullets, outils, niveau d'autonomie, signaux d'impact)
- Formation (institution, diplôme, filière, dates, cluster_hint)
- Certifications (mappées via registre ou unmapped)
- Outils agrégés (cap 50), entreprises, titres
- cluster_hints inférés (DATA_IT / FINANCE / SUPPLY_OPS / MARKETING_SALES / …)
- Qualité CV : LOW / MED / HIGH (exploitabilité, pas jugement)

**Règle de puissance :** n'influence jamais score_core.
""",
    response_class=JSONResponse,
)
async def post_profile_structured(request: ProfileStructuredRequest) -> JSONResponse:
    try:
        result = structure_profile_text_v1(request.cv_text, debug=request.debug)
        return JSONResponse(content=result.model_dump())
    except Exception as e:
        logger.exception("profile_structured: unexpected error")
        raise HTTPException(status_code=500, detail=f"Structuring error: {str(e)}")


@router.get(
    "/profile/structured",
    summary="Structure un CV court via GET (test/debug uniquement)",
    description="Même logique que POST /profile/structured — utile pour tests rapides via navigateur.",
    response_class=JSONResponse,
)
async def get_profile_structured(
    cv_text: str = Query(..., min_length=1, description="Raw CV text"),
    debug: bool = Query(False, description="Include extracted_sections debug output"),
) -> JSONResponse:
    try:
        result = structure_profile_text_v1(cv_text, debug=debug)
        return JSONResponse(content=result.model_dump())
    except Exception as e:
        logger.exception("profile_structured GET: unexpected error")
        raise HTTPException(status_code=500, detail=f"Structuring error: {str(e)}")
