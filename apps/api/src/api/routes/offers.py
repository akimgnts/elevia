"""
offers.py - Routes FastAPI pour les offres VIE

Endpoints:
- GET /offers/catalog - Live DB offers (BF: PostgreSQL clean_offers, FT: SQLite fact_offers)
- GET /offers/{offer_id}/detail - Single offer detail
"""

import json
import logging
import os
import socket
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
    NOT_FOUND = "NOT_FOUND"

logger = logging.getLogger(__name__)
router = APIRouter(tags=["offers"])

def _classify_postgres_exception(exc: Exception) -> str:
    message = str(exc).lower()
    if isinstance(exc, ModuleNotFoundError) and getattr(exc, "name", "") == "psycopg":
        return "MISSING_DRIVER"
    if isinstance(exc, socket.gaierror) or "nodename nor servname provided" in message or "failed to resolve host" in message:
        return "DB_DNS_ERROR"
    if "connection refused" in message:
        return "DB_CONNECTION_REFUSED"
    if "timeout expired" in message or "timed out" in message:
        return "DB_TIMEOUT"
    if "password authentication failed" in message:
        return "DB_AUTH_ERROR"
    return "DB_ERROR"


# ============================================================================
# CATALOG ENDPOINT
# ============================================================================

from ..utils.text_cleaning import clean_text, make_display_text
from ..utils.offer_skills import get_esco_skills_for_offer
from offer.offer_description_structurer import structure_offer_description
from compass.signal_layer import build_explain_payload_v1, get_signal_cfg
from compass.contracts import SkillRef
from compass.text_structurer import structure_offer_text_v1
from compass.offer.offer_intelligence import build_offer_intelligence
from compass.offer.offer_parse_pipeline import build_offer_canonical_representation
from compass.explainability.semantic_explanation_builder import build_semantic_explainability
from compass.scoring.scoring_v2 import build_scoring_v2
from compass.scoring.scoring_v3 import build_scoring_v3

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
    if source == CatalogSource.business_france:
        raise ValueError(
            "_load_from_sqlite must never be called for business_france — use _load_from_postgres"
        )

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


def _load_from_postgres(
    limit: int,
    source: CatalogSource = CatalogSource.all,
) -> Tuple[List[Dict[str, Any]], int, Optional[FallbackReason]]:
    """
    Load offers from PostgreSQL clean_offers table via DATABASE_URL.

    clean_offers schema differs from the old SQLite fact_offers:
    - primary offer identifier is external_id (e.g. "BF-242343"), not id
    - city column is named location
    - no contract_duration column (has contract_type TEXT instead)
    """
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        logger.error("[catalog] DATABASE_URL not set — Business France (clean_offers) unavailable")
        return [], 0, FallbackReason.DB_MISSING

    try:
        import psycopg
        conn = psycopg.connect(database_url, connect_timeout=5)
        source_val = source.value

        with conn.cursor() as cur:
            if source == CatalogSource.all:
                cur.execute("SELECT COUNT(*) FROM clean_offers")
                total_count = cur.fetchone()[0]
                cur.execute(
                    """
                    SELECT external_id, source, title, description, company,
                           location, country, publication_date, start_date
                    FROM clean_offers
                    ORDER BY publication_date DESC NULLS LAST
                    LIMIT %s
                    """,
                    (min(limit, 500),),
                )
            else:
                cur.execute(
                    "SELECT COUNT(*) FROM clean_offers WHERE source = %s",
                    (source_val,),
                )
                total_count = cur.fetchone()[0]
                cur.execute(
                    """
                    SELECT external_id, source, title, description, company,
                           location, country, publication_date, start_date
                    FROM clean_offers
                    WHERE source = %s
                    ORDER BY publication_date DESC NULLS LAST
                    LIMIT %s
                    """,
                    (source_val, min(limit, 500)),
                )
            rows = cur.fetchall()

        conn.close()

        if not rows:
            logger.info(f"[catalog] PostgreSQL clean_offers has 0 rows for source={source_val}")
            return [], total_count, FallbackReason.EMPTY_DB

        offers = []
        for row in rows:
            raw = {
                "id": row[0],                                          # external_id → offer id
                "source": row[1],
                "title": row[2],
                "description": row[3],
                "company": row[4],
                "city": row[5],                                        # location → city
                "country": row[6],
                "publication_date": str(row[7]) if row[7] else None,
                "contract_duration": None,                             # not stored in clean_offers
                "start_date": str(row[8]) if row[8] else None,
            }
            offers.append(_normalize_offer(raw))

        logger.info(
            f"[catalog] Loaded {len(offers)} offers from PostgreSQL "
            f"(source={source_val}, total={total_count})"
        )
        return offers, total_count, None

    except Exception as e:
        logger.error(f"[catalog] PostgreSQL error ({_classify_postgres_exception(e)}): {e}")
        return [], 0, FallbackReason.DB_ERROR


def _load_catalog_db_first(
    limit: int,
    source: CatalogSource,
) -> Tuple[List[Dict[str, Any]], int, str, Optional[FallbackReason]]:
    """
    Database-only catalog loading.

    Rules:
    - business_france: PostgreSQL clean_offers only
    - france_travail: SQLite fact_offers only
    - all: merge business_france from PostgreSQL + france_travail from SQLite
    """
    if source == CatalogSource.business_france:
        offers, total_count, failure = _load_from_postgres(limit, CatalogSource.business_france)
        if failure is not None:
            return [], total_count, "error", failure
        return offers, total_count, "live-db", None

    if source == CatalogSource.france_travail:
        offers, total_count, failure = _load_from_sqlite(limit, CatalogSource.france_travail)
        if failure is not None:
            return [], total_count, "error", failure
        return offers, total_count, "live-db", None

    bf_offers, bf_total, bf_failure = _load_from_postgres(limit, CatalogSource.business_france)
    ft_offers, ft_total, ft_failure = _load_from_sqlite(limit, CatalogSource.france_travail)

    if bf_failure is not None:
        return [], bf_total + ft_total, "error", bf_failure
    if ft_failure is not None and bf_offers:
        logger.warning(f"[catalog] France Travail unavailable ({ft_failure.value}), serving Business France only")
        combined = list(bf_offers)
        combined.sort(key=lambda offer: (str(offer.get("publication_date") or ""), str(offer.get("id") or "")), reverse=True)
        return combined[: min(limit, 500)], bf_total, "live-db-partial", None
    if ft_failure is not None:
        return [], bf_total + ft_total, "error", ft_failure

    combined = [*bf_offers, *ft_offers]
    combined.sort(key=lambda offer: (str(offer.get("publication_date") or ""), str(offer.get("id") or "")), reverse=True)
    return combined[: min(limit, 500)], bf_total + ft_total, "live-db", None


def _load_offer_detail_from_postgres(offer_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[FallbackReason]]:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        logger.error(f"[offer_detail] DATABASE_URL not set — Business France offer {offer_id} unavailable")
        return None, FallbackReason.DB_MISSING

    try:
        import psycopg

        with psycopg.connect(database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT external_id, source, title, description, company,
                           location, country, publication_date, start_date
                    FROM clean_offers
                    WHERE source = %s AND external_id = %s
                    LIMIT 1
                    """,
                    ("business_france", offer_id),
                )
                row = cur.fetchone()
        if row is None:
            return None, FallbackReason.NOT_FOUND
        return (
            {
                "id": row[0],
                "source": row[1],
                "title": row[2],
                "description": row[3],
                "company": row[4],
                "city": row[5],
                "country": row[6],
                "publication_date": str(row[7]) if row[7] else None,
                "contract_duration": None,
                "start_date": str(row[8]) if row[8] else None,
            },
            None,
        )
    except Exception as exc:
        logger.error(
            f"[offer_detail] PostgreSQL error for offer_id={offer_id} "
            f"({_classify_postgres_exception(exc)}): {exc}"
        )
        return None, FallbackReason.DB_ERROR


def _get_bf_skills_from_postgres(offer_id: str, limit: int = 12) -> List[str]:
    """
    Read ESCO-mapped skill labels for a Business France offer from PostgreSQL offer_skills.
    Returns empty list on any failure — skills are non-critical enrichment.
    """
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return []
    try:
        import psycopg

        with psycopg.connect(database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT skill FROM offer_skills
                    WHERE offer_id = %s AND source = %s AND skill_uri IS NOT NULL
                    ORDER BY skill ASC
                    LIMIT %s
                    """,
                    (offer_id, "business_france", limit),
                )
                rows = cur.fetchall()
        return [row[0] for row in rows]
    except Exception as exc:
        logger.warning(f"[offer_detail] BF skills fetch failed for {offer_id}: {exc}")
        return []


@router.get(
    "/catalog",
    summary="Get live offers catalog",
    description="""
Returns offers from the live databases only.

Business France is strict database-first:
- `source=business_france` reads only from PostgreSQL `clean_offers`
- `source=france_travail` reads from SQLite `fact_offers`
- `source=all` merges the two database-backed sources

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
    "data_source": "live-db",
    "fallback_reason": null
  }
}
```

**Headers:**
- `X-Data-Source`: 'live-db'

**Contract:** Returns OfferNormalized objects (see docs/contracts/offer_normalized.md)
""",
)
def get_catalog_offers(
    limit: int = Query(default=200, ge=1, le=500, description="Number of offers to return (max 500)"),
    source: str = Query(default="all", description="Filter by source: all, france_travail, business_france"),
) -> JSONResponse:
    """
    Get offers from the live databases only.

    Business France is PostgreSQL-only; France Travail remains SQLite-backed.
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

    offers, total_count, data_source, failure_reason = _load_catalog_db_first(limit, source_enum)

    if failure_reason is None:
        duration_ms = int((time.time() - start_time) * 1000)
        obs_log("catalog_fetch", run_id=run_id, status="success", duration_ms=duration_ms,
                extra={"data_source": data_source, "returned": len(offers), "source_filter": source_clean})
        return JSONResponse(
            content={
                "offers": offers,
                "meta": {
                    "total_available": total_count,
                    "returned": len(offers),
                    "data_source": data_source,
                    "fallback_reason": None,
                },
            },
            headers={"X-Data-Source": data_source},
        )

    duration_ms = int((time.time() - start_time) * 1000)
    error_code = failure_reason.value if failure_reason else "DB_ERROR"
    detail = None
    if source_enum in (CatalogSource.business_france, CatalogSource.all):
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            detail = "DATABASE_URL_MISSING"
        else:
            try:
                import psycopg  # noqa: F401
            except ModuleNotFoundError:
                detail = "MISSING_DRIVER"
    obs_log(
        "catalog_fetch",
        run_id=run_id,
        status="error",
        error_code=error_code,
        duration_ms=duration_ms,
        extra={"source_filter": source_clean, "detail": detail},
    )

    return JSONResponse(
        status_code=503,
        content={"error": "CATALOG_UNAVAILABLE", "reason": error_code, "source": source_clean, "detail": detail},
        headers={"X-Data-Source": "unavailable"},
    )


# ============================================================================
# OFFER DETAIL ENDPOINT
# ============================================================================

@router.get(
    "/{offer_id}/detail",
    summary="Get structured offer detail",
    description="""
Return a single offer with deterministic structured description sections.

**Structured sections (description_structured):**
- `summary`: Short intro ≤ 600 chars
- `missions`: Up to 8 bullet points
- `profile`: Up to 6 profile requirements
- `competences`: Up to 12 skills (ESCO preferred)
- `context`: Company/team context ≤ 300 chars
- `has_headings`: Whether heading-based parsing was used
- `source`: "structured" | "fallback"

Returns 404 if offer not found in the database.
""",
)
def get_offer_detail(
    offer_id: str,
    profile_role_block: Optional[str] = Query(default=None),
    profile_secondary_role_blocks: Optional[List[str]] = Query(default=None),
    profile_domains: Optional[List[str]] = Query(default=None),
    profile_signals: Optional[List[str]] = Query(default=None),
    profile_summary: Optional[str] = Query(default=None),
    matching_score: Optional[float] = Query(default=None),
) -> JSONResponse:
    """
    Fetch one offer by ID and return it with structured description sections.

    Deterministic: same input → same output.
    No LLM calls. ESCO skills preferred for competences section.
    """
    start_time = time.time()

    raw: Dict[str, Any]
    esco_skills: List[str] = []
    is_business_france = offer_id.upper().startswith("BF-")

    if is_business_france:
        raw, failure = _load_offer_detail_from_postgres(offer_id)
        if failure == FallbackReason.NOT_FOUND:
            return JSONResponse(status_code=404, content={"error": "NOT_FOUND", "offer_id": offer_id})
        if failure is not None or raw is None:
            obs_log("offer_detail_fetch", status="error", error_code=(failure.value if failure else "DB_ERROR"),
                    extra={"offer_id": offer_id, "source": "business_france"})
            return JSONResponse(status_code=503, content={"error": "DB_ERROR", "offer_id": offer_id})
        esco_skills = _get_bf_skills_from_postgres(offer_id)
    else:
        if not DB_PATH.exists():
            obs_log("offer_detail_fetch", status="error", error_code="DB_MISSING",
                    extra={"offer_id": offer_id})
            return JSONResponse(status_code=404, content={"error": "NOT_FOUND", "offer_id": offer_id})

        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=2)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, source, title, description, company, city, country,
                       publication_date, contract_duration, start_date
                FROM fact_offers
                WHERE id = ?
            """, (offer_id,))
            row = cursor.fetchone()

            if row is None:
                conn.close()
                return JSONResponse(status_code=404, content={"error": "NOT_FOUND", "offer_id": offer_id})

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

            # Fetch ESCO skills for this offer
            esco_skills = get_esco_skills_for_offer(conn, offer_id, limit=12)
            conn.close()

        except sqlite3.OperationalError as e:
            logger.warning(f"[offer_detail] SQLite error for offer_id={offer_id}: {e}")
            return JSONResponse(status_code=503, content={"error": "DB_ERROR"})

    # Normalize offer fields
    normalized = _normalize_offer(raw)
    raw_description = raw.get("description") or ""

    canonical_offer = build_offer_canonical_representation(
        normalized | {"skills_display": [{"label": s} for s in esco_skills], "skills": esco_skills}
    )
    description_structured = canonical_offer["description_structured"]
    description_structured_v1 = canonical_offer["description_structured_v1"]

    # Compass explain_v1_full (Part A — standalone view, no profile match)
    offer_skills_refs = [SkillRef(uri=None, label=s) for s in esco_skills]
    _cfg = get_signal_cfg()
    explain_v1_full = build_explain_payload_v1(
        score_core=0.0,
        matched_skills=[],
        offer_skills=offer_skills_refs,
        offer_text=raw_description,
        domain_bucket="out",
        idf_map={},
        cfg=_cfg,
        # No cluster_idf_table in standalone view (no catalog available here)
        offer_cluster=None,
        cluster_idf_table=None,
    )
    offer_intelligence = build_offer_intelligence(
        offer=normalized | {"skills_display": [{"label": s} for s in esco_skills], "skills": esco_skills},
        description_structured=description_structured,
        description_structured_v1=description_structured_v1,
        canonical_offer=canonical_offer,
    )
    semantic_explainability = None
    scoring_v2 = None
    scoring_v3 = None
    if profile_role_block or profile_domains or profile_signals or profile_summary:
        profile_intelligence = {
            "dominant_role_block": profile_role_block or "",
            "secondary_role_blocks": list(profile_secondary_role_blocks or []),
            "dominant_domains": list(profile_domains or []),
            "top_profile_signals": list(profile_signals or []),
            "profile_summary": profile_summary or "",
        }
        semantic_explainability = build_semantic_explainability(
            profile_intelligence=profile_intelligence,
            offer_intelligence=offer_intelligence,
            explanation=None,
        )
        if matching_score is not None:
            scoring_v2 = build_scoring_v2(
                profile_intelligence=profile_intelligence,
                offer_intelligence=offer_intelligence,
                semantic_explainability=semantic_explainability,
                matching_score=matching_score,
            )
            scoring_v3 = build_scoring_v3(
                profile_intelligence=profile_intelligence,
                offer_intelligence=offer_intelligence,
                semantic_explainability=semantic_explainability,
                matching_score=matching_score,
                explanation=None,
            )

    duration_ms = int((time.time() - start_time) * 1000)
    obs_log(
        "OFFER_DESCRIPTION_STRUCTURED",
        status="ok",
        duration_ms=duration_ms,
        extra={
            "offer_id": offer_id,
            "source": description_structured["source"],
            "has_headings": description_structured["has_headings"],
            "missions_count": len(description_structured.get("missions", [])),
            "profile_count": len(description_structured.get("profile", [])),
            "competences_count": len(description_structured.get("competences", [])),
            "used_esco_skills": len(esco_skills) > 0,
            "esco_skills_count": len(esco_skills),
            "structurer_v1_tools": len(description_structured_v1.tools_stack),
            "explain_v1_tool_notes": len(explain_v1_full.tool_notes),
        },
    )

    return JSONResponse(content={
        **normalized,
        "description_structured": description_structured,
        "description_structured_v1": description_structured_v1.model_dump(),
        "explain_v1_full": explain_v1_full.model_dump(),
        "offer_intelligence": offer_intelligence,
        "semantic_explainability": semantic_explainability,
        "scoring_v2": scoring_v2,
        "scoring_v3": scoring_v3,
    })
