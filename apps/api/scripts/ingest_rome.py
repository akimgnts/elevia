#!/usr/bin/env python3
"""
ingest_rome.py - France Travail ROME 4.0 Referential Ingestion
================================================================

Fetches ROME 4.0 metiers and competences from France Travail API
and stores them as a local SQLite snapshot for enrichment.

Usage:
    export FT_CLIENT_ID=...
    export FT_CLIENT_SECRET=...
    python3 apps/api/scripts/ingest_rome.py

Requires:
    - FT_CLIENT_ID and FT_CLIENT_SECRET in environment
    - api_romev1 scope activated on France Travail account

Tables created (in data/db/offers.db):
    - dim_rome_metier
    - dim_rome_competence
    - bridge_rome_metier_competence

This is an additive enrichment layer — it does NOT modify fact_offers
or any existing table.
"""

import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("[ERROR] requests library not installed. Run: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

API_ROOT = Path(__file__).parent.parent
DATA_DIR = API_ROOT / "data"
DB_PATH = DATA_DIR / "db" / "offers.db"

FT_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
FT_API_BASE = "https://api.francetravail.io/partenaire"

# ROME 4.0 endpoints (Metiers + Competences APIs)
ROME_METIERS_URL = f"{FT_API_BASE}/rome-metiers/v1/metiers/metier"
ROME_COMPETENCES_URL = f"{FT_API_BASE}/rome-competences/v1/competences/competence"

# Scopes needed for ROME APIs
ROME_SCOPES = "api_romev1 nomenclatureRome"

# Rate limit: 1 call/second as per FT docs
RATE_LIMIT_DELAY = 1.1


# ---------------------------------------------------------------------------
# Auth (same pattern as ingest_pipeline.py)
# ---------------------------------------------------------------------------

def get_ft_token(client_id: str, client_secret: str, scopes: str) -> str:
    """Get OAuth2 token from France Travail with given scopes."""
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": scopes,
    }
    try:
        r = requests.post(
            FT_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        if r.status_code == 200:
            token_data = r.json()
            token = token_data.get("access_token")
            if token:
                print(f"[AUTH] Token obtained (expires in {token_data.get('expires_in', '?')}s)")
                return token
        print(f"[AUTH] ERROR: Token request failed with status {r.status_code}")
        print(f"[AUTH] Response: {r.text[:500]}")
        return ""
    except requests.exceptions.Timeout:
        print("[AUTH] ERROR: Token request timeout")
        return ""
    except Exception as e:
        print(f"[AUTH] ERROR: Token request failed: {e}")
        return ""


def ft_get(url: str, token: str, params: dict | None = None, retries: int = 3) -> list | dict | None:
    """GET with retry + rate limit. Returns parsed JSON or None."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, params=params or {}, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 206:
                # Partial content (paginated) — still valid
                return r.json()
            if r.status_code == 429:
                wait = 2 ** attempt
                print(f"[API] Rate limited (429), waiting {wait}s...")
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                wait = 2 ** attempt
                print(f"[API] Server error {r.status_code}, retry {attempt+1}/{retries}...")
                time.sleep(wait)
                continue
            # Client error (400, 403, 404, etc.) — don't retry
            print(f"[API] ERROR {r.status_code}: {r.text[:300]}")
            return None
        except requests.exceptions.Timeout:
            print(f"[API] Timeout, retry {attempt+1}/{retries}...")
            time.sleep(2)
        except Exception as e:
            print(f"[API] ERROR: {e}")
            return None
    print("[API] All retries exhausted")
    return None


# ---------------------------------------------------------------------------
# Database schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS dim_rome_metier (
    rome_code    TEXT PRIMARY KEY,
    rome_label   TEXT NOT NULL,
    last_updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_rome_competence (
    competence_code  TEXT PRIMARY KEY,
    competence_label TEXT NOT NULL,
    esco_uri         TEXT,
    last_updated     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bridge_rome_metier_competence (
    rome_code       TEXT NOT NULL,
    competence_code TEXT NOT NULL,
    PRIMARY KEY (rome_code, competence_code),
    FOREIGN KEY (rome_code) REFERENCES dim_rome_metier(rome_code),
    FOREIGN KEY (competence_code) REFERENCES dim_rome_competence(competence_code)
);

CREATE INDEX IF NOT EXISTS idx_bridge_rome_code ON bridge_rome_metier_competence(rome_code);
CREATE INDEX IF NOT EXISTS idx_bridge_comp_code ON bridge_rome_metier_competence(competence_code);
"""


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create ROME tables if they don't exist. Does NOT touch fact_offers."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()


# ---------------------------------------------------------------------------
# Ingestion logic
# ---------------------------------------------------------------------------

def ingest_metiers(token: str, conn: sqlite3.Connection, now_iso: str) -> int:
    """Fetch all ROME metiers and UPSERT into dim_rome_metier.

    Returns count of rows upserted.
    """
    print("[METIERS] Fetching metiers list...")
    data = ft_get(ROME_METIERS_URL, token, params={"champs": "code,libelle"})

    if data is None:
        print("[METIERS] ERROR: No data returned")
        return 0

    # API may return a list directly or wrapped in a key
    records = data if isinstance(data, list) else data.get("metiers", data.get("resultats", []))
    if not isinstance(records, list):
        print(f"[METIERS] ERROR: Unexpected response type: {type(records)}")
        return 0

    count = 0
    cursor = conn.cursor()
    for rec in records:
        code = (rec.get("code") or "").strip()
        label = (rec.get("libelle") or "").strip()
        if not code or not label:
            continue
        cursor.execute(
            """INSERT INTO dim_rome_metier (rome_code, rome_label, last_updated)
               VALUES (?, ?, ?)
               ON CONFLICT(rome_code) DO UPDATE SET
                   rome_label = excluded.rome_label,
                   last_updated = excluded.last_updated""",
            (code, label, now_iso),
        )
        count += 1

    conn.commit()
    print(f"[METIERS] Upserted {count} metiers (skipped {len(records) - count} malformed)")
    return count


def ingest_competences(token: str, conn: sqlite3.Connection, now_iso: str) -> int:
    """Fetch all ROME competences and UPSERT into dim_rome_competence.

    Returns count of rows upserted.
    """
    print("[COMPETENCES] Fetching competences list...")
    data = ft_get(ROME_COMPETENCES_URL, token, params={"champs": "code,libelle,esco_uri"})

    if data is None:
        print("[COMPETENCES] ERROR: No data returned")
        return 0

    records = data if isinstance(data, list) else data.get("competences", data.get("resultats", []))
    if not isinstance(records, list):
        print(f"[COMPETENCES] ERROR: Unexpected response type: {type(records)}")
        return 0

    count = 0
    cursor = conn.cursor()
    for rec in records:
        code = (rec.get("code") or "").strip()
        label = (rec.get("libelle") or "").strip()
        if not code or not label:
            continue
        esco_uri = (rec.get("esco_uri") or rec.get("escoUri") or "").strip() or None
        cursor.execute(
            """INSERT INTO dim_rome_competence (competence_code, competence_label, esco_uri, last_updated)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(competence_code) DO UPDATE SET
                   competence_label = excluded.competence_label,
                   esco_uri = excluded.esco_uri,
                   last_updated = excluded.last_updated""",
            (code, label, esco_uri, now_iso),
        )
        count += 1

    conn.commit()
    print(f"[COMPETENCES] Upserted {count} competences (skipped {len(records) - count} malformed)")
    return count


def ingest_metier_competences(token: str, conn: sqlite3.Connection) -> int:
    """For each metier, fetch its linked competences and populate the bridge table.

    Uses the fiches-metiers API to get competence links per metier.
    Returns count of links inserted.
    """
    # Get all rome_codes already in dim_rome_metier
    rows = conn.execute("SELECT rome_code FROM dim_rome_metier").fetchall()
    rome_codes = [r[0] for r in rows]

    if not rome_codes:
        print("[BRIDGE] No metiers in DB — skipping bridge ingestion")
        return 0

    print(f"[BRIDGE] Fetching competence links for {len(rome_codes)} metiers...")
    fiches_url = f"{FT_API_BASE}/rome-fiches-metiers/v1/fiches-metiers/fiche-metier"

    cursor = conn.cursor()
    total_links = 0
    errors = 0

    for i, rome_code in enumerate(rome_codes):
        if i > 0 and i % 50 == 0:
            print(f"[BRIDGE] Progress: {i}/{len(rome_codes)} metiers processed ({total_links} links)")
            conn.commit()

        url = f"{fiches_url}/{rome_code}"
        data = ft_get(url, token, params={"champs": "code,competenceMobilisees"})
        time.sleep(RATE_LIMIT_DELAY)

        if data is None:
            errors += 1
            if errors > 20:
                print("[BRIDGE] Too many errors — stopping bridge ingestion")
                break
            continue

        # Extract competences from fiche metier response
        competences = []
        # The API may return competences under different keys
        for key in ("competenceMobilisees", "competencesMobilisees", "competences", "groupesCompetences"):
            val = data.get(key)
            if val:
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict):
                            # Could be grouped: {"competences": [...]}
                            sub = item.get("competences", [])
                            if isinstance(sub, list):
                                competences.extend(sub)
                            else:
                                competences.append(item)
                        elif isinstance(item, str):
                            competences.append({"code": item})
                break

        for comp in competences:
            comp_code = ""
            if isinstance(comp, dict):
                comp_code = (comp.get("code") or comp.get("codeCompetence") or "").strip()
            elif isinstance(comp, str):
                comp_code = comp.strip()

            if not comp_code:
                continue

            cursor.execute(
                """INSERT OR IGNORE INTO bridge_rome_metier_competence (rome_code, competence_code)
                   VALUES (?, ?)""",
                (rome_code, comp_code),
            )
            total_links += 1

    conn.commit()
    print(f"[BRIDGE] Inserted {total_links} metier-competence links ({errors} fetch errors)")
    return total_links


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_rome_ingestion() -> None:
    """Run the full ROME referential ingestion."""
    print("=" * 60)
    print("ELEVIA — ROME 4.0 REFERENTIAL INGESTION")
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    print(f"Started at: {now_iso}")
    print("=" * 60)

    # Credentials
    client_id = os.environ.get("FT_CLIENT_ID", "")
    client_secret = os.environ.get("FT_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        print("[ERROR] FT_CLIENT_ID and FT_CLIENT_SECRET must be set in environment")
        sys.exit(1)

    # Auth
    token = get_ft_token(client_id, client_secret, ROME_SCOPES)
    if not token:
        print("[ERROR] Could not obtain OAuth2 token. Is api_romev1 scope activated?")
        sys.exit(1)

    # DB
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    ensure_schema(conn)

    # Step 1: Metiers
    print("\n" + "-" * 40)
    metiers_count = ingest_metiers(token, conn, now_iso)

    time.sleep(RATE_LIMIT_DELAY)

    # Step 2: Competences
    print("\n" + "-" * 40)
    competences_count = ingest_competences(token, conn, now_iso)

    time.sleep(RATE_LIMIT_DELAY)

    # Step 3: Bridge (metier → competence links via fiches-metiers)
    print("\n" + "-" * 40)
    bridge_count = ingest_metier_competences(token, conn)

    conn.close()

    # Summary
    print("\n" + "=" * 60)
    print("ROME INGESTION SUMMARY")
    print("=" * 60)
    print(f"  Metiers:     {metiers_count}")
    print(f"  Competences: {competences_count}")
    print(f"  Links:       {bridge_count}")
    print(f"  DB:          {DB_PATH}")
    print(f"  Timestamp:   {now_iso}")

    log_line = {
        "timestamp": now_iso,
        "job": "rome_ingestion",
        "metiers": metiers_count,
        "competences": competences_count,
        "links": bridge_count,
    }
    print(f"\n[LOG] {json.dumps(log_line)}")


if __name__ == "__main__":
    run_rome_ingestion()
