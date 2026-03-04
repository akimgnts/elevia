"""
main.py - Application FastAPI Elevia
Sprint 7

Point d'entrée de l'API.
"""

import logging
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

# Charger .env AVANT tout import qui utilise les variables d'environnement
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

from fastapi import FastAPI
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request

logger = logging.getLogger(__name__)

from .middleware.request_id import RequestIdMiddleware
from .routes.health import router as health_router
from .routes.matching import router as matching_router
from .routes.metrics import router as metrics_router
from .routes.offers import router as offers_router
from .routes.profile import router as profile_router
from .routes.profile_baseline import router as profile_baseline_router
from .routes.profile_file import router as profile_file_router
from .routes.inbox import router as inbox_router
from .routes.applications import router as applications_router
from .routes.apply_pack import router as apply_pack_router
from .routes.debug_match import router as debug_router
from .routes.dev_tools import router as dev_tools_router
from .routes.profile_key_skills import router as profile_key_skills_router
from .routes.context import router as context_router
from .routes.documents import router as documents_router
from .routes.profile_structured import router as profile_structured_router
from .routes.profile_summary import router as profile_summary_router
from .routes.cluster_library_api import router as cluster_library_router
from .routes.analyze_recovery import router as analyze_recovery_router
from .routes.analyze_ai_quality import router as analyze_ai_quality_router
from documents.llm_client import is_llm_available


app = FastAPI(
    title="Elevia API",
    description="""
API de matching VIE pour Elevia Compass.

## Matching V1 (Sprint 6)
Moteur déterministe et explicable pour matcher des profils candidats avec des offres VIE.

**Caractéristiques:**
- Déterministe (mêmes inputs → mêmes outputs)
- Explicable (2-3 raisons factuelles max)
- Filtrage strict VIE (is_vie=True obligatoire)
- Seuil configurable (défaut: 80%)
""",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS pour dev local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Request ID: stamp every request with X-Request-Id header + request.state.request_id
app.add_middleware(RequestIdMiddleware)

# Routes
app.include_router(health_router)          # GET /health, GET /health/deps
app.include_router(matching_router, prefix="/v1")
app.include_router(metrics_router, prefix="/metrics")
app.include_router(offers_router, prefix="/offers")
app.include_router(profile_router, prefix="/profile")
app.include_router(profile_baseline_router)    # POST /profile/parse-baseline (no LLM)
app.include_router(profile_file_router)        # POST /profile/parse-file (multipart, no LLM)
app.include_router(inbox_router)
app.include_router(applications_router)
app.include_router(apply_pack_router)  # POST /apply-pack (baseline + optional LLM)
app.include_router(debug_router)  # DEV-only debug endpoints
app.include_router(dev_tools_router)  # DEV-only tools (guarded by ELEVIA_DEV_TOOLS=1)
app.include_router(profile_key_skills_router)  # POST /profile/key-skills (display-only ranking)
app.include_router(context_router)  # POST /context/*
app.include_router(documents_router)  # POST /documents/cv (CV Generator v1)
app.include_router(profile_structured_router)  # GET|POST /profile/structured (COMPASS D+)
app.include_router(profile_summary_router)  # GET /profile/summary (compact profile panel)
app.include_router(cluster_library_router)  # GET /cluster/library/* + POST /cluster/library/enrich/cv
app.include_router(analyze_recovery_router)  # POST /analyze/recover-skills (DEV-only)
app.include_router(analyze_ai_quality_router)  # POST /analyze/audit-ai-quality (DEV-only)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return a stable error shape for /analyze/recover-skills invalid payloads."""
    if request.url.path != "/analyze/recover-skills":
        return await request_validation_exception_handler(request, exc)
    request_id = getattr(request.state, "request_id", uuid.uuid4().hex[:8])
    return JSONResponse(
        status_code=400,
        content={
            "recovered_skills": [],
            "ai_available": False,
            "ai_error": "INVALID_REQUEST",
            "error_code": "INVALID_REQUEST",
            "error_message": "Invalid request payload",
            "cluster": "",
            "ignored_token_count": 0,
            "noise_token_count": 0,
            "error": {
                "code": "INVALID_REQUEST",
                "message": "Invalid request payload",
                "request_id": request_id,
            },
            "request_id": request_id,
        },
    )

# OBS: startup diagnostic (DEV-only, non-invasive)
_dev_tools_on = os.getenv("ELEVIA_DEV_TOOLS", "").lower() in {"1", "true", "yes"}
logger.info(
    "[startup] ELEVIA_DEV_TOOLS=%s → POST /dev/cv-delta %s",
    os.getenv("ELEVIA_DEV_TOOLS", "unset"),
    "ENABLED" if _dev_tools_on else "DISABLED (returns 403)",
)
logger.info(
    "[startup] OPENAI_API_KEY_present=%s",
    "true" if is_llm_available() else "false",
)


@app.get("/", tags=["root"])
async def root():
    """Root endpoint avec liens utiles."""
    return {
        "service": "Elevia API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "matching": "/v1/match",
        "profile_ingest": "/profile/ingest_cv"
    }
