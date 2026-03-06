#!/usr/bin/env python3
"""
ingest_business_france.py - Business France VIE Ingestion
Sprint 16 - Business France Live Pipeline

Production-grade ingestion with:
- Real HTML cleaning (no residual tags)
- Stable ID generation (native or hash fallback)
- Strict schema alignment (fail-fast on missing columns)
- UPSERT into SQLite fact_offers

Usage:
    python3 apps/api/scripts/ingest_business_france.py [--path <raw_file>]

If no --path, uses the most recent raw file in data/raw/business_france/
"""

import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, List

# Paths
API_ROOT = Path(__file__).parent.parent
DATA_DIR = API_ROOT / "data"
RAW_BF_DIR = DATA_DIR / "raw" / "business_france"
DB_PATH = DATA_DIR / "db" / "offers.db"

# Add src to path for shared utilities
sys.path.insert(0, str(API_ROOT / "src"))

from api.utils.offer_skills import ensure_offer_skills_table
from esco.extract import extract_raw_skills_from_offer
from esco.mapper import map_skill
from matching.extractors import normalize_skill_label

# Required DB columns (fail if missing)
REQUIRED_COLUMNS = {
    "id", "source", "title", "description", "company",
    "city", "country", "publication_date", "contract_duration", "start_date",
}

# Optional columns (use if present)
OPTIONAL_COLUMNS = {"payload_json", "last_updated"}


# ==============================================================================
# HTML CLEANING
# ==============================================================================

def html_to_text(html: Optional[str]) -> str:
    """
    Convert HTML to clean plain text.

    - Replaces <br>, <p>, <li> with newlines
    - Uses BeautifulSoup if available, else regex fallback
    - Normalizes whitespace
    - Strips leading/trailing whitespace
    - Removes residual HTML tags

    Args:
        html: HTML string or None

    Returns:
        Clean plain text (never None)
    """
    if not html:
        return ""

    text = str(html)

    # Try BeautifulSoup first (cleaner parsing)
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text, "html.parser")

        # Replace block elements with newlines
        for br in soup.find_all("br"):
            br.replace_with("\n")
        for tag in soup.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"]):
            tag.insert_before("\n")
            tag.insert_after("\n")

        text = soup.get_text(separator=" ")

    except ImportError:
        # Fallback: regex-based cleaning
        # Replace block-level tags with newlines
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</(p|div|li|h[1-6])>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<(p|div|li|h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)

        # Remove all remaining HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Decode common HTML entities
        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")
        text = text.replace("&apos;", "'")

    # Normalize whitespace
    lines = []
    for line in text.split("\n"):
        # Collapse multiple spaces, strip each line
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:  # Skip empty lines
            lines.append(line)

    return "\n".join(lines)


# ==============================================================================
# STABLE ID GENERATION
# ==============================================================================

# Native ID field names to check (in priority order)
NATIVE_ID_FIELDS = ["id", "offerId", "reference", "ref", "uuid", "slug"]


def make_business_france_id(payload: dict) -> tuple[str, str]:
    """
    Generate stable ID for Business France offer.

    Strategy:
    1. Native ID: Check known ID fields, use BF-{native_id}
    2. Hash fallback: SHA1 of canonical fields, use BF-{hash[:16]}

    Args:
        payload: Raw offer payload

    Returns:
        (offer_id, strategy) tuple where strategy is 'native' or 'hash'
    """
    # Try native ID fields
    for field in NATIVE_ID_FIELDS:
        native_id = payload.get(field)
        if native_id and str(native_id).strip():
            offer_id = f"BF-{str(native_id).strip()}"
            return offer_id, "native"

    # Hash fallback: concatenate canonical fields
    parts = []
    for field in ["company", "title", "city", "country", "start_date", "contract_duration"]:
        val = payload.get(field, "")
        if val is not None:
            parts.append(str(val).lower().strip())

    canonical = "|".join(parts)
    # Collapse multiple spaces
    canonical = re.sub(r"\s+", " ", canonical)

    hash_val = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]
    offer_id = f"BF-{hash_val}"
    return offer_id, "hash"


# ==============================================================================
# FIELD EXTRACTION
# ==============================================================================

def extract_field(payload: dict, keys: list, default=None) -> Any:
    """
    Extract field from payload, trying multiple key names.

    Args:
        payload: Raw offer payload
        keys: List of key names to try (in order)
        default: Default value if not found

    Returns:
        Field value or default
    """
    for key in keys:
        val = payload.get(key)
        if val is not None:
            return val
    return default


def extract_offer_fields(payload: dict) -> dict:
    """
    Extract normalized fields from Business France payload.

    Returns dict with all OfferNormalized fields.
    """
    # Generate stable ID
    offer_id, id_strategy = make_business_france_id(payload)

    # Extract raw fields (try multiple key names for flexibility)
    raw_title = extract_field(payload, ["title", "intitule", "poste", "name"], "")
    raw_desc = extract_field(payload, ["description", "descriptif", "content", "details"], "")
    raw_company = extract_field(payload, ["company", "entreprise", "companyName", "societe"], None)
    raw_city = extract_field(payload, ["city", "ville", "location", "lieu"], None)
    raw_country = extract_field(payload, ["country", "pays", "countryName"], None)
    raw_pub_date = extract_field(payload, ["publicationDate", "publication_date", "dateCreation", "createdAt"], None)
    raw_duration = extract_field(payload, ["contractDuration", "contract_duration", "duration", "duree"], None)
    raw_start = extract_field(payload, ["startDate", "start_date", "dateDebut"], None)

    # Clean HTML from text fields
    title = html_to_text(raw_title)
    description = html_to_text(raw_desc)
    company = html_to_text(raw_company) if raw_company else None
    city = html_to_text(raw_city) if raw_city else None
    country = html_to_text(raw_country) if raw_country else None

    # Parse contract duration as int
    contract_duration = None
    if raw_duration is not None:
        try:
            contract_duration = int(raw_duration)
        except (ValueError, TypeError):
            # Try extracting number from string like "12 mois"
            match = re.search(r"(\d+)", str(raw_duration))
            if match:
                contract_duration = int(match.group(1))

    return {
        "id": offer_id,
        "id_strategy": id_strategy,
        "source": "business_france",
        "title": title,
        "description": description,
        "company": company if company else None,
        "city": city if city else None,
        "country": country if country else None,
        "publication_date": raw_pub_date,
        "contract_duration": contract_duration,
        "start_date": raw_start,
    }


# ==============================================================================
# DATABASE OPERATIONS
# ==============================================================================

def verify_schema() -> tuple[bool, set, str]:
    """
    Verify database schema before ingestion.

    Returns:
        (is_valid, available_columns, error_message)
    """
    if not DB_PATH.exists():
        return False, set(), f"Database not found at {DB_PATH}"

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=5)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(fact_offers)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        # Check required columns
        missing = REQUIRED_COLUMNS - columns
        if missing:
            return False, columns, f"Missing required columns: {sorted(missing)}"

        return True, columns, ""

    except Exception as e:
        return False, set(), f"Schema verification failed: {e}"


def upsert_offers(offers: list[dict], available_columns: set) -> int:
    """
    UPSERT offers into SQLite database.

    Args:
        offers: List of extracted offer dicts
        available_columns: Set of available DB columns

    Returns:
        Number of offers upserted
    """
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    cursor = conn.cursor()
    count = 0
    timestamp = datetime.now(timezone.utc).isoformat()
    ensure_offer_skills_table(conn)

    # Build column list dynamically
    base_columns = ["id", "source", "title", "description", "company", "city",
                    "country", "publication_date", "contract_duration", "start_date"]
    insert_columns = base_columns.copy()

    if "payload_json" in available_columns:
        insert_columns.append("payload_json")
    if "last_updated" in available_columns:
        insert_columns.append("last_updated")

    placeholders = ", ".join(["?" for _ in insert_columns])
    columns_str = ", ".join(insert_columns)
    sql = f"INSERT OR REPLACE INTO fact_offers ({columns_str}) VALUES ({placeholders})"

    try:
        for offer in offers:
            values = [
                offer["id"],
                offer["source"],
                offer["title"],
                offer["description"],
                offer["company"],
                offer["city"],
                offer["country"],
                offer["publication_date"],
                offer["contract_duration"],
                offer["start_date"],
            ]

            if "payload_json" in insert_columns:
                values.append(offer.get("payload_json", "{}"))
            if "last_updated" in insert_columns:
                values.append(timestamp)

            cursor.execute(sql, values)
            count += 1

            # Skills enrichment (read-only additive)
            skills_from_payload = _extract_bf_skills(offer)
            if skills_from_payload:
                _insert_offer_skills(
                    cursor, offer["id"], _map_labels_to_uris(skills_from_payload), "manual", timestamp
                )

        conn.commit()
        return count

    except Exception as e:
        print(f"[DB] ERROR during upsert: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()


def _extract_bf_skills(offer: dict) -> List[str]:
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
        print(json.dumps({
            "event": "offer_skills_insert",
            "offer_id": offer_id,
            "rows_written": rows_written,
            "uris_written_count": uris_written,
            "null_uri_count": null_uri,
        }, ensure_ascii=False))


# ==============================================================================
# MAIN INGESTION
# ==============================================================================

def find_latest_raw_file() -> Optional[Path]:
    """Find the most recent raw JSONL file."""
    if not RAW_BF_DIR.exists():
        return None

    files = list(RAW_BF_DIR.glob("*.jsonl"))
    if not files:
        return None

    # Sort by modification time (most recent first)
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return files[0]


def run_ingestion(raw_path: Optional[Path] = None) -> int:
    """
    Run Business France ingestion.

    Args:
        raw_path: Specific raw file to ingest, or None to use latest

    Returns:
        Number of offers ingested
    """
    print("=" * 60)
    print("BUSINESS FRANCE INGESTION")
    print("=" * 60)

    # Find raw file
    if raw_path is None:
        raw_path = find_latest_raw_file()
        if raw_path is None:
            print("[ERROR] No raw files found in", RAW_BF_DIR)
            return 0

    if not raw_path.exists():
        print(f"[ERROR] Raw file not found: {raw_path}")
        return 0

    print(f"Ingesting raw file: {raw_path}")
    print()

    # Verify schema
    print("[SCHEMA] Verifying database schema...")
    is_valid, available_columns, error_msg = verify_schema()
    if not is_valid:
        print(f"[SCHEMA] ERROR: {error_msg}")
        print("[ABORT] Cannot proceed without valid schema")
        sys.exit(1)

    print(f"[SCHEMA] Available columns: {sorted(available_columns)}")
    print()

    # Read and process raw file
    offers = []
    id_stats = {"native": 0, "hash": 0}

    with open(raw_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                record = json.loads(line)
                payload = record.get("payload", {})

                # Extract and clean fields
                offer = extract_offer_fields(payload)

                # PATCH 1 — VIE detection: inject is_vie as JSON boolean
                # Civiweb Azure API returns missionType="VIE" but not is_vie boolean.
                # _attach_payload_fields() requires isinstance(payload.get("is_vie"), bool)
                # — SQL integer 1 fails this check, so we must use Python bool here.
                _mission_type = str(payload.get("missionType") or "").upper()
                payload["is_vie"] = (_mission_type == "VIE")

                # Store raw payload for debugging
                offer["payload_json"] = json.dumps(payload, ensure_ascii=False)

                # Track ID strategy stats
                id_stats[offer.pop("id_strategy")] += 1

                offers.append(offer)

            except json.JSONDecodeError as e:
                print(f"[WARNING] Line {line_num}: Invalid JSON: {e}")
            except Exception as e:
                print(f"[WARNING] Line {line_num}: Error processing: {e}")

    print(f"[PARSE] Processed {len(offers)} offers from raw file")
    print(f"[ID] Strategies: native={id_stats['native']}, hash={id_stats['hash']}")
    print()

    if not offers:
        print("[WARNING] No offers to ingest")
        return 0

    # Verify HTML cleaning (spot check)
    html_count = 0
    for offer in offers[:10]:  # Check first 10
        desc = offer.get("description", "")
        if re.search(r"<[a-zA-Z][^>]*>", desc):
            html_count += 1

    if html_count > 0:
        print(f"[WARNING] {html_count}/10 offers still contain HTML tags!")
    else:
        print("[HTML] Clean: No HTML tags detected in sample")

    # UPSERT to database
    print()
    print("[DB] Upserting offers...")
    count = upsert_offers(offers, available_columns)

    print()
    print("=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    print(f"Raw file: {raw_path}")
    print(f"Offers parsed: {len(offers)}")
    print(f"Offers upserted: {count}")
    print(f"ID strategies: native={id_stats['native']}, hash={id_stats['hash']}")

    return count


if __name__ == "__main__":
    # Parse args
    raw_path = None
    if len(sys.argv) > 2 and sys.argv[1] == "--path":
        raw_path = Path(sys.argv[2])

    count = run_ingestion(raw_path)
    sys.exit(0 if count > 0 else 1)
