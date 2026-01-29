"""
metrics.py - Routes FastAPI pour les métriques de survie
Sprint 14 - VERROU #1

Endpoint POST /metrics/correction pour logger les corrections utilisateur.
Format normalisé strict - aucune variation autorisée.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["metrics"])


def _log_survival_metric(metric: dict) -> None:
    """Append metric to JSONL log (stdout fallback)."""
    log_dir = Path(__file__).parent.parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "survival_metrics.log"
    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(metric) + "\n")
    except Exception:
        print(json.dumps(metric))


# --- Normalized correction format (VERROU #1) ---


class ModifiedLevelItem(BaseModel):
    """Single capability level modification."""
    name: str
    # "from" is a reserved keyword in Python, use alias
    from_level: str = Field(..., alias="from")
    to: str

    model_config = {"populate_by_name": True}


class CapabilitiesCorrections(BaseModel):
    """Capabilities corrections - normalized format."""
    added: List[str] = Field(default_factory=list)
    deleted: List[str] = Field(default_factory=list)
    modified_level: List[ModifiedLevelItem] = Field(default_factory=list)


class Corrections(BaseModel):
    """Corrections container - normalized format."""
    capabilities: CapabilitiesCorrections


class Stats(BaseModel):
    """Stats - normalized format."""
    unmapped_count: int = Field(default=0, ge=0)
    detected_capabilities_count: int = Field(default=0, ge=0)


class Meta(BaseModel):
    """Meta - normalized format."""
    app_version: str
    api_version: str
    timestamp: str


class CorrectionRequest(BaseModel):
    """
    Correction event request - NORMALIZED FORMAT.
    NO VARIATION ALLOWED.
    """
    type: str = Field(default="correction")
    session_id: str = Field(..., min_length=6)
    profile_hash: str = Field(..., min_length=8)
    corrections: Corrections
    stats: Stats
    meta: Meta


@router.post(
    "/correction",
    status_code=201,
    summary="Log user corrections",
    description="Logs user profile corrections for survival metrics analysis. Format normalisé Sprint 14.",
)
async def log_correction(request: CorrectionRequest) -> Dict[str, Any]:
    """
    Log a user correction event.

    NO CV, NO PII - only correction metadata.
    Format normalisé VERROU #1.
    """
    ts_server = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Log EXACTLY what we receive + ts_server
    metric = {
        "type": "correction",
        "ts_server": ts_server,
        "session_id": request.session_id,
        "profile_hash": request.profile_hash,
        "corrections": {
            "capabilities": {
                "added": request.corrections.capabilities.added,
                "deleted": request.corrections.capabilities.deleted,
                "modified_level": [
                    {"name": m.name, "from": m.from_level, "to": m.to}
                    for m in request.corrections.capabilities.modified_level
                ],
            },
        },
        "stats": {
            "unmapped_count": request.stats.unmapped_count,
            "detected_capabilities_count": request.stats.detected_capabilities_count,
        },
        "meta": {
            "app_version": request.meta.app_version,
            "api_version": request.meta.api_version,
            "timestamp": request.meta.timestamp,
        },
    }

    _log_survival_metric(metric)
    logger.info(f"Correction logged: session={request.session_id}")

    return {"status": "logged", "session_id": request.session_id}
