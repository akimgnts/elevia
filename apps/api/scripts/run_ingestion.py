#!/usr/bin/env python3
"""
run_ingestion.py - Autonomous Ingestion Orchestrator
Sprint 19 - Autonomie technique ingestion
Sprint 20 - Business France fallback on cached raw
Sprint 20.1 - BF fallback survival patch (hardened cache)

Production-grade orchestrator with:
- JSON structured logging (stdout, Railway compatible)
- Slack webhook alerting on failure
- Post-run sanity checks
- Proper exit codes for CRON monitoring
- Business France fallback to cached raw on API failure (Sprint 20)
- Anti-poisoning, atomic writes, staleness tracking (Sprint 20.1)

Usage:
    python scripts/run_ingestion.py

Environment variables:
    DATA_DIR: Override data directory (default: /data for Railway, ./data for local)
    SLACK_WEBHOOK_URL: Slack webhook for failure alerts (optional)
    FT_CLIENT_ID: France Travail API client ID
    FT_CLIENT_SECRET: France Travail API client secret
    BF_USE_SAMPLE: Set to "1" to use sample file instead of live API

CRON (Railway):
    0 2 * * *  # Daily at 02:00 UTC

Resilience (Sprint 20 + 20.1):
    - If Business France API fails, falls back to most recent cached raw JSONL
    - Anti-poisoning: never overwrite valid cache with invalid/empty data
    - Atomic writes: tmp + fsync + replace pattern
    - Staleness alerts: warning >24h, critical >72h
    - Pipeline continues as long as total_offers > 0
    - Exit code 1 ONLY if total_offers == 0 or DB write fails
"""

import argparse
import json
import os
import os
import sqlite3
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, List
from uuid import uuid4

try:
    import requests
except ImportError:
    print(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "job_name": "ingestion_pipeline",
        "run_id": "INIT_FAILED",
        "step": "init",
        "status": "error",
        "error": "requests library not installed"
    }))
    sys.exit(1)


# Add src to path for shared utilities
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.utils.offer_skills import ensure_offer_skills_table
from api.utils.raw_offers_pg import persist_raw_offers
from api.utils.rome_link import get_offer_rome_link, get_rome_competences_for_rome_codes
from esco.extract import extract_raw_skills_from_offer
from matching.extractors import normalize_skill_label
from esco.mapper import map_skill

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Detect environment: Railway uses /data volume, local uses ./data
if os.path.exists("/data"):
    DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
else:
    DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent.parent / "data"))

DB_PATH = DATA_DIR / "db" / "offers.db"
RAW_FT_DIR = DATA_DIR / "raw" / "france_travail"
RAW_BF_DIR = DATA_DIR / "raw" / "business_france"

# Slack webhook (optional)
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

# France Travail API
FT_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
FT_API_BASE = "https://api.francetravail.io/partenaire"
FT_SCOPES = "api_offresdemploiv2 o2dsoffre"

# Business France config — Option A
# BF_USE_SAMPLE default is "0" (LIVE). Set to "1" for explicit SAMPLE mode.
# STOP: default was "1" (silent sample) — fixed to "0" (explicit LIVE required)
_BF_USE_SAMPLE_ENV = os.environ.get("BF_USE_SAMPLE", "0")
BF_USE_SAMPLE = _BF_USE_SAMPLE_ENV == "1"
# BF_SOURCE: "LIVE" | "SAMPLE" | "CACHE" — explicit, never ambiguous
BF_SOURCE = os.environ.get("BF_SOURCE", "SAMPLE" if BF_USE_SAMPLE else "LIVE").upper()
if BF_SOURCE not in ("LIVE", "SAMPLE", "CACHE"):
    BF_SOURCE = "LIVE"

SAMPLE_FILE = DATA_DIR / "sample_vie_offers.json"
BF_CACHE_FILE = RAW_BF_DIR / "bf_cache.jsonl"  # Single cache file for atomic ops

# Import hardened cache utilities (Sprint 20.1)
from bf_cache import (
    validate_offers_minimal,
    atomic_write_jsonl,
    read_jsonl_best_effort,
    cache_age_hours,
    get_staleness_level,
    CACHE_WARNING_HOURS,
    CACHE_CRITICAL_HOURS,
)


# ==============================================================================
# STRUCTURED LOGGING
# ==============================================================================

class StructuredLogger:
    """JSON structured logger for Railway/stdout."""

    def __init__(self, job_name: str, run_id: str):
        self.job_name = job_name
        self.run_id = run_id

    def log(
        self,
        step: str,
        status: str,
        duration_ms: Optional[int] = None,
        offers_processed: Optional[int] = None,
        error: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Emit a structured log entry to stdout."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "job_name": self.job_name,
            "run_id": self.run_id,
            "step": step,
            "status": status,
            "duration_ms": duration_ms,
            "offers_processed": offers_processed,
            "error": error,
        }
        if extra:
            entry.update(extra)

        # Remove None values for cleaner logs
        entry = {k: v for k, v in entry.items() if v is not None}

        print(json.dumps(entry), flush=True)
        return entry


# ==============================================================================
# ALERTING
# ==============================================================================

def send_slack_alert(run_id: str, step: str, error: str) -> bool:
    """
    Send failure alert to Slack webhook.

    Returns True if alert sent successfully, False otherwise.
    """
    if not SLACK_WEBHOOK_URL:
        return False

    payload = {
        "text": f"❌ Elevia ingestion failed\nrun_id={run_id}\nstep={step}\nerror={error}"
    }

    try:
        r = requests.post(
            SLACK_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        return r.status_code == 200
    except Exception:
        return False


# ==============================================================================
# FRANCE TRAVAIL INGESTION
# ==============================================================================

def ingest_france_travail(logger: StructuredLogger) -> int:
    """
    Fetch and ingest France Travail offers.

    Returns number of offers ingested.
    """
    start_time = time.time()

    client_id = os.environ.get("FT_CLIENT_ID", "")
    client_secret = os.environ.get("FT_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        logger.log("scrape_france_travail", "error", error="FT_CLIENT_ID or FT_CLIENT_SECRET not set")
        return 0

    # Get OAuth token
    try:
        r = requests.post(
            FT_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": FT_SCOPES,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )

        if r.status_code != 200:
            logger.log("scrape_france_travail", "error", error=f"Token request failed: HTTP {r.status_code}")
            return 0

        token = r.json().get("access_token")
        if not token:
            logger.log("scrape_france_travail", "error", error="No access_token in response")
            return 0

    except Exception as e:
        logger.log("scrape_france_travail", "error", error=f"Token request failed: {e}")
        return 0

    # Fetch offers
    try:
        url = f"{FT_API_BASE}/offresdemploi/v2/offres/search"
        r = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"range": "0-149"},
            timeout=30,
        )

        if r.status_code not in (200, 206):
            logger.log("scrape_france_travail", "error", error=f"API returned HTTP {r.status_code}")
            return 0

        offers = r.json().get("resultats", [])

        if not offers:
            logger.log("scrape_france_travail", "success", offers_processed=0,
                       duration_ms=int((time.time() - start_time) * 1000))
            return 0

    except Exception as e:
        logger.log("scrape_france_travail", "error", error=f"API request failed: {e}")
        return 0

    # Write raw JSONL
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat()
    date_str = now.strftime("%Y-%m-%d")

    RAW_FT_DIR.mkdir(parents=True, exist_ok=True)
    raw_file = RAW_FT_DIR / f"{date_str}.jsonl"

    with open(raw_file, "a", encoding="utf-8") as f:
        for offer in offers:
            record = {
                "source": "france_travail",
                "fetched_at": timestamp,
                "payload": offer,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    pg_result = persist_raw_offers("france_travail", offers, timestamp)
    if pg_result.error:
        logger.log(
            "persist_raw_offers_pg",
            "warning",
            error=pg_result.error,
            offers_processed=pg_result.persisted,
            extra={"source": "france_travail"},
        )
    else:
        logger.log(
            "persist_raw_offers_pg",
            "success",
            offers_processed=pg_result.persisted,
            extra={"source": "france_travail"},
        )

    # Persist to SQLite
    count = persist_ft_offers(offers, timestamp)

    duration_ms = int((time.time() - start_time) * 1000)
    logger.log("scrape_france_travail", "success", duration_ms=duration_ms, offers_processed=count)

    return count


def persist_ft_offers(offers: list, timestamp: str) -> int:
    """Persist France Travail offers to SQLite."""
    ensure_db_exists()

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    cursor = conn.cursor()
    count = 0

    try:
        for offer in offers:
            raw_id = offer.get("id", "")
            offer_id = f"FT-{raw_id}" if raw_id else f"FT-{hash(json.dumps(offer, sort_keys=True))}"

            title = offer.get("intitule", "Sans titre")
            description = offer.get("description", "")

            entreprise = offer.get("entreprise", {})
            company = entreprise.get("nom") or None

            lieu = offer.get("lieuTravail", {})
            city = lieu.get("libelle") or None
            country = "France"

            publication_date = offer.get("dateCreation") or offer.get("dateActualisation")
            payload_json = json.dumps(offer, ensure_ascii=False)

            cursor.execute("""
                INSERT OR REPLACE INTO fact_offers
                (id, source, title, description, company, city, country,
                 publication_date, contract_duration, start_date, payload_json, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (offer_id, "france_travail", title, description, company, city, country,
                  publication_date, None, None, payload_json, timestamp))
            count += 1

            # ------------------------------------------------------------------
            # Skills enrichment (read-only additive)
            # ------------------------------------------------------------------
            # ROME competences (if available)
            rome_link = get_offer_rome_link(conn, offer_id)
            if rome_link and rome_link.get("rome_code"):
                rome_map = get_rome_competences_for_rome_codes(conn, [rome_link["rome_code"]], limit_per_rome=3)
                rome_competences = rome_map.get(rome_link["rome_code"], [])
                rome_skills = [
                    normalize_skill_label(c["competence_label"])
                    for c in rome_competences
                    if c.get("competence_label")
                ]
                rome_skills = [s for s in rome_skills if s]
                if rome_skills:
                    _insert_offer_skills(
                        cursor, offer_id, _map_labels_to_uris(rome_skills), "rome", timestamp
                    )

            skills_from_payload = _extract_ft_skills(offer)
            if skills_from_payload:
                _insert_offer_skills(
                    cursor,
                    offer_id,
                    _map_labels_to_uris(skills_from_payload),
                    "france_travail",
                    timestamp,
                )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return count


# ==============================================================================
# BUSINESS FRANCE INGESTION (Sprint 20.1 - Hardened fallback)
# ==============================================================================

def scrape_bf_live(logger: StructuredLogger) -> tuple[list, Optional[str]]:
    """
    Try to scrape fresh Business France data.

    Sprint 20.1: Returns offers WITHOUT writing cache yet.
    Cache write happens only after validation in ingest_business_france.

    Returns:
        (offers_list, error_message)
        - If success: (offers, None)
        - If failure: ([], error_message)
    """
    # In sample mode, load from sample file
    if BF_USE_SAMPLE:
        if not SAMPLE_FILE.exists():
            return [], f"Sample file not found: {SAMPLE_FILE}"

        try:
            with open(SAMPLE_FILE, "r", encoding="utf-8") as f:
                offers = json.load(f)

            if not isinstance(offers, list):
                return [], "Sample file is not a list"

            return offers, None

        except json.JSONDecodeError as e:
            return [], f"JSONDecodeError: {e}"
        except Exception as e:
            return [], f"Error reading sample: {e}"

    # Live API mode (not implemented - would require actual BF API access)
    return [], "Live BF API not configured (BF_USE_SAMPLE=0 but no API available)"


def load_bf_from_cache(logger: StructuredLogger) -> tuple[list, Optional[Path], Optional[float]]:
    """
    Load Business France offers from cache with validation.

    Sprint 20.1: Uses read_jsonl_best_effort for safe reading,
    validates offers, and computes staleness.

    Returns:
        (offers_list, cache_file_path, cache_age_hours)
    """
    # Try the single cache file first (Sprint 20.1 pattern)
    if BF_CACHE_FILE.exists():
        offers, valid_count, skipped = read_jsonl_best_effort(BF_CACHE_FILE, min_valid=1)
        age_hours = cache_age_hours(BF_CACHE_FILE)

        if skipped > 0:
            logger.log("load_bf_cache", "warning",
                       extra={"skipped_lines": skipped, "valid_count": valid_count})

        if offers and validate_offers_minimal(offers):
            return offers, BF_CACHE_FILE, age_hours

    # Fallback: try legacy per-run files (backwards compatibility)
    if RAW_BF_DIR.exists():
        raw_files = [f for f in RAW_BF_DIR.glob("*.jsonl") if f.name != "bf_cache.jsonl"]
        if raw_files:
            raw_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            legacy_file = raw_files[0]

            offers, valid_count, skipped = read_jsonl_best_effort(legacy_file, min_valid=1)
            age_hours = cache_age_hours(legacy_file)

            if offers and validate_offers_minimal(offers):
                return offers, legacy_file, age_hours

    return [], None, None


def ingest_business_france(logger: StructuredLogger, bf_source: str) -> int:
    """
    Option A — launcher pattern for Business France.

    One True Path:
      1. scrape_business_france_azure.py  →  raw JSONL (LIVE only)
      2. ingest_business_france.py --path <raw> →  normalize + UPSERT DB

    bf_source: "LIVE" | "SAMPLE" | "CACHE"
      - LIVE   : scrape fresh data from Civiweb Azure API
      - SAMPLE : reuse latest existing raw JSONL (explicit, never silent)
      - CACHE  : fallback to latest existing raw JSONL after scrape failure

    normalization_source_of_truth = ingest_business_france.py (NEVER here)
    id_strategy = BF-<native_id> (NEVER hash())
    """
    start_time = time.time()
    SCRIPTS_DIR = Path(__file__).parent

    # ── OBS: BF_INGEST_START ─────────────────────────────────────────────────
    logger.log("BF_INGEST_START", "started", extra={
        "bf_source": bf_source,
        "db_path": str(DB_PATH),
        "raw_dir": str(RAW_BF_DIR),
        "catalog_source": "RAW",
    })

    raw_file_path: Optional[Path] = None

    # ── Step 1: Scrape (LIVE) or reuse existing raw JSONL (SAMPLE / CACHE) ──
    if bf_source == "LIVE":
        scraper = SCRIPTS_DIR / "scrape_business_france_azure.py"
        logger.log("BF_SCRAPE_START", "started", extra={
            "bf_source": "LIVE",
            "catalog_source": "RAW",
        })
        env = {**os.environ}
        env.setdefault("BF_AZURE_SKIP_DETAILS", "1")

        try:
            result = subprocess.run(
                [sys.executable, str(scraper)],
                env=env,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            logger.log("BF_SCRAPE_SUMMARY", "error",
                       error="Scraper timeout (300s) — falling back to CACHE",
                       extra={"bf_source": "LIVE"})
            bf_source = "CACHE"
            result = None

        if result is not None and result.returncode == 0:
            raw_files = sorted(
                RAW_BF_DIR.glob("bf_azure_*.jsonl"),
                key=lambda f: f.stat().st_mtime, reverse=True,
            ) if RAW_BF_DIR.exists() else []
            if raw_files:
                raw_file_path = raw_files[0]
                logger.log("BF_SCRAPE_SUMMARY", "success", extra={
                    "bf_source": "LIVE",
                    "raw_file": raw_file_path.name,
                    "catalog_source": "RAW",
                })
            else:
                logger.log("BF_SCRAPE_SUMMARY", "error",
                           error="Scraper exited 0 but no raw file found — CACHE fallback",
                           extra={"bf_source": "LIVE"})
                bf_source = "CACHE"
        elif result is not None:
            logger.log("BF_SCRAPE_SUMMARY", "error",
                       error=f"Scraper exited {result.returncode} — CACHE fallback",
                       extra={"bf_source": "LIVE"})
            bf_source = "CACHE"

    # SAMPLE / CACHE: use latest existing raw JSONL (no new API calls)
    if raw_file_path is None and RAW_BF_DIR.exists():
        raw_files = sorted(
            RAW_BF_DIR.glob("bf_azure_*.jsonl"),
            key=lambda f: f.stat().st_mtime, reverse=True,
        )
        if raw_files:
            raw_file_path = raw_files[0]
            log_status = "success" if bf_source == "SAMPLE" else "fallback"
            logger.log("BF_SCRAPE_SUMMARY", log_status, extra={
                "bf_source": bf_source,
                "raw_file": raw_file_path.name,
                "catalog_source": "RAW",
            })

    # ── RELIABILITY STOP: no raw file ────────────────────────────────────────
    if raw_file_path is None or not raw_file_path.exists():
        logger.log("BF_INGEST_SUMMARY", "error",
                   duration_ms=int((time.time() - start_time) * 1000),
                   offers_processed=0,
                   error="STOP: no raw file available (scrape failed, no cache)",
                   extra={"bf_source": bf_source, "catalog_source": "RAW"})
        return 0

    # ── RELIABILITY STOP: raw file empty ─────────────────────────────────────
    if raw_file_path.stat().st_size == 0:
        logger.log("BF_INGEST_SUMMARY", "error",
                   duration_ms=int((time.time() - start_time) * 1000),
                   offers_processed=0,
                   error=f"STOP: raw file is empty — {raw_file_path.name}",
                   extra={"bf_source": bf_source})
        return 0

    # ── Step 2: Delegate normalization + UPSERT to ingest_business_france.py ─
    ingestor = SCRIPTS_DIR / "ingest_business_france.py"
    count_before = _get_bf_count()

    try:
        result = subprocess.run(
            [sys.executable, str(ingestor), "--path", str(raw_file_path)],
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        logger.log("BF_INGEST_SUMMARY", "error",
                   error="Ingestor timeout (120s)",
                   extra={"bf_source": bf_source})
        return 0

    if result.returncode != 0:
        logger.log("BF_INGEST_SUMMARY", "error",
                   duration_ms=int((time.time() - start_time) * 1000),
                   offers_processed=0,
                   error=f"STOP: ingestor exited {result.returncode}",
                   extra={"bf_source": bf_source, "raw_file": raw_file_path.name})
        return 0

    count_after = _get_bf_count()
    skills_count = _get_bf_skills_count()

    # ── RELIABILITY STOP: zero upserts ───────────────────────────────────────
    if count_after == 0:
        logger.log("BF_INGEST_SUMMARY", "error",
                   duration_ms=int((time.time() - start_time) * 1000),
                   offers_processed=0,
                   error="STOP: zero rows in fact_offers after ingest",
                   extra={"bf_source": bf_source})
        return 0

    duration_ms = int((time.time() - start_time) * 1000)

    # ── OBS: BF_INGEST_SUMMARY + BF_DB_EVIDENCE ──────────────────────────────
    logger.log("BF_INGEST_SUMMARY", "success",
               duration_ms=duration_ms,
               offers_processed=count_after,
               extra={
                   "bf_source": bf_source,
                   "db_path": str(DB_PATH),
                   "upserts_this_run": count_after - count_before,
                   "total_bf_rows": count_after,
                   "skills_rows": skills_count,
                   "raw_file": raw_file_path.name,
                   "catalog_source": "DB",
               })
    logger.log("BF_DB_EVIDENCE", "success", extra={
        "catalog_source": "DB",
        "bf_source": bf_source,
        "fact_offers_bf": count_after,
        "fact_offer_skills": skills_count,
    })

    return count_after


def _get_bf_count() -> int:
    """Return current count of business_france rows in fact_offers."""
    if not DB_PATH.exists():
        return 0
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM fact_offers WHERE source='business_france'")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def _get_bf_skills_count() -> int:
    """Return count of skills linked to BF offers in fact_offer_skills."""
    if not DB_PATH.exists():
        return 0
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM fact_offer_skills WHERE offer_id LIKE 'BF-%'")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def persist_bf_offers(offers: list, timestamp: str) -> int:
    """
    DEPRECATED — Option A: normalization is exclusively in ingest_business_france.py.

    This function is dead code in the Option A path. It is kept for backward
    compatibility only. It must NOT be called by ingest_business_france().
    If called directly, it raises RuntimeError to prevent silent parallel normalization.
    """
    raise RuntimeError(
        "persist_bf_offers() is disabled (Option A). "
        "Use ingest_business_france() → subprocess ingest_business_france.py instead."
    )
    ensure_db_exists()

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    cursor = conn.cursor()
    count = 0

    try:
        for offer in offers:
            # Extract ID (try multiple field names)
            native_id = None
            for field in ["id", "offer_id", "offerId", "reference"]:
                if offer.get(field):
                    native_id = str(offer[field])
                    break

            offer_id = f"BF-{native_id}" if native_id else f"BF-{hash(json.dumps(offer, sort_keys=True))}"

            title = offer.get("title") or offer.get("intitule") or "Sans titre"
            description = offer.get("description") or ""
            company = offer.get("company") or offer.get("company_name") or None
            city = offer.get("city") or offer.get("location_label") or None
            country = offer.get("country") or None
            publication_date = offer.get("publication_date") or None
            contract_duration = offer.get("contract_duration")
            start_date = offer.get("start_date") or None
            payload_json = json.dumps(offer, ensure_ascii=False)

            # Parse contract_duration as int
            if contract_duration is not None:
                try:
                    contract_duration = int(contract_duration)
                except (ValueError, TypeError):
                    contract_duration = None

            cursor.execute("""
                INSERT OR REPLACE INTO fact_offers
                (id, source, title, description, company, city, country,
                 publication_date, contract_duration, start_date, payload_json, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (offer_id, "business_france", title, description, company, city, country,
                  publication_date, contract_duration, start_date, payload_json, timestamp))
            count += 1

            # ------------------------------------------------------------------
            # Skills enrichment (read-only additive)
            # ------------------------------------------------------------------
            skills_from_payload = _extract_bf_skills(offer)
            if skills_from_payload:
                _insert_offer_skills(
                    cursor, offer_id, _map_labels_to_uris(skills_from_payload), "manual", timestamp
                )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return count


# ==============================================================================
# DATABASE UTILITIES
# ==============================================================================

def ensure_db_exists() -> None:
    """Initialize database if it doesn't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    cursor = conn.cursor()

    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fact_offers (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL CHECK(source IN ('france_travail', 'business_france')),
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            company TEXT,
            city TEXT,
            country TEXT,
            publication_date TEXT,
            contract_duration INTEGER,
            start_date TEXT,
            payload_json TEXT NOT NULL,
            last_updated TEXT NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fact_offers_source ON fact_offers(source)")
    ensure_offer_skills_table(conn)

    conn.commit()
    conn.close()


def _extract_ft_skills(offer: Dict[str, Any]) -> List[str]:
    """Extract and normalize FT skills from payload."""
    skills: List[str] = []

    competences = offer.get("competences", [])
    if isinstance(competences, list):
        for comp in competences:
            if isinstance(comp, dict):
                label = comp.get("libelle") or comp.get("label")
                if label:
                    skills.append(str(label))
            elif isinstance(comp, str):
                skills.append(comp)

    # Fallback: extract from title/description if no competences
    if not skills:
        payload = {
            "title": offer.get("intitule") or offer.get("appellationlibelle"),
            "description": offer.get("description"),
            "skills": competences,
        }
        skills = extract_raw_skills_from_offer(payload)

    normalized = [normalize_skill_label(s) for s in skills if s]
    return sorted({s for s in normalized if s})


def _extract_bf_skills(offer: Dict[str, Any]) -> List[str]:
    """Extract and normalize Business France skills from payload."""
    skills = extract_raw_skills_from_offer(offer)
    normalized = [normalize_skill_label(s) for s in skills if s]
    return sorted({s for s in normalized if s})


def _map_labels_to_uris(labels: List[str]) -> List[tuple[str, str | None]]:
    out: List[tuple[str, str | None]] = []
    for label in labels:
        uri = None
        result = map_skill(label, enable_fuzzy=False)
        if result and result.get("esco_id"):
            uri = str(result.get("esco_id"))
        out.append((label, uri))
    return out


def _insert_offer_skills(
    cursor: sqlite3.Cursor,
    offer_id: str,
    skills: List[tuple[str, str | None]],
    source: str,
    timestamp: str,
) -> None:
    """Insert skills into fact_offer_skills (idempotent)."""
    rows_written = 0
    uris_written = 0
    null_uri = 0
    for label, uri in skills:
        cursor.execute(
            """
            INSERT OR IGNORE INTO fact_offer_skills
            (offer_id, skill, skill_uri, source, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (offer_id, label, uri, source, None, timestamp),
        )
        if cursor.rowcount == 1:
            rows_written += 1
            if uri:
                uris_written += 1
            else:
                null_uri += 1
    if os.getenv("ELEVIA_DEBUG_OFFER_SKILLS", "").lower() in {"1", "true", "yes"}:
        logger.log(
            "offer_skills_insert",
            "debug",
            offer_id=offer_id,
            rows_written=rows_written,
            uris_written_count=uris_written,
            null_uri_count=null_uri,
        )


def run_sanity_checks(logger: StructuredLogger) -> bool:
    """
    Post-run sanity checks.

    Returns True if all checks pass, False otherwise.
    """
    start_time = time.time()

    if not DB_PATH.exists():
        logger.log("sanity_check", "error", error="Database file does not exist")
        return False

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        cursor = conn.cursor()

        # Check total count
        cursor.execute("SELECT COUNT(*) FROM fact_offers")
        total_count = cursor.fetchone()[0]

        # Check by source
        cursor.execute("SELECT source, COUNT(*) FROM fact_offers GROUP BY source")
        source_counts = dict(cursor.fetchall())

        conn.close()

        ft_count = source_counts.get("france_travail", 0)
        bf_count = source_counts.get("business_france", 0)

        duration_ms = int((time.time() - start_time) * 1000)

        if total_count == 0:
            logger.log("sanity_check", "error", duration_ms=duration_ms,
                       error="Database is empty (0 offers)",
                       extra={"total_count": total_count})
            return False

        if ft_count == 0 and bf_count == 0:
            logger.log("sanity_check", "error", duration_ms=duration_ms,
                       error="No offers from either source",
                       extra={"france_travail": ft_count, "business_france": bf_count})
            return False

        logger.log("sanity_check", "success", duration_ms=duration_ms,
                   extra={"total_count": total_count, "france_travail": ft_count, "business_france": bf_count})
        return True

    except Exception as e:
        logger.log("sanity_check", "error", error=f"Sanity check failed: {e}")
        return False


# ==============================================================================
# MAIN ORCHESTRATOR (Sprint 20 - Resilient pipeline)
# ==============================================================================

def run_ingestion() -> int:
    """
    Main ingestion orchestrator — Option A launcher for BF.

    BF path: scrape_business_france_azure.py → ingest_business_france.py (subprocess)
    normalization_source_of_truth = ingest_business_france.py
    id_strategy = BF-<native_id>, never hash()

    CLI flags:
      --bf-only   Run Business France only (skip France Travail)

    Env vars (explicit, no silent defaults):
      BF_USE_SAMPLE=0  (default LIVE)  |  BF_USE_SAMPLE=1 → SAMPLE (logged)
      BF_SOURCE=LIVE | SAMPLE | CACHE

    Returns exit code: 0 = success, 1 = failure
    """
    parser = argparse.ArgumentParser(description="Elevia ingestion pipeline (Option A)")
    parser.add_argument("--bf-only", action="store_true",
                        help="Run Business France ingestion only (skip France Travail)")
    args, _unknown = parser.parse_known_args()

    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    logger = StructuredLogger("ingestion_pipeline", run_id)

    # Determine BF source — explicit, never silent
    bf_source = BF_SOURCE
    if BF_USE_SAMPLE:
        bf_source = "SAMPLE"

    total_start = time.time()
    ft_count = 0
    bf_count = 0
    ft_error = None
    bf_error = None

    try:
        logger.log("pipeline", "started", extra={
            "db_path": str(DB_PATH),
            "raw_dir": str(RAW_BF_DIR),
            "bf_source": bf_source,
            "bf_only": args.bf_only,
        })

        # Step 1: France Travail (skipped in --bf-only mode)
        if not args.bf_only:
            try:
                ft_count = ingest_france_travail(logger)
            except Exception as e:
                ft_error = str(e)
                logger.log("scrape_france_travail", "error", error=f"{e}\n{traceback.format_exc()}")
                # Continue to Business France

        # Step 2: Business France — Option A launcher (always explicit bf_source)
        try:
            bf_count = ingest_business_france(logger, bf_source)
        except Exception as e:
            bf_error = str(e)
            logger.log("ingest_business_france", "error", error=f"{e}\n{traceback.format_exc()}")

        # Step 3: Sanity checks (this determines exit code)
        sanity_ok = run_sanity_checks(logger)

        # Summary
        total_duration_ms = int((time.time() - total_start) * 1000)
        total_offers = ft_count + bf_count

        # Determine final status based on Sprint 20 rules:
        # - Exit 0 if catalog has data (even if one source failed)
        # - Exit 1 ONLY if catalog is empty
        if not sanity_ok:
            # Sanity check failed = catalog empty or DB error
            error_summary = []
            if ft_error:
                error_summary.append(f"FT: {ft_error}")
            if bf_error:
                error_summary.append(f"BF: {bf_error}")
            error_msg = "; ".join(error_summary) if error_summary else "Sanity check failed"

            logger.log("pipeline", "error",
                       duration_ms=total_duration_ms,
                       offers_processed=total_offers,
                       error=error_msg,
                       extra={
                           "france_travail": ft_count,
                           "business_france": bf_count,
                           "ft_error": ft_error,
                           "bf_error": bf_error,
                       })
            send_slack_alert(run_id, "pipeline", error_msg)
            return 1

        # Sanity check passed = catalog has data
        # Log partial success if one source had issues
        if ft_error or bf_error:
            logger.log("pipeline", "partial",
                       duration_ms=total_duration_ms,
                       offers_processed=total_offers,
                       extra={
                           "france_travail": ft_count,
                           "business_france": bf_count,
                           "ft_error": ft_error,
                           "bf_error": bf_error,
                       })
        else:
            logger.log("pipeline", "success",
                       duration_ms=total_duration_ms,
                       offers_processed=total_offers,
                       extra={
                           "france_travail": ft_count,
                           "business_france": bf_count,
                       })

        return 0

    except Exception as e:
        # Catch-all for unexpected errors
        logger.log("pipeline", "error", error=f"Unexpected error: {e}\n{traceback.format_exc()}")
        send_slack_alert(run_id, "pipeline", str(e))
        return 1


if __name__ == "__main__":
    sys.exit(run_ingestion())

# ==============================================================================
# OPTION A CONTRACT
# ==============================================================================
# one_true_path: scrape_business_france_azure.py → ingest_business_france.py
# run_ingestion_role: launcher_only (no BF normalization here)
# id_strategy: BF-<native_id> (in ingest_business_france.py, NEVER hash() here)
# normalization_source_of_truth: ingest_business_france.py
# bf_source: LIVE | SAMPLE | CACHE — always explicit, never silent
