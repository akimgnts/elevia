"""
main.py - Application FastAPI Elevia
Sprint 7

Point d'entrée de l'API.
"""

from pathlib import Path
from dotenv import load_dotenv

# Charger .env AVANT tout import qui utilise les variables d'environnement
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.matching import router as matching_router
from .routes.metrics import router as metrics_router
from .routes.offers import router as offers_router
from .routes.profile import router as profile_router
from .routes.inbox import router as inbox_router


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

# Routes
app.include_router(matching_router, prefix="/v1")
app.include_router(metrics_router, prefix="/metrics")
app.include_router(offers_router, prefix="/offers")
app.include_router(profile_router, prefix="/profile")
app.include_router(inbox_router)


@app.get("/health", tags=["health"])
async def health_check():
    """Healthcheck endpoint."""
    return {"status": "ok"}


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
