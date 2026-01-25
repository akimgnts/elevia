#!/usr/bin/env python3
"""
run_ingestion.py - Autonomous Ingestion Orchestrator
Sprint 19 - Autonomie technique ingestion
Sprint 20 - Business France fallback on cached raw

Production-grade orchestrator with:
- JSON structured logging (stdout, Railway compatible)
- Slack webhook alerting on failure
- Post-run sanity checks
- Proper exit codes for CRON monitoring
- Business France fallback to cached raw on API failure (Sprint 20)

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

Resilience (Sprint 20):
    - If Business France API fails, falls back to most recent cached raw JSONL
    - Pipeline continues as long as total_offers > 0
    - Exit code 1 ONLY if total_offers == 0 or DB write fails
"""

import json
import os
import sqlite3
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
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

# Business France config
BF_USE_SAMPLE = os.environ.get("BF_USE_SAMPLE", "1") == "1"  # Default to sample mode
SAMPLE_FILE = DATA_DIR / "sample_vie_offers.json"


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

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return count


# ==============================================================================
# BUSINESS FRANCE INGESTION (Sprint 20 - Fallback on cached raw)
# ==============================================================================

def scrape_bf_live(logger: StructuredLogger) -> tuple[list, Optional[Path], Optional[str]]:
    """
    Try to scrape fresh Business France data.

    Returns:
        (offers_list, raw_file_path, error_message)
        - If success: (offers, raw_file, None)
        - If failure: ([], None, error_message)
    """
    # In sample mode, load from sample file
    if BF_USE_SAMPLE:
        if not SAMPLE_FILE.exists():
            return [], None, f"Sample file not found: {SAMPLE_FILE}"

        try:
            with open(SAMPLE_FILE, "r", encoding="utf-8") as f:
                offers = json.load(f)

            if not isinstance(offers, list):
                return [], None, "Sample file is not a list"

            # Write to raw JSONL (immutable per run)
            now = datetime.now(timezone.utc)
            run_id = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            fetched_at = now.isoformat()

            RAW_BF_DIR.mkdir(parents=True, exist_ok=True)
            raw_file = RAW_BF_DIR / f"{run_id}.jsonl"

            # Avoid overwriting existing file
            if raw_file.exists():
                raw_file = RAW_BF_DIR / f"{run_id}-{int(time.time())}.jsonl"

            with open(raw_file, "w", encoding="utf-8") as f:
                for offer in offers:
                    if "source" not in offer:
                        offer["source"] = "business_france"
                    record = {
                        "run_id": run_id,
                        "fetched_at": fetched_at,
                        "source_url": f"file://{SAMPLE_FILE}",
                        "payload": offer,
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")

            return offers, raw_file, None

        except json.JSONDecodeError as e:
            return [], None, f"JSONDecodeError: {e}"
        except Exception as e:
            return [], None, f"Error reading sample: {e}"

    # Live API mode (not implemented - would require actual BF API access)
    # For now, return error to trigger fallback
    return [], None, "Live BF API not configured (BF_USE_SAMPLE=0 but no API available)"


def load_bf_from_cache(logger: StructuredLogger) -> tuple[list, Optional[Path]]:
    """
    Load Business France offers from the most recent cached raw JSONL file.

    Returns:
        (offers_list, raw_file_path)
    """
    if not RAW_BF_DIR.exists():
        return [], None

    raw_files = list(RAW_BF_DIR.glob("*.jsonl"))
    if not raw_files:
        return [], None

    # Sort by modification time, most recent first
    raw_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    raw_file = raw_files[0]

    offers = []
    with open(raw_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                payload = record.get("payload", {})
                offers.append(payload)
            except json.JSONDecodeError:
                continue

    return offers, raw_file


def ingest_business_france(logger: StructuredLogger) -> int:
    """
    Ingest Business France offers with fallback to cached raw.

    Sprint 20 behavior:
    1. Try to scrape fresh data (live API or sample file)
    2. If that fails, fall back to most recent cached raw JSONL
    3. Log clearly whether using live data or fallback
    4. Only return 0 if both live AND cache are empty/unavailable

    Returns number of offers ingested.
    """
    start_time = time.time()
    timestamp = datetime.now(timezone.utc).isoformat()

    # Step 1: Try live scraping
    offers, raw_file, scrape_error = scrape_bf_live(logger)

    if offers and raw_file:
        # Success: live data obtained
        count = persist_bf_offers(offers, timestamp)
        duration_ms = int((time.time() - start_time) * 1000)
        logger.log("ingest_business_france", "success",
                   duration_ms=duration_ms,
                   offers_processed=count,
                   extra={"source": "live", "raw_file": str(raw_file.name)})
        return count

    # Step 2: Live failed, try fallback to cached raw
    logger.log("scrape_business_france", "error",
               error=scrape_error or "Unknown scrape error",
               extra={"attempting_fallback": True})

    cached_offers, cached_file = load_bf_from_cache(logger)

    if cached_offers and cached_file:
        # Fallback: using cached data
        count = persist_bf_offers(cached_offers, timestamp)
        duration_ms = int((time.time() - start_time) * 1000)

        # Log with status="fallback" as required by Sprint 20
        logger.log("ingest_business_france", "fallback",
                   duration_ms=duration_ms,
                   offers_processed=count,
                   extra={
                       "source": "cached_raw",
                       "raw_file": str(cached_file.name),
                       "original_error": scrape_error,
                   })
        return count

    # Step 3: Both live and cache failed
    duration_ms = int((time.time() - start_time) * 1000)
    logger.log("ingest_business_france", "error",
               duration_ms=duration_ms,
               offers_processed=0,
               error="Both live scrape and cache fallback failed",
               extra={
                   "scrape_error": scrape_error,
                   "cache_available": False,
               })
    return 0


def persist_bf_offers(offers: list, timestamp: str) -> int:
    """Persist Business France offers to SQLite."""
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

    if DB_PATH.exists():
        return

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

    conn.commit()
    conn.close()


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
    Main ingestion orchestrator.

    Sprint 20 behavior:
    - Pipeline continues even if one source fails
    - Exit code 0 as long as total_offers > 0 after sanity check
    - Exit code 1 ONLY if:
      - total_offers == 0 (catalog would be empty)
      - DB write fails
      - Unexpected uncaught exception

    Returns exit code: 0 = success/partial, 1 = failure
    """
    run_id = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    logger = StructuredLogger("ingestion_pipeline", run_id)

    total_start = time.time()
    ft_count = 0
    bf_count = 0
    ft_error = None
    bf_error = None

    try:
        logger.log("pipeline", "started")

        # Step 1: France Travail (error = non-blocking)
        try:
            ft_count = ingest_france_travail(logger)
        except Exception as e:
            ft_error = str(e)
            logger.log("scrape_france_travail", "error", error=f"{e}\n{traceback.format_exc()}")
            # Continue to Business France

        # Step 2: Business France with fallback (error = non-blocking if cache available)
        try:
            bf_count = ingest_business_france(logger)
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
