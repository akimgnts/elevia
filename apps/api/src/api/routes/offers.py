# DATASET SOURCE: Realistic Beta Catalog (Not real production extraction)
"""
offers.py - Routes FastAPI pour les offres VIE
Sprint 14 - VERROU #3 (Stabilization)
Sprint: Live Data Switch - Added /offers/catalog with SQLite + fallback
Sprint 15.1 - Data Quality + Hardened Contract
Sprint 21 - Observability logging

Endpoints:
- GET /offers/sample - Static sample offers (legacy)
- GET /offers/catalog - Live DB offers with static fallback

Anti-crash design:
- Lazy loading (file read on first request, not at import)
- Graceful degradation if file missing (returns empty list + warning header)
- MD5-based version header for cache validation
- SQLite timeout + fallback for catalog endpoint
- Explicit fallback_reason in meta for debugging
"""

import hashlib
import json
import logging
import sqlite3
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from ..utils.obs_logger import obs_log


# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================

class CatalogSource(str, Enum):
    """Valid source values for catalog filtering."""
    all = "all"
    france_travail = "france_travail"
    business_france = "business_france"


class FallbackReason(str, Enum):
    """Reasons why fallback to static data occurred."""
    EMPTY_DB = "EMPTY_DB"
    DB_LOCKED = "DB_LOCKED"
    DB_MISSING = "DB_MISSING"
    DB_ERROR = "DB_ERROR"

logger = logging.getLogger(__name__)
router = APIRouter(tags=["offers"])

# Path to sample offers file
SAMPLE_OFFERS_PATH = Path(__file__).parent.parent.parent.parent / "data" / "sample_vie_offers.json"

# Cache: (offers_list, version_hash)
_cache: Optional[Tuple[List[Dict[str, Any]], str]] = None


def _compute_version_hash(data: bytes) -> str:
    """Compute MD5 hash (first 8 chars) for versioning."""
    return hashlib.md5(data).hexdigest()[:8]


def _load_offers_lazy() -> Tuple[List[Dict[str, Any]], str]:
    """
    Lazy load offers from JSON file.
    Returns (offers_list, version_hash).
    Graceful fallback if file missing.
    """
    global _cache

    # Return cached if available
    if _cache is not None:
        return _cache

    # Try to load file
    if not SAMPLE_OFFERS_PATH.exists():
        logger.warning(f"WARNING: Sample offers file missing at {SAMPLE_OFFERS_PATH}")
        _cache = ([], "missing")
        return _cache

    try:
        raw_data = SAMPLE_OFFERS_PATH.read_bytes()
        offers = json.loads(raw_data.decode("utf-8"))
        version_hash = _compute_version_hash(raw_data)

        if not isinstance(offers, list):
            logger.warning(f"WARNING: Sample offers file is not a list, got {type(offers)}")
            _cache = ([], "invalid")
            return _cache

        logger.info(f"Loaded {len(offers)} offers from {SAMPLE_OFFERS_PATH} (v:{version_hash})")
        _cache = (offers, version_hash)
        return _cache

    except json.JSONDecodeError as e:
        logger.warning(f"WARNING: Invalid JSON in sample offers file: {e}")
        _cache = ([], "invalid")
        return _cache
    except Exception as e:
        logger.warning(f"WARNING: Failed to load sample offers: {e}")
        _cache = ([], "error")
        return _cache


@router.get(
    "/sample",
    summary="Get sample VIE offers",
    description="Returns a list of sample VIE offers for testing. Max 500 offers.",
)
async def get_sample_offers(
    limit: int = Query(default=200, ge=1, le=500, description="Number of offers to return (max 500)")
) -> JSONResponse:
    """
    Get sample VIE offers for beta testing.

    Returns up to `limit` offers from the sample dataset.
    Graceful fallback: returns empty list if file missing (does not crash).

    Headers:
    - X-Sample-Version: MD5 hash (8 chars) or "missing"/"invalid"/"error"
    """
    offers, version_hash = _load_offers_lazy()

    # Cap at requested limit
    result_offers = offers[:limit]

    response_data = {
        "total_available": len(offers),
        "returned": len(result_offers),
        "offers": result_offers,
    }

    return JSONResponse(
        content=response_data,
        headers={"X-Sample-Version": version_hash},
    )


# ============================================================================
# CATALOG ENDPOINT (Live Data Switch + Sprint 15 Data Quality)
# ============================================================================

from ..utils.text_cleaning import clean_text, make_display_text

# Path to SQLite database
DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "db" / "offers.db"


def _normalize_offer(raw: Dict[str, Any], source_hint: str = "unknown") -> Dict[str, Any]:
    """
    Transform raw offer data into OfferNormalized contract.

    Rules:
    - No fabricated values (no default country/company)
    - Text cleaning applied
    - Nullable fields are null, not empty strings with defaults
    """
    # Determine source
    source = raw.get("source", source_hint)
    if source not in ("france_travail", "business_france"):
        source = "unknown"

    # Get raw values
    raw_title = raw.get("title") or raw.get("intitule") or ""
    raw_desc = raw.get("description") or ""
    raw_company = raw.get("company") or raw.get("company_name") or None
    raw_city = raw.get("city") or raw.get("location_label") or None
    raw_country = raw.get("country") or None
    raw_pub_date = raw.get("publication_date") or None
    raw_duration = raw.get("contract_duration")
    raw_start = raw.get("start_date") or None

    # Clean text fields
    title = clean_text(raw_title)
    description = clean_text(raw_desc)
    display_description = make_display_text(raw_desc, max_len=800)

    # Validate contract_duration is int or null
    contract_duration = None
    if raw_duration is not None:
        try:
            contract_duration = int(raw_duration)
        except (ValueError, TypeError):
            contract_duration = None

    # Clean nullable strings (empty -> null)
    company = clean_text(raw_company) if raw_company else None
    city = clean_text(raw_city) if raw_city else None
    country = clean_text(raw_country) if raw_country else None

    # Build OfferNormalized
    return {
        "id": str(raw.get("id") or raw.get("offer_id") or ""),
        "source": source,
        "title": title,
        "description": description,
        "display_description": display_description,
        "publication_date": raw_pub_date,
        "company": company if company else None,
        "city": city if city else None,
        "country": country if country else None,
        "contract_duration": contract_duration,
        "start_date": raw_start,
    }


def _load_from_sqlite(
    limit: int,
    source: CatalogSource = CatalogSource.all
) -> Tuple[List[Dict[str, Any]], int, Optional[FallbackReason]]:
    """
    Load offers from SQLite database with source filtering.

    Args:
        limit: Max offers to return
        source: CatalogSource enum value

    Returns:
        (offers_list, total_count, fallback_reason)
        - fallback_reason is None if success (live-db)
        - fallback_reason is set if fallback needed
    """
    if not DB_PATH.exists():
        logger.info(f"[catalog] DB not found at {DB_PATH}")
        return [], 0, FallbackReason.DB_MISSING

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=2)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query with optional source filter
        source_val = source.value
        if source == CatalogSource.all:
            cursor.execute("SELECT COUNT(*) FROM fact_offers")
            total_count = cursor.fetchone()[0]

            cursor.execute("""
                SELECT id, source, title, description, company, city, country,
                       publication_date, contract_duration, start_date
                FROM fact_offers
                ORDER BY publication_date DESC NULLS LAST
                LIMIT ?
            """, (min(limit, 500),))
        else:
            cursor.execute("SELECT COUNT(*) FROM fact_offers WHERE source = ?", (source_val,))
            total_count = cursor.fetchone()[0]

            cursor.execute("""
                SELECT id, source, title, description, company, city, country,
                       publication_date, contract_duration, start_date
                FROM fact_offers
                WHERE source = ?
                ORDER BY publication_date DESC NULLS LAST
                LIMIT ?
            """, (source_val, min(limit, 500)))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            logger.info(f"[catalog] DB has 0 rows for source={source_val}")
            return [], total_count, FallbackReason.EMPTY_DB

        # Normalize each offer (ALWAYS applies clean_text/make_display_text)
        offers = []
        for row in rows:
            raw = {
                "id": row["id"],
                "source": row["source"],
                "title": row["title"],
                "description": row["description"],
                "company": row["company"],
                "city": row["city"],
                "country": row["country"],
                "publication_date": row["publication_date"],
                "contract_duration": row["contract_duration"],
                "start_date": row["start_date"],
            }
            offers.append(_normalize_offer(raw))

        logger.info(f"[catalog] Loaded {len(offers)} offers from SQLite (source={source_val}, total={total_count})")
        return offers, total_count, None  # None = success, no fallback needed

    except sqlite3.OperationalError as e:
        error_str = str(e).lower()
        if "locked" in error_str:
            logger.warning(f"[catalog] SQLite database locked: {e}")
            return [], 0, FallbackReason.DB_LOCKED
        logger.warning(f"[catalog] SQLite operational error: {e}")
        return [], 0, FallbackReason.DB_ERROR
    except Exception as e:
        logger.warning(f"[catalog] Unexpected error loading from DB: {e}")
        return [], 0, FallbackReason.DB_ERROR


def _normalize_fallback_offers(
    raw_offers: List[Dict[str, Any]],
    source_filter: CatalogSource = CatalogSource.all
) -> List[Dict[str, Any]]:
    """
    Normalize fallback offers and apply source filtering.

    Static sample offers are treated as "business_france" (VIE-like).
    ALWAYS applies _normalize_offer (clean_text/make_display_text).
    """
    normalized = []
    for raw in raw_offers:
        # Determine source for filtering
        offer_source = raw.get("source", "business_france")
        if offer_source not in ("france_travail", "business_france"):
            offer_source = "business_france"  # VIE-like static data

        # Apply source filter
        if source_filter != CatalogSource.all and offer_source != source_filter.value:
            continue

        # Normalize with source hint (ALWAYS applies cleaning)
        norm = _normalize_offer(raw, source_hint=offer_source)
        normalized.append(norm)

    return normalized


@router.get(
    "/catalog",
    summary="Get live offers catalog",
    description="""
Returns offers from the live database (France Travail + Business France).
Falls back to static sample data if database is unavailable.

**Query params:**
- `limit`: Max offers (1-500, default 200)
- `source`: Filter by source ("all", "france_travail", "business_france")

**Response:**
```json
{
  "offers": [...],
  "meta": {
    "total_available": int,
    "returned": int,
    "data_source": "live-db" | "static-fallback",
    "fallback_reason": null | "EMPTY_DB" | "DB_LOCKED" | "DB_MISSING" | "DB_ERROR"
  }
}
```

**Headers:**
- `X-Data-Source`: 'live-db' or 'static-fallback' (mirrors meta.data_source)

**Contract:** Returns OfferNormalized objects (see docs/contracts/offer_normalized.md)
""",
)
async def get_catalog_offers(
    limit: int = Query(default=200, ge=1, le=500, description="Number of offers to return (max 500)"),
    source: str = Query(default="all", description="Filter by source: all, france_travail, business_france"),
) -> JSONResponse:
    """
    Get offers from live database with static fallback.

    Priority:
    1. SQLite database (live data from France Travail / Business France)
    2. Static sample_vie_offers.json (fallback)

    Returns { offers, meta } with OfferNormalized contract. NEVER crashes.
    """
    run_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    # Validate source manually (returns 400, not 422)
    ALLOWED_SOURCES = {"all", "france_travail", "business_france"}
    source_clean = (source or "all").strip().lower()
    if source_clean not in ALLOWED_SOURCES:
        obs_log("catalog_fetch", run_id=run_id, status="error", error_code="INVALID_SOURCE",
                duration_ms=int((time.time() - start_time) * 1000))
        return JSONResponse(
            status_code=400,
            content={
                "error": "INVALID_SOURCE",
                "allowed": sorted(list(ALLOWED_SOURCES)),
            },
        )

    # Convert to enum for internal use
    source_enum = CatalogSource(source_clean)

    # Try live database first
    offers, total_count, fallback_reason = _load_from_sqlite(limit, source_enum)

    if fallback_reason is None and offers:
        # Success: live-db
        duration_ms = int((time.time() - start_time) * 1000)
        obs_log("catalog_fetch", run_id=run_id, status="success", duration_ms=duration_ms,
                extra={"data_source": "live-db", "returned": len(offers), "source_filter": source_clean})
        return JSONResponse(
            content={
                "offers": offers,
                "meta": {
                    "total_available": total_count,
                    "returned": len(offers),
                    "data_source": "live-db",
                    "fallback_reason": None,
                },
            },
            headers={"X-Data-Source": "live-db"},
        )

    # Fallback to static JSON
    logger.info(f"[catalog] Falling back to static sample data (source={source_clean}, reason={fallback_reason})")
    static_offers, version_hash = _load_offers_lazy()

    # Normalize and filter fallback offers (ALWAYS applies _normalize_offer)
    normalized = _normalize_fallback_offers(static_offers, source_enum)
    result_offers = normalized[:limit]

    duration_ms = int((time.time() - start_time) * 1000)
    obs_log("catalog_fetch", run_id=run_id, status="success", duration_ms=duration_ms,
            extra={"data_source": "static-fallback", "returned": len(result_offers),
                   "source_filter": source_clean,
                   "fallback_reason": fallback_reason.value if fallback_reason else None})

    return JSONResponse(
        content={
            "offers": result_offers,
            "meta": {
                "total_available": len(normalized),
                "returned": len(result_offers),
                "data_source": "static-fallback",
                "fallback_reason": fallback_reason.value if fallback_reason else None,
            },
        },
        headers={
            "X-Data-Source": "static-fallback",
            "X-Sample-Version": version_hash,
        },
    )
