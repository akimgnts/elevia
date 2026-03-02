"""
profile_summary.py — Compact ProfileSummaryV1 endpoint.
"""
from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, HTTPException, Query

from api.schemas.profile_summary import ProfileSummaryV1
from api.utils.profile_summary_store import get_profile_summary

logger = logging.getLogger(__name__)
router = APIRouter(tags=["profile"])


def _debug_profile_summary_enabled() -> bool:
    value = os.getenv("ELEVIA_DEBUG_PROFILE_SUMMARY", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


@router.get("/profile/summary", response_model=ProfileSummaryV1)
async def get_profile_summary_route(
    profile_id: str = Query(..., min_length=1),
) -> ProfileSummaryV1:
    payload = get_profile_summary(profile_id)
    if not payload:
        if _debug_profile_summary_enabled():
            logger.info(
                "PROFILE_SUMMARY %s",
                json.dumps({"event": "PROFILE_SUMMARY", "profile_id": profile_id, "status": "MISS"}),
            )
        raise HTTPException(status_code=404, detail={"status": "NO_PROFILE"})

    summary = ProfileSummaryV1.model_validate(payload)
    if _debug_profile_summary_enabled():
        logger.info(
            "PROFILE_SUMMARY %s",
            json.dumps(
                {
                    "event": "PROFILE_SUMMARY",
                    "profile_id": profile_id,
                    "status": "HIT",
                    "last_updated": summary.last_updated,
                }
            ),
        )
    return summary
