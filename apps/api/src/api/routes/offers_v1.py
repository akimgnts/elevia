from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ..repositories.offers_pg import OffersPgRepository
from ..schemas.offers_v1 import OfferDetailResponse, RecentOffersResponse


logger = logging.getLogger(__name__)

router = APIRouter(tags=["offers-v1"])


def _service_unavailable() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "OFFERS_UNAVAILABLE",
                "message": "Offers V1 is temporarily unavailable",
            }
        },
    )


@router.get("/recent", response_model=RecentOffersResponse)
async def get_recent_offers(
    limit: int = Query(default=20, ge=1, le=100),
    country: str | None = Query(default=None),
):
    try:
        offers = OffersPgRepository().fetch_recent_offers(
            limit=limit,
            country=country,
            source="business_france",
        )
    except Exception as exc:
        logger.warning("[offers_v1] recent offers unavailable: %s", exc)
        return _service_unavailable()

    return RecentOffersResponse(offers=offers)


@router.get("/{offer_id}", response_model=OfferDetailResponse)
async def get_offer_detail(offer_id: int):
    try:
        offer = OffersPgRepository().fetch_offer_detail(offer_id)
    except Exception as exc:
        logger.warning("[offers_v1] offer detail unavailable for %s: %s", offer_id, exc)
        return _service_unavailable()

    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")

    return OfferDetailResponse.model_validate(offer)
