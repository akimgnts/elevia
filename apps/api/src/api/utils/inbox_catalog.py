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
from .generic_skills_filter import filter_skills_uri_for_scoring
from compass.offer_canonicalization import normalize_offers_to_uris
from offer.offer_cluster import detect_offer_cluster

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "db" / "offers.db"
MAX_DESCRIPTION_SNIPPET = 280
_CATALOG_CACHE: Optional[List[Dict]] = None
_CATALOG_CACHE_KEY: Optional[str] = None

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


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def _catalog_cache_key() -> str:
    if not DB_PATH.exists():
        return "db:missing"
    stat = DB_PATH.stat()
    return f"db:{stat.st_mtime_ns}:{stat.st_size}"


def _get_cached_catalog() -> Optional[List[Dict]]:
    global _CATALOG_CACHE, _CATALOG_CACHE_KEY
    cache_key = _catalog_cache_key()
    if _CATALOG_CACHE is None or _CATALOG_CACHE_KEY != cache_key:
        _CATALOG_CACHE = None
        _CATALOG_CACHE_KEY = cache_key
        return None
    return _CATALOG_CACHE


def _set_cached_catalog(offers: List[Dict]) -> List[Dict]:
    global _CATALOG_CACHE, _CATALOG_CACHE_KEY
    _CATALOG_CACHE = offers
    _CATALOG_CACHE_KEY = _catalog_cache_key()
    return offers


def _load_business_france_from_postgres() -> List[Dict]:
    database_url = _database_url()
    if not database_url:
        logger.error("[inbox] DATABASE_URL not set — Business France catalog unavailable")
        raise RuntimeError("DATABASE_URL not set")

    try:
        import psycopg

        with psycopg.connect(database_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT external_id, source, title, description, company,
                           location, country, publication_date, start_date
                    FROM clean_offers
                    WHERE source = %s
                    ORDER BY publication_date DESC NULLS LAST
                    """,
                    ("business_france",),
                )
                rows = cur.fetchall()
        return [
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
            }
            for row in rows
        ]
    except Exception as e:
        logger.error(f"[inbox] Business France catalog load failed (PostgreSQL): {e}")
        raise


def _load_france_travail_from_sqlite() -> List[Dict]:
    if not DB_PATH.exists():
        logger.error(f"[inbox] SQLite DB missing at {DB_PATH} — France Travail catalog unavailable")
        raise RuntimeError(f"SQLite DB missing at {DB_PATH}")
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=2)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=2000;")
        rows = conn.execute(
            "SELECT id, source, title, description, company, city, country, "
            "publication_date, contract_duration, start_date, payload_json FROM fact_offers "
            "WHERE source = 'france_travail'"
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
        return offers
    except Exception as e:
        logger.error(f"[inbox] France Travail catalog load failed (SQLite): {e}")
        raise


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


def _extract_skill_labels_for_cluster(offer: Dict) -> list:
    """Extract flat skill label list for cluster detection."""
    skills = offer.get("skills_display") or offer.get("skills") or []
    labels = []
    for item in skills:
        if isinstance(item, dict):
            label = str(item.get("label") or "").strip()
            if label:
                labels.append(label)
        elif isinstance(item, str) and item.strip():
            labels.append(item.strip())
    return labels


def _apply_esco_normalization(offers: List[Dict]) -> List[Dict]:
    """Apply ESCO extraction + normalization to all offers, and precompute offer_cluster."""
    offers_needing_normalization: List[Dict] = []
    for offer in offers:
        description_raw = offer.get("description") or offer.get("display_description") or ""
        description_clean = _clean_description(description_raw) if isinstance(description_raw, str) else ""
        offer["description"] = description_clean or (description_raw if isinstance(description_raw, str) else None)
        offer["description_snippet"] = _description_snippet(description_clean)
        precomputed_uris = offer.get("skills_uri") or []
        precomputed_skills = offer.get("skills") or []
        if precomputed_uris:
            offer["skills_source"] = offer.get("skills_source") or "precomputed"
            offer["skills_uri_count"] = len(precomputed_uris)
            offer["skills_uri_collapsed_dupes"] = int(offer.get("skills_uri_collapsed_dupes") or 0)
            offer["skills_unmapped"] = offer.get("skills_unmapped") or []
            offer["skills_unmapped_count"] = int(offer.get("skills_unmapped_count") or 0)
            if not offer.get("skills_display") and isinstance(precomputed_skills, list):
                offer["skills_display"] = [
                    {"label": str(skill), "source": "precomputed"}
                    for skill in precomputed_skills
                    if str(skill).strip()
                ]
        else:
            offers_needing_normalization.append(offer)

    if offers_needing_normalization:
        normalize_offers_to_uris(offers_needing_normalization)

    # Filter generic URIs from scoring set (flag-gated: ELEVIA_FILTER_GENERIC_URIS=1).
    # skills_display is NOT modified — user-visible labels are unaffected.
    # Applied after full normalization (including domain URIs) so domain signals survive.
    offers_touched = 0
    total_removed = 0
    removed_uri_counts: Dict[str, int] = {}
    for offer in offers:
        raw = offer.get("skills_uri") or []
        filtered = filter_skills_uri_for_scoring(raw)
        if filtered is not raw:
            removed = [u for u in raw if u not in set(filtered)]
            offer["skills_uri"] = filtered
            offer["skills_uri_count"] = len(filtered)
            offers_touched += 1
            total_removed += len(removed)
            for uri in removed:
                removed_uri_counts[uri] = removed_uri_counts.get(uri, 0) + 1
    if offers_touched:
        logger.info(
            "generic_skills_filter: offers_touched=%d total_uris_removed=%d breakdown=%s",
            offers_touched,
            total_removed,
            removed_uri_counts,
        )

    # Precompute offer_cluster once per catalog load — eliminates N+1 in inbox scoring loop
    for offer in offers:
        if not offer.get("offer_cluster"):
            try:
                cluster, _, _ = detect_offer_cluster(
                    offer.get("title"),
                    offer.get("description") or offer.get("display_description"),
                    _extract_skill_labels_for_cluster(offer),
                )
                offer["offer_cluster"] = cluster or "OTHER"
            except Exception:
                offer["offer_cluster"] = "OTHER"

    return offers


def load_catalog_offers() -> List[Dict]:
    """Load offers from PostgreSQL clean_offers (BF) and SQLite fact_offers (FT).

    Pipeline:
    1. Load each source independently; log errors explicitly
    2. If both sources fail, raise — never return a silently empty catalog
    3. Normalize all skills via ESCO referential
    """
    cached = _get_cached_catalog()
    if cached is not None:
        return cached

    bf_offers: List[Dict] = []
    ft_offers: List[Dict] = []
    bf_error: Optional[Exception] = None
    ft_error: Optional[Exception] = None

    try:
        bf_offers = _load_business_france_from_postgres()
    except Exception as e:
        bf_error = e

    try:
        ft_offers = _load_france_travail_from_sqlite()
    except Exception as e:
        ft_error = e

    if bf_error and ft_error:
        raise RuntimeError(
            f"[inbox] Both catalog sources unavailable — BF: {bf_error} | FT: {ft_error}"
        )

    combined = [*bf_offers, *ft_offers]
    combined.sort(key=lambda offer: str(offer.get("id") or ""))
    combined.sort(key=lambda offer: str(offer.get("publication_date") or ""), reverse=True)

    return _set_cached_catalog(_apply_esco_normalization(combined))


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
    catalog = load_catalog_offers()
    filtered = _filter_offers_in_memory(
        catalog,
        q_company=q_company,
        country=country,
        city=city,
        source=source,
        published_from=published_from,
        published_to=published_to,
    )
    filtered.sort(key=lambda o: str(o.get("id") or ""))
    filtered.sort(key=lambda o: str(o.get("publication_date") or ""), reverse=True)
    return filtered[offset : offset + limit] if limit else filtered[offset:]


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
    catalog = load_catalog_offers()
    if not catalog:
        return 0
    return len(
        _filter_offers_in_memory(
            catalog,
            q_company=q_company,
            country=country,
            city=city,
            source=source,
            published_from=published_from,
            published_to=published_to,
        )
    )
