from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from profile_understanding.service import get_profile_understanding_resources

router = APIRouter(tags=["profile-understanding"])


@router.get("/profile-understanding/resources")
async def get_profile_understanding_agent_resources() -> Dict[str, Any]:
    return get_profile_understanding_resources()
