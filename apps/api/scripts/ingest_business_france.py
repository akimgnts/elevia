#!/usr/bin/env python3
"""
ingest_business_france.py - Business France VIE Ingestion

Production-grade ingestion with:
- Real HTML cleaning (no residual tags)
- Stable ID generation (native or hash fallback)
- INSERT INTO raw_offers (PostgreSQL, jsonb)

Usage:
    python3 apps/api/scripts/ingest_business_france.py [--path <raw_file>]

If no --path, uses the most recent raw file in data/raw/business_france/
Requires DATABASE_URL environment variable.
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, List

import psycopg

# Paths
API_ROOT = Path(__file__).parent.parent
DATA_DIR = API_ROOT / "data"
RAW_BF_DIR = DATA_DIR / "raw" / "business_france"

# Add src to path for shared utilities
sys.path.insert(0, str(API_ROOT / "src"))


# ==============================================================================
# HTML CLEANING
# ==============================================================================

def html_to_text(html: Optional[str]) -> str:
    if not html:
        return ""

    text = str(html)

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text, "html.parser")

        for br in soup.find_all("br"):
            br.replace_with("\n")
        for tag in soup.find_all(["p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"]):
            tag.insert_before("\n")
            tag.insert_after("\n")

        text = soup.get_text(separator=" ")

    except ImportError:
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</(p|div|li|h[1-6])>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<(p|div|li|h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")
        text = text.replace("&apos;", "'")

    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)

    return "\n".join(lines)


# ==============================================================================
# STABLE ID GENERATION
# ==============================================================================

NATIVE_ID_FIELDS = ["id", "offerId", "reference", "ref", "uuid", "slug"]


def make_business_france_id(payload: dict) -> tuple[str, str]:
    for field in NATIVE_ID_FIELDS:
        native_id = payload.get(field)
        if native_id and str(native_id).strip():
            offer_id = f"BF-{str(native_id).strip()}"
            return offer_id, "native"

    parts = []
    for field in ["company", "title", "city", "country", "start_date", "contract_duration"]:
        val = payload.get(field, "")
        if val is not None:
            parts.append(str(val).lower().strip())

    canonical = "|".join(parts)
    canonical = re.sub(r"\s+", " ", canonical)

    hash_val = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]
    offer_id = f"BF-{hash_val}"
    return offer_id, "hash"


# ==============================================================================
# FIELD EXTRACTION
# ==============================================================================

def extract_field(payload: dict, keys: list, default=None) -> Any:
    for key in keys:
        val = payload.get(key)
        if val is not None:
            return val
    return default


def extract_offer_fields(payload: dict) -> dict:
    offer_id, id_strategy = make_business_france_id(payload)

    raw_title = extract_field(payload, ["title", "intitule", "poste", "name"], "")
    raw_desc = extract_field(payload, ["description", "descriptif", "content", "details"], "")
    raw_company = extract_field(payload, ["company", "entreprise", "companyName", "societe"], None)
    raw_city = extract_field(payload, ["city", "ville", "location", "lieu"], None)
    raw_country = extract_field(payload, ["country", "pays", "countryName"], None)
    raw_pub_date = extract_field(payload, ["publicationDate", "publication_date", "dateCreation", "createdAt"], None)
    raw_duration = extract_field(payload, ["contractDuration", "contract_duration", "duration", "duree"], None)
    raw_start = extract_field(payload, ["startDate", "start_date", "dateDebut"], None)

    title = html_to_text(raw_title)
    description = html_to_text(raw_desc)
    company = html_to_text(raw_company) if raw_company else None
    city = html_to_text(raw_city) if raw_city else None
    country = html_to_text(raw_country) if raw_country else None

    contract_duration = None
    if raw_duration is not None:
        try:
            contract_duration = int(raw_duration)
        except (ValueError, TypeError):
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
# DATABASE OPERATIONS (PostgreSQL)
# ==============================================================================

def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return url


def ensure_raw_offers_table(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS raw_offers (
                id          SERIAL PRIMARY KEY,
                source      TEXT NOT NULL,
                external_id TEXT NOT NULL,
                payload_json JSONB,
                scraped_at  TIMESTAMP,
                UNIQUE (source, external_id)
            )
        """)
    conn.commit()


def insert_raw_offers(conn: psycopg.Connection, rows: list[dict]) -> int:
    count = 0
    scraped_at = datetime.now(timezone.utc)

    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                """
                INSERT INTO raw_offers (source, external_id, payload_json, scraped_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (source, external_id) DO NOTHING
                """,
                (
                    row["source"],
                    row["external_id"],
                    json.dumps(row["payload_json"], ensure_ascii=False),
                    scraped_at,
                ),
            )
            if cur.rowcount == 1:
                count += 1

    conn.commit()
    return count


# ==============================================================================
# MAIN INGESTION
# ==============================================================================

def find_latest_raw_file() -> Optional[Path]:
    if not RAW_BF_DIR.exists():
        return None

    files = list(RAW_BF_DIR.glob("*.jsonl"))
    if not files:
        return None

    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return files[0]


def run_ingestion(raw_path: Optional[Path] = None) -> int:
    print("=" * 60)
    print("BUSINESS FRANCE INGESTION")
    print("=" * 60)

    database_url = get_database_url()

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

    rows = []
    id_stats = {"native": 0, "hash": 0}

    with open(raw_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                record = json.loads(line)
                payload = record.get("payload", {})

                offer = extract_offer_fields(payload)

                # VIE detection: inject is_vie as JSON boolean
                _mission_type = str(payload.get("missionType") or "").upper()
                payload["is_vie"] = (_mission_type == "VIE")

                id_stats[offer.pop("id_strategy")] += 1

                rows.append({
                    "source": "business_france",
                    "external_id": offer["id"],
                    "payload_json": payload,
                })

            except json.JSONDecodeError as e:
                print(f"[WARNING] Line {line_num}: Invalid JSON: {e}")
            except Exception as e:
                print(f"[WARNING] Line {line_num}: Error processing: {e}")

    print(f"[PARSE] Processed {len(rows)} offers from raw file")
    print(f"[ID] Strategies: native={id_stats['native']}, hash={id_stats['hash']}")
    print()

    if not rows:
        print("[WARNING] No offers to ingest")
        return 0

    print("[DB] Connecting to PostgreSQL...")
    with psycopg.connect(database_url) as conn:
        ensure_raw_offers_table(conn)
        count = insert_raw_offers(conn, rows)

    print()
    print("=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    print(f"Raw file: {raw_path}")
    print(f"Offers parsed: {len(rows)}")
    print(f"Offers inserted: {count}")
    print(f"ID strategies: native={id_stats['native']}, hash={id_stats['hash']}")

    return count


if __name__ == "__main__":
    raw_path = None
    if len(sys.argv) > 2 and sys.argv[1] == "--path":
        raw_path = Path(sys.argv[2])

    count = run_ingestion(raw_path)
    sys.exit(0 if count > 0 else 1)
