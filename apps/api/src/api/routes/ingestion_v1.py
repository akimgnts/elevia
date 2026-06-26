from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..repositories.offers_pg import OffersPgRepository
from ..schemas.offers_v1 import IngestionLatestResponse


logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingestion-v1"])


def _service_unavailable() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "INGESTION_UNAVAILABLE",
                "message": "Ingestion status is temporarily unavailable",
            }
        },
    )


@router.get("/ingestion/latest", response_model=IngestionLatestResponse)
async def get_latest_ingestion():
    try:
        run = OffersPgRepository().fetch_latest_ingestion(source="business_france")
    except Exception as exc:
        logger.warning("[ingestion_v1] latest ingestion unavailable: %s", exc)
        return _service_unavailable()

    if run is None:
        return _service_unavailable()

    return IngestionLatestResponse.model_validate(run)
