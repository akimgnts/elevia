"""
health.py — Health and dependency check endpoints.

GET /health        → quick liveness probe
GET /health/deps   → dependency readiness probe
"""
import logging
import sqlite3
import subprocess
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Request

from esco.loader import esco_index_stats

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

# ── Paths ──────────────────────────────────────────────────────────────────────
_API_ROOT = Path(__file__).parent.parent.parent.parent  # apps/api/
_DB_PATH = _API_ROOT / "data" / "db" / "offers.db"
_ESCO_DIR = _API_ROOT / "data" / "esco" / "v1_2_1" / "fr"
# Offers fixture (static fallback — always present)
_OFFERS_FIXTURE = _API_ROOT / "fixtures" / "offers" / "vie_catalog.json"


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2,
            cwd=str(_API_ROOT),
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


# ── /health ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health(request: Request):
    """Liveness probe — returns quickly, never touches data."""
    request_id = getattr(request.state, "request_id", "n/a")
    return {
        "status": "ok",
        "service": "api",
        "version": _git_sha(),
        "request_id": request_id,
    }


# ── /health/deps ───────────────────────────────────────────────────────────────

def _check_offers_db() -> Dict[str, Any]:
    """Check SQLite offers DB: existence and reachability.
    The live 'offers' table is optional — inbox falls back to fixtures.
    We check that the DB is reachable and has the 'offer_decisions' table.
    """
    if not _DB_PATH.exists():
        # Fall back to fixture existence
        if _OFFERS_FIXTURE.exists():
            return {"ok": True, "source": "fixture", "note": "no live DB, fixture present"}
        return {"ok": False, "error": "offers.db not found and no fixture"}

    try:
        conn = sqlite3.connect(str(_DB_PATH), timeout=1)
        # Check DB is reachable; prefer offer_decisions (always exists), offer count optional
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        has_decisions = "offer_decisions" in tables
        has_offers = "offers" in tables
        return {
            "ok": True,
            "source": "sqlite",
            "has_offer_decisions": has_decisions,
            "has_offers_table": has_offers,
            "note": "inbox uses fixture catalog (no live offers table required)",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _check_esco() -> Dict[str, Any]:
    """Check ESCO resource directory and index readiness."""
    stats = esco_index_stats()
    skills_index_size = int(stats.get("skills_index_size", 0) or 0)
    collections_loaded = int(stats.get("collections_loaded", 0) or 0)

    if skills_index_size <= 0:
        return {
            "status": "fail",
            "skills_index_size": skills_index_size,
            "collections_loaded": collections_loaded,
            "reason": stats.get("error") or "ESCO index empty",
            "data_path": stats.get("data_path"),
        }

    return {
        "status": "ok",
        "skills_index_size": skills_index_size,
        "collections_loaded": collections_loaded,
        "data_path": stats.get("data_path"),
    }


def _check_weights() -> Dict[str, Any]:
    """Check weights / IDF data. IDF is computed from offers at runtime — no static files needed."""
    # Static weights not required; offers fixture is the source of truth.
    if _OFFERS_FIXTURE.exists():
        return {"ok": True, "note": "IDF computed from offers at runtime"}
    return {"ok": False, "error": "offers fixture missing — IDF source unavailable"}


@router.get("/health/deps")
async def health_deps(request: Request):
    """Readiness probe — checks data dependencies."""
    request_id = getattr(request.state, "request_id", "n/a")

    deps = {
        "offers_db": _check_offers_db(),
        "esco": _check_esco(),
        "weights": _check_weights(),
    }

    all_ok = all(v.get("status") == "ok" or v.get("ok") for v in deps.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "deps": deps,
        "request_id": request_id,
    }
