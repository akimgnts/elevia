#!/usr/bin/env python3
"""
scrape_business_france.py - Business France VIE Scraper
Sprint 16 - Business France Live Pipeline

Production-grade scraper with:
- Endpoint viability test
- Immutable raw JSONL per run (auditability)
- Pagination with configurable limits
- Local sample mode for development/testing

Usage:
    python3 apps/api/scripts/scrape_business_france.py [--sample]

Modes:
    --sample: Use local sample_vie_offers.json (development mode)
    --test: Test endpoint viability only
    (default): Attempt live API fetch

Environment variables:
    MAX_PAGES: Maximum pages to fetch (default: 3)
    SLEEP_SEC: Sleep between pages (default: 1.0)
    BF_API_URL: Override Business France API URL
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("[ERROR] requests library not installed. Run: pip install requests")
    sys.exit(1)

# Paths
API_ROOT = Path(__file__).parent.parent
DATA_DIR = API_ROOT / "data"
RAW_BF_DIR = DATA_DIR / "raw" / "business_france"
SAMPLE_FILE = DATA_DIR / "sample_vie_offers.json"

# Business France API config (can be overridden via env)
BF_API_URL = os.environ.get("BF_API_URL", "https://mon-vie-via.businessfrance.fr/api/offres")

# Request headers
HEADERS = {
    "User-Agent": "Elevia/1.0",
    "Accept": "application/json",
}

# Config from environment
MAX_PAGES = int(os.environ.get("MAX_PAGES", "3"))
SLEEP_SEC = float(os.environ.get("SLEEP_SEC", "1.0"))
TIMEOUT_SEC = 15


def test_endpoint_viability() -> bool:
    """
    Test if the Business France API endpoint is viable.

    Makes 1 real request and prints diagnostic info:
    - HTTP status
    - Content-Type
    - JSON keys (if JSON) or first 200 chars (if not)

    Returns:
        True if endpoint is viable, False otherwise
    """
    print("=" * 60)
    print("BUSINESS FRANCE ENDPOINT VIABILITY TEST")
    print("=" * 60)
    print(f"URL: {BF_API_URL}")
    print(f"Headers: {HEADERS}")
    print()

    try:
        r = requests.get(
            BF_API_URL,
            headers=HEADERS,
            timeout=TIMEOUT_SEC,
        )

        print(f"HTTP Status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('Content-Type', 'N/A')}")
        print(f"Content-Length: {r.headers.get('Content-Length', 'N/A')}")
        print()

        # Handle rate limiting / forbidden
        if r.status_code == 403:
            print("[ERROR] 403 Forbidden - Access denied to Business France API")
            print("[HINT] The API may require authentication or be IP-restricted")
            return False

        if r.status_code == 429:
            print("[ERROR] 429 Too Many Requests - Rate limited")
            print("[HINT] Wait before retrying or reduce request frequency")
            return False

        if r.status_code >= 400:
            print(f"[ERROR] HTTP {r.status_code} error")
            print(f"Response (first 200 chars): {r.text[:200]}")
            return False

        # Check if response is JSON
        content_type = r.headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                data = r.json()
                print("[OK] Response is valid JSON")

                if isinstance(data, dict):
                    print(f"Top-level keys: {list(data.keys())}")

                    # Check for offers
                    for key in ["content", "data", "offers", "results", "items"]:
                        if key in data:
                            items = data[key]
                            if isinstance(items, list):
                                print(f"Found '{key}' array with {len(items)} items")
                                if items:
                                    print(f"First item keys: {list(items[0].keys()) if isinstance(items[0], dict) else 'N/A'}")
                            break

                    # Check pagination info
                    for key in ["totalElements", "total", "count", "totalPages", "page"]:
                        if key in data:
                            print(f"{key}: {data[key]}")

                elif isinstance(data, list):
                    print(f"Response is array with {len(data)} items")
                    if data and isinstance(data[0], dict):
                        print(f"First item keys: {list(data[0].keys())}")

                print()
                print("[VIABILITY] PASS - Endpoint is viable")
                return True

            except json.JSONDecodeError as e:
                print(f"[ERROR] Invalid JSON despite Content-Type: {e}")
                print(f"Response (first 200 chars): {r.text[:200]}")
                return False
        else:
            print(f"[WARNING] Response is not JSON")
            print(f"Response (first 200 chars): {r.text[:200]}")
            if r.status_code == 200:
                print()
                print("[VIABILITY] PARTIAL - Endpoint responds but not JSON")
                return False
            return False

    except requests.exceptions.Timeout:
        print(f"[ERROR] Request timeout after {TIMEOUT_SEC}s")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"[ERROR] Connection failed: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False


def test_sample_viability() -> bool:
    """
    Test if local sample file is viable for sample mode.

    Returns:
        True if sample file exists and is valid JSON array
    """
    print("=" * 60)
    print("SAMPLE FILE VIABILITY TEST")
    print("=" * 60)
    print(f"File: {SAMPLE_FILE}")
    print()

    if not SAMPLE_FILE.exists():
        print("[ERROR] Sample file not found")
        return False

    try:
        with open(SAMPLE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            print(f"[ERROR] Sample file is not a list, got {type(data)}")
            return False

        print(f"[OK] Sample file is valid JSON array")
        print(f"Total offers: {len(data)}")

        if data:
            print(f"First offer keys: {list(data[0].keys())}")

        print()
        print("[VIABILITY] PASS - Sample file is viable")
        return True

    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Failed to read file: {e}")
        return False


def fetch_page(page: int, run_id: str) -> tuple[list, bool]:
    """
    Fetch a single page of offers from live API.

    Args:
        page: Page number (0-indexed)
        run_id: Run identifier for logging

    Returns:
        (offers_list, has_more) tuple
    """
    params = {
        "page": page,
        "size": 50,
    }

    try:
        r = requests.get(
            BF_API_URL,
            headers=HEADERS,
            params=params,
            timeout=TIMEOUT_SEC,
        )

        if r.status_code == 403:
            print(f"[BF] page={page} ERROR: 403 Forbidden")
            return [], False

        if r.status_code == 429:
            print(f"[BF] page={page} ERROR: 429 Rate Limited")
            return [], False

        if r.status_code >= 400:
            print(f"[BF] page={page} ERROR: HTTP {r.status_code}")
            return [], False

        data = r.json()

        # Handle different response structures
        if isinstance(data, dict):
            if "content" in data:
                offers = data["content"]
                total_pages = data.get("totalPages", 1)
                has_more = page < total_pages - 1
            elif "data" in data:
                offers = data["data"]
                has_more = len(offers) > 0
            elif "offers" in data:
                offers = data["offers"]
                has_more = len(offers) > 0
            else:
                for key, val in data.items():
                    if isinstance(val, list) and len(val) > 0:
                        offers = val
                        has_more = len(offers) > 0
                        break
                else:
                    print(f"[BF] page={page} WARNING: No offers array found in response")
                    return [], False
        elif isinstance(data, list):
            offers = data
            has_more = len(offers) > 0
        else:
            print(f"[BF] page={page} WARNING: Unexpected response type: {type(data)}")
            return [], False

        print(f"[BF] page={page} got={len(offers)}")
        return offers, has_more and len(offers) > 0

    except requests.exceptions.Timeout:
        print(f"[BF] page={page} ERROR: Timeout")
        return [], False
    except json.JSONDecodeError as e:
        print(f"[BF] page={page} ERROR: Invalid JSON: {e}")
        return [], False
    except Exception as e:
        print(f"[BF] page={page} ERROR: {e}")
        return [], False


def run_scraper_sample() -> int:
    """
    Run scraper in sample mode using local VIE offers file.

    Creates raw JSONL from sample_vie_offers.json for pipeline testing.

    Returns:
        Total number of offers processed
    """
    print("=" * 60)
    print("BUSINESS FRANCE SCRAPER (SAMPLE MODE)")
    print("=" * 60)

    if not SAMPLE_FILE.exists():
        print(f"[ERROR] Sample file not found: {SAMPLE_FILE}")
        return 0

    # Generate run_id (UTC ISO timestamp)
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"Run ID: {run_id}")
    print(f"Source: {SAMPLE_FILE}")
    print()

    # Load sample data
    try:
        with open(SAMPLE_FILE, "r", encoding="utf-8") as f:
            offers = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load sample file: {e}")
        return 0

    if not isinstance(offers, list):
        print(f"[ERROR] Sample file is not a list")
        return 0

    print(f"[SAMPLE] Loaded {len(offers)} offers from sample file")

    # Ensure directory exists
    RAW_BF_DIR.mkdir(parents=True, exist_ok=True)

    # Raw output file (one per run, never overwrite)
    raw_file = RAW_BF_DIR / f"{run_id}.jsonl"
    if raw_file.exists():
        print(f"[ERROR] Raw file already exists: {raw_file}")
        sys.exit(1)

    # Write each offer as JSONL record
    fetched_at = datetime.now(timezone.utc).isoformat()
    with open(raw_file, "w", encoding="utf-8") as f:
        for offer in offers:
            # Add source marker if not present
            if "source" not in offer:
                offer["source"] = "business_france"

            record = {
                "run_id": run_id,
                "fetched_at": fetched_at,
                "source_url": f"file://{SAMPLE_FILE}",
                "payload": offer,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print()
    print("=" * 60)
    print("SCRAPER SUMMARY (SAMPLE MODE)")
    print("=" * 60)
    print(f"Total offers: {len(offers)}")
    print(f"Raw file: {raw_file}")

    return len(offers)


def run_scraper() -> int:
    """
    Run the Business France scraper (live API mode).

    Fetches offers page by page and writes to immutable JSONL file.

    Returns:
        Total number of offers scraped
    """
    print("=" * 60)
    print("BUSINESS FRANCE SCRAPER (LIVE MODE)")
    print("=" * 60)

    # Generate run_id (UTC ISO timestamp)
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"Run ID: {run_id}")
    print(f"API URL: {BF_API_URL}")
    print(f"Max pages: {MAX_PAGES}")
    print(f"Sleep between pages: {SLEEP_SEC}s")
    print()

    # Ensure directory exists
    RAW_BF_DIR.mkdir(parents=True, exist_ok=True)

    # Raw output file (one per run, never overwrite)
    raw_file = RAW_BF_DIR / f"{run_id}.jsonl"
    if raw_file.exists():
        print(f"[ERROR] Raw file already exists: {raw_file}")
        sys.exit(1)

    total_offers = 0
    page = 0

    while page < MAX_PAGES:
        offers, has_more = fetch_page(page, run_id)

        if not offers:
            print(f"[BF] No offers on page {page}, stopping pagination")
            break

        # Write each offer as JSONL record
        with open(raw_file, "a", encoding="utf-8") as f:
            fetched_at = datetime.now(timezone.utc).isoformat()
            for offer in offers:
                record = {
                    "run_id": run_id,
                    "fetched_at": fetched_at,
                    "source_url": BF_API_URL,
                    "payload": offer,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        total_offers += len(offers)
        page += 1

        if not has_more:
            print(f"[BF] No more pages (last={page-1})")
            break

        if page < MAX_PAGES:
            time.sleep(SLEEP_SEC)

    print()
    print("=" * 60)
    print("SCRAPER SUMMARY")
    print("=" * 60)
    print(f"Pages fetched: {page}")
    print(f"Total offers: {total_offers}")
    print(f"Raw file: {raw_file}")

    return total_offers


if __name__ == "__main__":
    # Check for --test flag
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        success = test_endpoint_viability()
        sys.exit(0 if success else 1)

    # Check for --sample flag
    if len(sys.argv) > 1 and sys.argv[1] == "--sample":
        if "--test" in sys.argv:
            success = test_sample_viability()
            sys.exit(0 if success else 1)
        count = run_scraper_sample()
        sys.exit(0 if count > 0 else 1)

    # Default: try live API
    count = run_scraper()
    if count == 0:
        print()
        print("[INFO] Live API returned 0 offers. Try --sample mode for testing:")
        print("  python3 apps/api/scripts/scrape_business_france.py --sample")
    sys.exit(0 if count > 0 else 1)
