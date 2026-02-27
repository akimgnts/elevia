"""
health.py — Health and dependency check endpoints.

GET /health        → quick liveness probe
GET /health/deps   → dependency readiness probe
"""
import importlib
import logging
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Request

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.utils.env import get_llm_api_key

try:
    from ...esco.loader import esco_index_stats
    from ...profile.esco_aliases import alias_stats as _alias_stats
except ImportError:
    esco_index_stats = importlib.import_module("esco.loader").esco_index_stats
    _alias_stats = importlib.import_module("profile.esco_aliases").alias_stats

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


def _check_aliases() -> Dict[str, Any]:
    """Check ESCO alias table: existence and count."""
    try:
        stats = _alias_stats()
        return stats
    except Exception as exc:
        return {"status": "error", "alias_count": 0, "error": str(exc)}


def _check_llm() -> Dict[str, Any]:
    """Check whether LLM key is configured (optional dependency)."""
    key_present = bool(get_llm_api_key())
    return {
        "status": "ok" if key_present else "missing",
        "provider": "openai",
        "key_present": key_present,
    }


def _check_uri_collapse() -> Dict[str, Any]:
    """Signal URI-collapse readiness (deterministic, local-only)."""
    return {
        "status": "ok",
        "mode": "uri",
        "version": "v0",
        "notes": "collapse before scoring",
    }


@router.get("/health/deps")
async def health_deps(request: Request):
    """Readiness probe — checks data dependencies."""
    request_id = getattr(request.state, "request_id", "n/a")

    deps = {
        "offers_db": _check_offers_db(),
        "esco": _check_esco(),
        "esco_aliases": _check_aliases(),
        "alias": _check_aliases(),
        "weights": _check_weights(),
        "llm": _check_llm(),
    }
    deps["esco"]["uri_collapse"] = _check_uri_collapse()

    all_ok = all(
        v.get("status") == "ok" or v.get("ok")
        for k, v in deps.items()
        if k != "llm"
    )

    return {
        "status": "ok" if all_ok else "degraded",
        "deps": deps,
        "request_id": request_id,
    }
