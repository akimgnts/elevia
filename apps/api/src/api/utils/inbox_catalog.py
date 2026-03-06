"""
Inbox catalog loader (shared by runtime route and smoke scripts).

Sprint 7 - ESCO extraction + normalization for offers.
"""

import json
import os
import sqlite3
import logging
import html
import re
from pathlib import Path
from typing import Dict, List, Optional

from .offer_skills import get_offer_skills_by_offer_ids
from compass.offer_canonicalization import normalize_offers_to_uris

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "db" / "offers.db"
VIE_FIXTURES_PATH = Path(__file__).parent.parent.parent.parent / "fixtures" / "offers" / "vie_catalog.json"
VIE_FIXTURES_ENV = "ELEVIA_INBOX_USE_VIE_FIXTURES"
MAX_DESCRIPTION_SNIPPET = 280

_BR_RE = re.compile(r"(?i)<br\\s*/?>")
_P_OPEN_RE = re.compile(r"(?i)<p[^>]*>")
_P_CLOSE_RE = re.compile(r"(?i)</p>")
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\\s+")


def _clean_description(text: str) -> str:
    if not text:
        return ""
    raw = html.unescape(str(text))
    raw = _BR_RE.sub("\n", raw)
    raw = _P_CLOSE_RE.sub("\n", raw)
    raw = _P_OPEN_RE.sub("", raw)
    raw = _TAG_RE.sub(" ", raw)
    lines = []
    for line in raw.splitlines():
        clean_line = _WS_RE.sub(" ", line).strip()
        if clean_line:
            lines.append(clean_line)
    return "\n\n".join(lines)


def _description_snippet(text: str, limit: int = MAX_DESCRIPTION_SNIPPET) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _use_vie_fixtures() -> bool:
    value = os.getenv(VIE_FIXTURES_ENV, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _load_vie_fixtures() -> List[Dict]:
    if not VIE_FIXTURES_PATH.exists():
        logger.warning(f"[inbox] VIE fixtures missing at {VIE_FIXTURES_PATH}")
        return []
    try:
        raw = VIE_FIXTURES_PATH.read_text(encoding="utf-8")
        offers = json.loads(raw)
        if not isinstance(offers, list):
            logger.warning(f"[inbox] VIE fixtures not a list: {type(offers)}")
            return []
        return offers
    except Exception as e:
        logger.warning(f"[inbox] Failed to load VIE fixtures: {e}")
        return []


def _extract_skills_from_payload(payload: Dict) -> List[str]:
    skills = payload.get("skills") or payload.get("required_skills") or []
    if isinstance(skills, list) and skills:
        return [str(s) for s in skills if isinstance(s, (str, int, float))]
    competences = payload.get("competences") or []
    if isinstance(competences, list) and competences:
        extracted = []
        for comp in competences:
            if isinstance(comp, dict) and comp.get("libelle"):
                extracted.append(str(comp["libelle"]))
            elif isinstance(comp, str):
                extracted.append(comp)
        return extracted
    return []


def _extract_languages_from_payload(payload: Dict) -> List[str]:
    languages = payload.get("languages") or payload.get("required_languages") or []
    if isinstance(languages, list) and languages:
        return [str(l) for l in languages if isinstance(l, (str, int, float))]
    if isinstance(languages, str):
        return [l.strip() for l in languages.split(",") if l.strip()]
    return []


def _extract_education_from_payload(payload: Dict) -> str | None:
    education = payload.get("education_level") or payload.get("education")
    if isinstance(education, str):
        return education
    return None


def _attach_payload_fields(offer: Dict) -> None:
    payload_raw = offer.get("payload_json")
    if not payload_raw or not isinstance(payload_raw, str):
        return
    try:
        payload = json.loads(payload_raw)
    except Exception:
        return

    if offer.get("is_vie") is None and isinstance(payload.get("is_vie"), bool):
        offer["is_vie"] = payload.get("is_vie")

    if not offer.get("skills"):
        offer["skills"] = _extract_skills_from_payload(payload)

    if not offer.get("languages"):
        offer["languages"] = _extract_languages_from_payload(payload)

    if not offer.get("education"):
        education = _extract_education_from_payload(payload)
        if education:
            offer["education"] = education


def _apply_esco_normalization(offers: List[Dict]) -> List[Dict]:
    """Apply ESCO extraction + normalization to all offers."""
    for offer in offers:
        description_raw = offer.get("description") or offer.get("display_description") or ""
        description_clean = _clean_description(description_raw) if isinstance(description_raw, str) else ""
        offer["description"] = description_clean or (description_raw if isinstance(description_raw, str) else None)
        offer["description_snippet"] = _description_snippet(description_clean)

    normalize_offers_to_uris(offers)
    return offers


def load_catalog_offers() -> List[Dict]:
    """Load offers from fact_offers with payload mapping + fixture fallback.

    Pipeline:
    1. Load from DB or VIE fixtures
    2. Extract skills from payload_json (if not already present)
    3. Normalize all skills via ESCO referential
    """
    if _use_vie_fixtures():
        fixtures = _load_vie_fixtures()
        if fixtures:
            return _apply_esco_normalization(fixtures)

    if not DB_PATH.exists():
        fixtures = _load_vie_fixtures()
        return _apply_esco_normalization(fixtures) if fixtures else []

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=2)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=2000;")
        rows = conn.execute(
            "SELECT id, source, title, description, company, city, country, "
            "publication_date, contract_duration, start_date, payload_json FROM fact_offers"
        ).fetchall()
        offers = [dict(r) for r in rows]

        offer_ids = [str(o.get("id") or "") for o in offers]
        skills_map = get_offer_skills_by_offer_ids(conn, offer_ids)
        for offer in offers:
            offer_id = str(offer.get("id") or "")
            if offer_id in skills_map:
                entry = skills_map[offer_id]
                if entry.get("skills_uri"):
                    offer["skills_uri"] = entry["skills_uri"]
                if entry.get("skills"):
                    offer["skills"] = entry["skills"]
            _attach_payload_fields(offer)
            offer.pop("payload_json", None)

        conn.close()

        if not offers:
            fixtures = _load_vie_fixtures()
            return _apply_esco_normalization(fixtures) if fixtures else []

        if not any(offer.get("is_vie") is True for offer in offers):
            fixtures = _load_vie_fixtures()
            if fixtures:
                return _apply_esco_normalization(fixtures)

        return _apply_esco_normalization(offers)
    except Exception as e:
        logger.warning(f"[inbox] Failed to load catalog: {e}")
        fixtures = _load_vie_fixtures()
        return _apply_esco_normalization(fixtures) if fixtures else []


def _filter_offers_in_memory(
    offers: List[Dict],
    *,
    q_company: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    source: Optional[str] = None,
    published_from: Optional[str] = None,
    published_to: Optional[str] = None,
) -> List[Dict]:
    def _norm(value: Optional[str]) -> str:
        return str(value or "").strip().lower()

    q_company_norm = _norm(q_company)
    country_norm = _norm(country)
    city_norm = _norm(city)
    source_norm = _norm(source)

    results: List[Dict] = []
    for offer in offers:
        if q_company_norm:
            company_val = _norm(offer.get("company"))
            if q_company_norm not in company_val:
                continue
        if country_norm:
            if _norm(offer.get("country")) != country_norm:
                continue
        if city_norm:
            if _norm(offer.get("city")) != city_norm:
                continue
        if source_norm:
            if _norm(offer.get("source")) != source_norm:
                continue
        pub_date = offer.get("publication_date")
        if published_from and pub_date and str(pub_date) < published_from:
            continue
        if published_to and pub_date and str(pub_date) >= published_to:
            continue
        results.append(offer)
    return results


def load_catalog_offers_filtered(
    *,
    q_company: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    source: Optional[str] = None,
    published_from: Optional[str] = None,
    published_to: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> List[Dict]:
    """
    Load offers with SQL prefilter (company/country/city/date/source), then normalize.

    Falls back to fixtures or in-memory filtering when DB is missing.
    """
    if _use_vie_fixtures():
        fixtures = _load_vie_fixtures()
        if fixtures:
            filtered = _filter_offers_in_memory(
                fixtures,
                q_company=q_company,
                country=country,
                city=city,
                source=source,
                published_from=published_from,
                published_to=published_to,
            )
            filtered = filtered[offset : offset + limit] if limit else filtered[offset:]
            return _apply_esco_normalization(filtered)

    if not DB_PATH.exists():
        fixtures = _load_vie_fixtures()
        if fixtures:
            filtered = _filter_offers_in_memory(
                fixtures,
                q_company=q_company,
                country=country,
                city=city,
                source=source,
                published_from=published_from,
                published_to=published_to,
            )
            filtered = filtered[offset : offset + limit] if limit else filtered[offset:]
            return _apply_esco_normalization(filtered)
        return []

    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=2)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=2000;")

        where_clauses: List[str] = []
        params: List[object] = []

        if q_company:
            where_clauses.append("LOWER(company) LIKE ?")
            params.append(f"%{q_company.strip().lower()}%")
        if country:
            where_clauses.append("LOWER(country) = ?")
            params.append(country.strip().lower())
        if city:
            where_clauses.append("LOWER(city) = ?")
            params.append(city.strip().lower())
        if source:
            where_clauses.append("source = ?")
            params.append(source)
        if published_from:
            where_clauses.append("publication_date >= ?")
            params.append(published_from)
        if published_to:
            where_clauses.append("publication_date < ?")
            params.append(published_to)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"""
            SELECT id, source, title, description, company, city, country,
                   publication_date, contract_duration, start_date, payload_json
            FROM fact_offers
            {where_sql}
            ORDER BY publication_date DESC, id ASC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        offers = [dict(r) for r in rows]

        offer_ids = [str(o.get("id") or "") for o in offers]
        skills_map = get_offer_skills_by_offer_ids(conn, offer_ids)
        for offer in offers:
            offer_id = str(offer.get("id") or "")
            if offer_id in skills_map:
                entry = skills_map[offer_id]
                if entry.get("skills_uri"):
                    offer["skills_uri"] = entry["skills_uri"]
                if entry.get("skills"):
                    offer["skills"] = entry["skills"]
            _attach_payload_fields(offer)
            offer.pop("payload_json", None)

        conn.close()

        if not offers:
            fixtures = _load_vie_fixtures()
            return _apply_esco_normalization(fixtures) if fixtures else []

        return _apply_esco_normalization(offers)
    except Exception as e:
        logger.warning(f"[inbox] Failed to load filtered catalog: {e}")
        fixtures = _load_vie_fixtures()
        return _apply_esco_normalization(fixtures) if fixtures else []


def count_catalog_offers_filtered(
    *,
    q_company: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    source: Optional[str] = None,
    published_from: Optional[str] = None,
    published_to: Optional[str] = None,
) -> Optional[int]:
    """Return COUNT(*) for prefilter, or None when unavailable."""
    if _use_vie_fixtures() or not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=2)
        conn.row_factory = sqlite3.Row
        where_clauses: List[str] = []
        params: List[object] = []

        if q_company:
            where_clauses.append("LOWER(company) LIKE ?")
            params.append(f"%{q_company.strip().lower()}%")
        if country:
            where_clauses.append("LOWER(country) = ?")
            params.append(country.strip().lower())
        if city:
            where_clauses.append("LOWER(city) = ?")
            params.append(city.strip().lower())
        if source:
            where_clauses.append("source = ?")
            params.append(source)
        if published_from:
            where_clauses.append("publication_date >= ?")
            params.append(published_from)
        if published_to:
            where_clauses.append("publication_date < ?")
            params.append(published_to)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = f"SELECT COUNT(*) as cnt FROM fact_offers {where_sql}"
        row = conn.execute(query, params).fetchone()
        conn.close()
        return int(row["cnt"]) if row and row["cnt"] is not None else None
    except Exception:
        return None
