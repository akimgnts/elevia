#!/usr/bin/env python3
"""
build_clean_offers.py - Build clean_offers from raw_offers (Business France)

Reads raw_offers WHERE source = 'business_france', normalizes each payload,
and upserts into clean_offers.  raw_offers is never modified.

Usage:
    python3 apps/api/scripts/build_clean_offers.py

Requires DATABASE_URL environment variable.
"""

import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

import psycopg

API_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(API_ROOT / "src"))


# ==============================================================================
# DATABASE HELPERS
# ==============================================================================

def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return url


def ensure_clean_offers_table(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clean_offers (
                id               BIGSERIAL PRIMARY KEY,
                source           TEXT NOT NULL,
                external_id      TEXT NOT NULL,
                title            TEXT,
                company          TEXT,
                location         TEXT,
                country          TEXT,
                contract_type    TEXT,
                description      TEXT,
                mission_profile  TEXT,
                publication_date TIMESTAMPTZ NULL,
                start_date       DATE NULL,
                salary           TEXT NULL,
                url              TEXT NULL,
                payload_json     JSONB NOT NULL,
                cleaned_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (source, external_id)
            )
        """)
        cur.execute(
            "ALTER TABLE clean_offers ADD COLUMN IF NOT EXISTS mission_profile TEXT"
        )
    conn.commit()


# ==============================================================================
# FIELD EXTRACTION HELPERS
# ==============================================================================

def _first(payload: dict, *keys: str, default: Any = None) -> Any:
    for k in keys:
        v = payload.get(k)
        if v is not None and str(v).strip():
            return v
    return default


def _parse_date(raw: Any) -> Optional[date]:
    if not raw:
        return None
    s = str(raw).strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _parse_timestamptz(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    s = str(raw).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[:19], fmt[:len(s[:19])])
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _clean_text(val: Any) -> Optional[str]:
    if val is None:
        return None
    text = re.sub(r"<[^>]+>", " ", str(val))
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text or None


# ==============================================================================
# TRANSFORM
# ==============================================================================

def transform_bf(payload: dict) -> dict:
    title = _clean_text(_first(payload, "title", "intitule", "poste", "name"))
    company = _clean_text(_first(payload, "company", "entreprise", "companyName", "societe"))
    location = _clean_text(_first(payload, "city", "ville", "location", "lieu"))
    country = _clean_text(_first(payload, "country", "pays", "countryName"))
    description = _clean_text(_first(payload, "description", "descriptif", "content", "details"))
    mission_profile = _clean_text(_first(payload, "missionProfile", "profil", "profile", "profileDescription"))
    url = _clean_text(_first(payload, "url", "applyUrl", "link", "jobUrl"))
    salary = _clean_text(_first(payload, "salary", "salaire", "remuneration", "compensation"))

    raw_contract = _first(payload, "contractType", "contract_type", "typeContrat", "missionType")
    contract_type = _clean_text(raw_contract)

    raw_pub = _first(payload, "publicationDate", "publication_date", "dateCreation", "createdAt")
    publication_date = _parse_timestamptz(raw_pub)

    raw_start = _first(payload, "startDate", "start_date", "dateDebut")
    start_date = _parse_date(raw_start)

    return {
        "title": title,
        "company": company,
        "location": location,
        "country": country,
        "contract_type": contract_type,
        "description": description,
        "mission_profile": mission_profile,
        "publication_date": publication_date,
        "start_date": start_date,
        "salary": salary,
        "url": url,
    }


# ==============================================================================
# READ + UPSERT
# ==============================================================================

def fetch_raw_offers(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT external_id, payload_json FROM raw_offers WHERE source = 'business_france'"
        )
        return [{"external_id": row[0], "payload_json": row[1]} for row in cur.fetchall()]


def upsert_clean_offers(conn: psycopg.Connection, rows: list[dict]) -> int:
    count = 0
    with conn.cursor() as cur:
        for row in rows:
            fields = transform_bf(row["payload_json"])
            cur.execute(
                """
                INSERT INTO clean_offers (
                    source, external_id,
                    title, company, location, country, contract_type,
                    description, mission_profile, publication_date, start_date, salary, url,
                    payload_json
                ) VALUES (
                    'business_france', %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s
                )
                ON CONFLICT (source, external_id) DO UPDATE SET
                    title            = EXCLUDED.title,
                    company          = EXCLUDED.company,
                    location         = EXCLUDED.location,
                    country          = EXCLUDED.country,
                    contract_type    = EXCLUDED.contract_type,
                    description      = EXCLUDED.description,
                    mission_profile  = EXCLUDED.mission_profile,
                    publication_date = EXCLUDED.publication_date,
                    start_date       = EXCLUDED.start_date,
                    salary           = EXCLUDED.salary,
                    url              = EXCLUDED.url,
                    payload_json     = EXCLUDED.payload_json,
                    cleaned_at       = NOW()
                """,
                (
                    row["external_id"],
                    fields["title"],
                    fields["company"],
                    fields["location"],
                    fields["country"],
                    fields["contract_type"],
                    fields["description"],
                    fields["mission_profile"],
                    fields["publication_date"],
                    fields["start_date"],
                    fields["salary"],
                    fields["url"],
                    json.dumps(row["payload_json"], ensure_ascii=False),
                ),
            )
            count += cur.rowcount
    conn.commit()
    return count


# ==============================================================================
# MAIN
# ==============================================================================

def run() -> None:
    print("=" * 60)
    print("BUILD CLEAN OFFERS — business_france")
    print("=" * 60)

    database_url = get_database_url()

    with psycopg.connect(database_url) as conn:
        ensure_clean_offers_table(conn)

        print("[READ] Fetching raw_offers WHERE source = 'business_france'...")
        raw_rows = fetch_raw_offers(conn)
        print(f"[READ] {len(raw_rows)} rows found")

        if not raw_rows:
            print("[WARN] Nothing to process — exiting")
            return

        print("[UPSERT] Transforming and upserting into clean_offers...")
        affected = upsert_clean_offers(conn, raw_rows)



if __name__ == "__main__":
    run()
    sys.exit(0)
