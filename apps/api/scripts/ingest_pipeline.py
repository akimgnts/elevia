#!/usr/bin/env python3
"""
ingest_pipeline.py - France Travail ETL Pipeline
Sprint: Live Data Switch

Pipeline: RAW (JSONL, immutable) -> NORMALIZED (SQLite)

Usage:
    export FT_CLIENT_ID=...
    export FT_CLIENT_SECRET=...
    python3 apps/api/scripts/ingest_pipeline.py

Requires:
    - FT_CLIENT_ID and FT_CLIENT_SECRET in environment
    - Database initialized (will auto-init if missing)
"""

import json
import os
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.utils.offer_skills import ensure_offer_skills_table
from compass.offer_canonicalization import normalize_offers_to_uris

try:
    import requests
except ImportError:
    print("[ERROR] requests library not installed. Run: pip install requests")
    sys.exit(1)

# Paths
API_ROOT = Path(__file__).parent.parent
DATA_DIR = API_ROOT / "data"
RAW_FT_DIR = DATA_DIR / "raw" / "france_travail"
DB_PATH = DATA_DIR / "db" / "offers.db"

# France Travail API config
FT_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
FT_API_BASE = "https://api.francetravail.io/partenaire"
FT_SCOPES = "api_offresdemploiv2 o2dsoffre"


def get_ft_token(client_id: str, client_secret: str) -> str:
    """Get OAuth2 token from France Travail."""
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": FT_SCOPES,
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
                print(f"[FT] Token obtained (expires in {token_data.get('expires_in', '?')}s)")
                return token

        print(f"[FT] ERROR: Token request failed with status {r.status_code}")
        print(f"[FT] Response: {r.text[:300]}")
        return ""

    except requests.exceptions.Timeout:
        print("[FT] ERROR: Token request timeout")
        return ""
    except Exception as e:
        print(f"[FT] ERROR: Token request failed: {e}")
        return ""


def fetch_france_travail(limit: int = 150) -> int:
    """
    Fetch offers from France Travail API.

    1. Write RAW JSONL (immutable archive)
    2. UPSERT into SQLite

    Returns:
        Number of offers ingested
    """
    # Get credentials from env
    client_id = os.environ.get("FT_CLIENT_ID", "")
    client_secret = os.environ.get("FT_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print("[FT] ERROR: FT_CLIENT_ID and FT_CLIENT_SECRET must be set")
        return 0

    # Get token
    token = get_ft_token(client_id, client_secret)
    if not token:
        return 0

    # Fetch offers
    headers = {"Authorization": f"Bearer {token}"}
    # France Travail uses 0-indexed ranges, max 150 per request
    params = {"range": f"0-{min(limit - 1, 149)}"}
    url = f"{FT_API_BASE}/offresdemploi/v2/offres/search"

    print(f"[FT] Fetching offers from: {url}")
    print(f"[FT] Range: {params['range']}")

    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)

        # 200 = full response, 206 = partial content (paginated)
        if r.status_code in (200, 206):
            data = r.json()
            offers = data.get("resultats", [])
            print(f"[FT] Received {len(offers)} offers")

            if not offers:
                print("[FT] No offers returned")
                return 0

            # Write RAW JSONL (immutable archive)
            now = datetime.now(timezone.utc)
            date_str = now.strftime("%Y-%m-%d")
            timestamp = now.isoformat()

            RAW_FT_DIR.mkdir(parents=True, exist_ok=True)
            raw_file = RAW_FT_DIR / f"{date_str}.jsonl"

            with open(raw_file, "a", encoding="utf-8") as f:
                for offer in offers:
                    raw_record = {
                        "source": "france_travail",
                        "fetched_at": timestamp,
                        "payload": offer,
                    }
                    f.write(json.dumps(raw_record, ensure_ascii=False) + "\n")

            print(f"[FT] Raw data appended to: {raw_file}")

            # UPSERT into SQLite
            ingested = upsert_offers(offers, "france_travail", timestamp)
            return ingested

        elif r.status_code == 204:
            print("[FT] No content (204) - no offers match criteria")
            return 0
        else:
            print(f"[FT] ERROR: API returned status {r.status_code}")
            print(f"[FT] Response: {r.text[:300]}")
            return 0

    except requests.exceptions.Timeout:
        print("[FT] ERROR: API request timeout")
        return 0
    except Exception as e:
        print(f"[FT] ERROR: API request failed: {e}")
        return 0


def upsert_offers(offers: list, source: str, timestamp: str) -> int:
    """
    UPSERT offers into SQLite database.

    Args:
        offers: List of raw offer payloads
        source: 'france_travail' or 'business_france'
        timestamp: ISO timestamp for last_updated

    Returns:
        Number of offers upserted
    """
    if not DB_PATH.exists():
        print(f"[DB] Database not found at {DB_PATH}")
        print("[DB] Initializing database...")
        from db.init_db import init_database
        init_database()

    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    cursor = conn.cursor()
    count = 0
    ensure_offer_skills_table(conn)

    try:
        for offer in offers:
            # Build stable ID
            if source == "france_travail":
                raw_id = offer.get("id", "")
                offer_id = f"FT-{raw_id}" if raw_id else f"FT-{hash(json.dumps(offer, sort_keys=True))}"

                # Extract normalized fields from FT payload
                title = offer.get("intitule", "Sans titre")
                description = offer.get("description", "")

                # Company
                entreprise = offer.get("entreprise", {})
                company = entreprise.get("nom") or entreprise.get("entrepriseAdaptee") or None

                # Location
                lieu = offer.get("lieuTravail", {})
                city = lieu.get("libelle") or lieu.get("commune") or None
                country = "France"  # FT is France-only

                # Dates
                publication_date = offer.get("dateCreation") or offer.get("dateActualisation")

                # Contract duration (in months if available)
                duree = offer.get("dureeTravailLibelle") or ""
                contract_duration = None
                if "mois" in duree.lower():
                    try:
                        contract_duration = int("".join(filter(str.isdigit, duree.split("mois")[0])))
                    except ValueError:
                        pass

                start_date = None  # FT doesn't always provide this

            else:
                # Business France (future)
                offer_id = f"BF-{offer.get('id', hash(json.dumps(offer, sort_keys=True)))}"
                title = offer.get("title", "Sans titre")
                description = offer.get("description", "")
                company = offer.get("company")
                city = offer.get("city")
                country = offer.get("country")
                publication_date = offer.get("publication_date")
                contract_duration = offer.get("contract_duration")
                start_date = offer.get("start_date")

            # Payload JSON
            payload_json = json.dumps(offer, ensure_ascii=False)

            # UPSERT (INSERT OR REPLACE)
            cursor.execute("""
                INSERT OR REPLACE INTO fact_offers
                (id, source, title, description, company, city, country,
                 publication_date, contract_duration, start_date, payload_json, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                offer_id,
                source,
                title,
                description,
                company,
                city,
                country,
                publication_date,
                contract_duration,
                start_date,
                payload_json,
                timestamp,
            ))
            count += 1

            skill_candidates = (
                _extract_ft_skill_candidates(offer) if source == "france_travail"
                else _extract_bf_skill_candidates(offer)
            )
            offer_stub = {
                "id": offer_id,
                "title": title,
                "description": description or "",
                "skills": skill_candidates,
            }
            skills_from_payload = _normalize_offer_skills_for_ingest(offer_stub)
            if skills_from_payload:
                source_label = "france_travail" if source == "france_travail" else "manual"
                _insert_offer_skills(cursor, offer_id, skills_from_payload, source=source_label, timestamp=timestamp)

        conn.commit()
        print(f"[DB] Upserted {count} offers into fact_offers")
        return count

    except Exception as e:
        print(f"[DB] ERROR during upsert: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()


def _extract_ft_skill_candidates(offer: dict) -> list[str]:
    """Extract raw FT skills from payload (no normalization)."""
    skills: list[str] = []
    competences = offer.get("competences", [])
    if isinstance(competences, list):
        for comp in competences:
            if isinstance(comp, dict):
                label = comp.get("libelle") or comp.get("label")
                if label:
                    skills.append(str(label))
            elif isinstance(comp, str):
                skills.append(comp)
    return skills


def _extract_bf_skill_candidates(offer: dict) -> list[str]:
    """Extract raw BF skills from payload (no normalization)."""
    skills = offer.get("skills") or offer.get("competences") or []
    if isinstance(skills, list):
        return [str(s) for s in skills if s]
    return []


def _normalize_offer_skills_for_ingest(offer_stub: dict) -> list[tuple[str, str | None]]:
    """Canonical ESCO normalization (includes domain URIs for consistency)."""
    normalize_offers_to_uris([offer_stub], include_domain_uris=True)
    skills = offer_stub.get("skills") or []
    display = offer_stub.get("skills_display") or []
    uri_map: dict[str, str] = {}
    if isinstance(display, list):
        for item in display:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip().lower()
            uri = str(item.get("uri") or "").strip()
            if label and uri and label not in uri_map:
                uri_map[label] = uri
    out: list[tuple[str, str | None]] = []
    for s in skills:
        if not s:
            continue
        label = str(s)
        uri = uri_map.get(str(s).strip().lower())
        out.append((label, uri))
    return out


def _insert_offer_skills(
    cursor: sqlite3.Cursor,
    offer_id: str,
    skills: list[tuple[str, str | None]],
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


def run_pipeline() -> None:
    """
    Run the full ingestion pipeline.

    Currently: France Travail only
    Future: Business France support at schema level
    """
    print("=" * 60)
    print("ELEVIA INGEST PIPELINE")
    print(f"Started at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    # France Travail
    print("\n[PIPELINE] Source: France Travail")
    ft_count = fetch_france_travail(limit=150)

    # Summary
    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    print(f"France Travail: {ft_count} offers ingested")
    print(f"Business France: 0 offers (not implemented)")
    print(f"Total: {ft_count} offers")

    # Log result
    log_line = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "france_travail": ft_count,
        "business_france": 0,
        "total": ft_count,
    }
    print(f"\n[LOG] {json.dumps(log_line)}")


if __name__ == "__main__":
    run_pipeline()
