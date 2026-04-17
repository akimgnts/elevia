from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from profile_understanding.schemas import (
    ProfileUnderstandingSessionRequest,
    ProfileUnderstandingSessionResponse,
)
from profile_understanding.service import ProfileUnderstandingService

router = APIRouter(tags=["profile-understanding"])
service = ProfileUnderstandingService()


@router.post(
    "/profile-understanding/session",
    response_model=ProfileUnderstandingSessionResponse,
)
async def create_profile_understanding_session(
    payload: ProfileUnderstandingSessionRequest,
) -> ProfileUnderstandingSessionResponse:
    return service.create_session(payload)
