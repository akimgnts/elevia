"""
profile.py - Routes FastAPI pour l'ingestion de profil
Sprint 12
Sprint 21 - Observability logging

Endpoint POST /profile/ingest_cv pour extraire un profil structuré depuis un CV.
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from ..utils.obs_logger import obs_log


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

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from profile import (
    CvIngestRequest,
    CvExtractionResponse,
    extract_profile_from_cv,
    ExtractionError,
    ProviderNotConfiguredError,
)
from semantic.profile_cache import cache_profile_text, compute_profile_hash
from compass.profile_structurer import structure_profile_text_v1
from api.utils.profile_summary_builder import build_profile_summary
from api.utils.profile_summary_store import store_profile_summary


logger = logging.getLogger(__name__)
router = APIRouter(tags=["profile"])


@router.post(
    "/ingest_cv",
    response_model=CvExtractionResponse,
    summary="Extrait un profil structuré depuis un CV",
    description="""
Prend un CV brut (texte) en entrée et retourne un profil structuré.

**Pipeline:**
1. Le CV est envoyé à un LLM pour extraction
2. La réponse LLM est validée par Pydantic (barrière anti-hallucination)
3. Seules les capacités du référentiel V0.1 sont acceptées

**Capacités reconnues (V0.1):**
- data_visualization: PowerBI, Tableau, Looker, Qlik...
- spreadsheet_logic: Excel, VBA, Google Sheets...
- crm_management: Salesforce, HubSpot, Zoho...
- programming_scripting: Python, SQL, JavaScript...
- project_management: Jira, Asana, Trello, Agile...

**Erreurs possibles:**
- 422: CV vide, JSON invalide, capacité hors référentiel
- 503: Provider LLM non configuré
""",
    responses={
        200: {
            "description": "Profil extrait avec succès",
            "content": {
                "application/json": {
                    "example": {
                        "candidate_info": {
                            "first_name": "Jean",
                            "last_name": "Dupont",
                            "email": "jean.dupont@example.com",
                            "years_of_experience": 5
                        },
                        "detected_capabilities": [
                            {
                                "name": "programming_scripting",
                                "level": "expert",
                                "score": 85,
                                "proofs": ["5 ans de Python"],
                                "tools_detected": ["Python", "SQL"]
                            }
                        ],
                        "languages": [
                            {"code": "fr", "level": "C2", "raw_text": "Français natif"}
                        ],
                        "education_summary": {
                            "level": "BAC+5",
                            "raw_text": "Master Data Science"
                        }
                    }
                }
            }
        },
        422: {
            "description": "Validation échouée (CV vide, JSON invalide, schéma non respecté)"
        },
        503: {
            "description": "Provider LLM non disponible"
        }
    }
)
async def ingest_cv(request: CvIngestRequest) -> CvExtractionResponse:
    """
    Extrait un profil structuré depuis le texte d'un CV.

    Le LLM propose, Pydantic garde la vérité.
    Toute capacité hors du référentiel V0.1 est rejetée.
    """
    run_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    # Vérification taille (déjà faite par Pydantic mais double check)
    if len(request.cv_text.strip()) < 10:
        obs_log("cv_ingested", run_id=run_id, status="error", error_code="CV_TOO_SHORT",
                duration_ms=int((time.time() - start_time) * 1000))
        raise HTTPException(
            status_code=422,
            detail="Le CV est trop court (minimum 10 caractères)"
        )

    try:
        # Appel au LLM
        raw_data = extract_profile_from_cv(request.cv_text)

        # Validation Pydantic (barrière anti-hallucination)
        validated = CvExtractionResponse.model_validate(raw_data)

        profile_hash = compute_profile_hash(validated.model_dump())
        cache_profile_text(profile_hash, request.cv_text)

        # ── Profile summary cache (deterministic) ────────────────────────────
        try:
            structured = structure_profile_text_v1(request.cv_text, debug=False)
            summary = build_profile_summary(structured)
            store_profile_summary(profile_hash, summary.model_dump())
            if os.getenv("ELEVIA_DEBUG_PROFILE_SUMMARY", "").strip().lower() in {"1", "true", "yes", "on"}:
                logger.info(
                    "PROFILE_SUMMARY_STORED profile_id=%s last_updated=%s",
                    profile_hash,
                    summary.last_updated,
                )
        except Exception as exc:
            logger.warning("[profile/ingest_cv] profile summary failed: %s", type(exc).__name__)

        duration_ms = int((time.time() - start_time) * 1000)
        obs_log("cv_ingested", run_id=run_id, status="success", duration_ms=duration_ms,
                extra={"capabilities_count": len(validated.detected_capabilities)})

        return validated

    except ProviderNotConfiguredError as e:
        logger.error(f"Provider LLM non configuré: {e}")
        obs_log("cv_ingested", run_id=run_id, status="error", error_code="PROVIDER_NOT_CONFIGURED",
                duration_ms=int((time.time() - start_time) * 1000))
        raise HTTPException(
            status_code=503,
            detail="Le service d'extraction n'est pas disponible. Contactez l'administrateur."
        )

    except ExtractionError as e:
        logger.error(f"Extraction échouée: {e}")
        logger.error(f"Raw LLM output: {e.raw_output}")
        obs_log("cv_ingested", run_id=run_id, status="error", error_code="EXTRACTION_FAILED",
                duration_ms=int((time.time() - start_time) * 1000))
        raise HTTPException(
            status_code=422,
            detail="L'extraction du CV a échoué. Le format de sortie n'est pas valide."
        )

    except ValidationError as e:
        logger.error(f"Validation Pydantic échouée: {e}")
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        _log_survival_metric({
            "type": "pydantic_reject",
            "ts_server": ts,
            "endpoint": "/profile/ingest_cv",
            "reason": str(e.errors()[0]["msg"]) if e.errors() else "unknown",
            "model": "CvExtractionResponse",
            "retry_used": False,
            "meta": {"api_version": "api@0.1.0", "timestamp": ts}
        })
        errors = []
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            errors.append(f"{loc}: {error['msg']}")
        raise HTTPException(
            status_code=422,
            detail={"message": "Le profil extrait ne respecte pas le schéma attendu", "errors": errors[:5]}
        )

    except Exception as e:
        logger.exception(f"Erreur inattendue lors de l'ingestion CV: {e}")
        raise HTTPException(
            status_code=500,
            detail="Une erreur inattendue s'est produite"
        )
