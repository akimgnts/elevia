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
import importlib
from pathlib import Path
from typing import Dict, List, Optional, Any

from .offer_skills import get_offer_skills_by_offer_ids
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

try:
    from compass.canonical.esco_bridge import build_canonical_esco_promoted
except ImportError:
    try:
        _esco_bridge = importlib.import_module("compass.canonical.esco_bridge")
        build_canonical_esco_promoted = _esco_bridge.build_canonical_esco_promoted
    except ImportError:
        build_canonical_esco_promoted = None

_RUNTIME_OFFER_GENERIC_IDS = {
    "skill:english",
    "skill:french",
    "skill:arabic",
    "skill:spanish",
    "skill:communication",
    "skill:data_analysis",
    "skill:analysis",
    "skill:management",
    "skill:project_management",
    "skill:reporting",
    "skill:coordination",
}
_RUNTIME_OFFER_GENERIC_LABELS = {
    "english",
    "french",
    "arabic",
    "spanish",
    "communication",
    "data analysis",
    "analysis",
    "management",
    "project management",
    "reporting",
    "coordination",
    "suivi",
    "gestion",
}


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


def _runtime_offer_skills_injection_enabled() -> bool:
    value = os.getenv("ELEVIA_RUNTIME_OFFER_SKILLS_INJECTION", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        key = str(value or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def _normalize_offer_skill_label(value: str) -> str:
    normalized = str(value or "").strip().lower()
    normalized = re.sub(r"[^\w\s\+#]", " ", normalized, flags=re.UNICODE)
    normalized = re.sub(r"\s+", " ", normalized, flags=re.UNICODE).strip()
    return normalized


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


def _extract_skills_uri_from_payload(payload: Dict[str, Any]) -> List[str]:
    raw = payload.get("skills_uri") or payload.get("esco_skills_uri") or []
    if isinstance(raw, list):
        return _dedupe_preserve_order([str(item) for item in raw if str(item or "").strip()])
    return []


def _fetch_business_france_offer_skills_rows(
    conn,
    external_ids: List[str],
) -> Dict[str, List[Dict[str, Any]]]:
    if not external_ids:
        return {}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (external_id, canonical_id)
                       external_id, canonical_id, label, importance_level, skill_type, source_method,
                       COALESCE(resolved_esco_uris, '[]'::jsonb)
                FROM offer_skills
                WHERE source = %s
                  AND external_id = ANY(%s)
                ORDER BY external_id, canonical_id, created_at DESC NULLS LAST
                """,
                ("business_france", list(external_ids)),
            )
            rows = cur.fetchall()
    except Exception:
        return {}

    mapping: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        external_id = str(row[0] or "").strip()
        canonical_id = str(row[1] or "").strip()
        label = str(row[2] or "").strip()
        if not external_id or not canonical_id or not label:
            continue
        mapping.setdefault(external_id, []).append(
            {
                "canonical_id": canonical_id,
                "label": label,
                "importance_level": str(row[3] or "").strip().upper() or "SECONDARY",
                "skill_type": str(row[4] or "").strip(),
                "source_method": str(row[5] or "").strip(),
                "resolved_esco_uris": [
                    str(uri)
                    for uri in (row[6] if isinstance(row[6], list) else [])
                    if str(uri or "").strip()
                ],
            }
        )
    return mapping


def _extract_runtime_offer_canonical_ids(rows: List[Dict[str, Any]]) -> List[str]:
    scored: List[tuple[int, str, str]] = []
    seen: set[str] = set()
    for row in rows:
        canonical_id = str(row.get("canonical_id") or "").strip()
        if not canonical_id or canonical_id in seen:
            continue
        label = _normalize_offer_skill_label(str(row.get("label") or ""))
        if canonical_id in _RUNTIME_OFFER_GENERIC_IDS:
            continue
        if label and label in _RUNTIME_OFFER_GENERIC_LABELS:
            continue
        seen.add(canonical_id)
        importance = str(row.get("importance_level") or "").strip().upper()
        score = 0 if importance == "CORE" else 1
        scored.append((score, canonical_id, label))
    scored.sort(key=lambda item: (item[0], item[2], item[1]))
    return [canonical_id for _, canonical_id, _ in scored]


def _apply_runtime_offer_skills_enrichment(
    offer: Dict[str, Any],
    skill_rows: List[Dict[str, Any]],
) -> None:
    if not _runtime_offer_skills_injection_enabled():
        return
    if not isinstance(offer, dict) or not skill_rows:
        return

    existing_uris = _dedupe_preserve_order([str(uri) for uri in (offer.get("skills_uri") or [])])
    existing_labels = _dedupe_preserve_order([str(label) for label in (offer.get("skills") or []) if str(label or "").strip()])
    row_labels = _dedupe_preserve_order([str(row.get("label") or "") for row in skill_rows if str(row.get("label") or "").strip()])
    row_precomputed_uris = _dedupe_preserve_order(
        [
            str(uri)
            for row in skill_rows
            for uri in (row.get("resolved_esco_uris") or [])
            if str(uri or "").strip()
        ]
    )

    canonical_ids = _extract_runtime_offer_canonical_ids(skill_rows)
    resolved_precomputed_ids = {
        str(row.get("canonical_id") or "").strip()
        for row in skill_rows
        if str(row.get("canonical_id") or "").strip() and (row.get("resolved_esco_uris") or [])
    }
    canonical_ids_to_bridge = [canonical_id for canonical_id in canonical_ids if canonical_id not in resolved_precomputed_ids]
    unresolved_labels: List[str] = []
    specialized_count = len(canonical_ids)
    injected_uris: List[str] = list(row_precomputed_uris)
    bridge_trace: Dict[str, Any] = {}

    if canonical_ids_to_bridge and build_canonical_esco_promoted:
        bridged_uris = build_canonical_esco_promoted(
            canonical_ids_to_bridge,
            base_skills_uri=_dedupe_preserve_order(existing_uris + row_precomputed_uris),
            _promote_override=True,
            trace=bridge_trace,
        ) or []
        injected_uris = _dedupe_preserve_order(
            list(row_precomputed_uris) + [str(uri) for uri in bridged_uris if str(uri or "").strip()]
        )

    unresolved_ids = set(bridge_trace.get("unresolved_canonical_ids") or [])
    unresolved_labels = [
        str(row.get("label") or "")
        for row in skill_rows
        if not (row.get("resolved_esco_uris") or [])
        and not str(row.get("canonical_id") or "").strip()
        and str(row.get("label") or "").strip()
    ]
    if unresolved_ids:
        unresolved_labels.extend(
            [
                str(row.get("label") or "")
                for row in skill_rows
                if str(row.get("canonical_id") or "").strip() in unresolved_ids
                and str(row.get("label") or "").strip()
            ]
        )
    unresolved_labels = _dedupe_preserve_order(unresolved_labels)

    if row_precomputed_uris and not bridge_trace.get("canonical_bridge_source"):
        bridge_trace["canonical_bridge_source"] = {
            str(row.get("canonical_id") or "").strip(): ["persisted_offer_skills_row_uri"]
            for row in skill_rows
            if str(row.get("canonical_id") or "").strip() in resolved_precomputed_ids
        }

    merged_labels = _dedupe_preserve_order(existing_labels + row_labels)
    if merged_labels and not offer.get("skills"):
        offer["skills"] = merged_labels
    elif merged_labels:
        offer["skills"] = merged_labels

    merged_uris = _dedupe_preserve_order(existing_uris + injected_uris)
    net_injected_count = len([uri for uri in merged_uris if uri not in set(existing_uris)])
    if merged_uris:
        offer["skills_uri"] = merged_uris

    if existing_uris and injected_uris:
        source = "payload_plus_offer_skills"
    elif existing_uris:
        source = "payload"
    elif injected_uris:
        source = "offer_skills_db"
    else:
        source = "offer_skills_labels_only"

    if merged_uris:
        offer["skills_source"] = source
    offer["runtime_offer_skills_uri_source"] = source
    offer["runtime_offer_injected_from_offer_skills"] = net_injected_count
    offer["runtime_offer_skills_uri_count"] = len(merged_uris)
    offer["runtime_offer_unresolved_skills"] = unresolved_labels
    offer["runtime_offer_specialized_count"] = specialized_count
    if bridge_trace.get("canonical_resolution_success") is not None:
        offer["runtime_offer_canonical_resolution_success"] = bridge_trace.get("canonical_resolution_success")
    if bridge_trace.get("canonical_bridge_source") is not None:
        offer["runtime_offer_canonical_bridge_source"] = bridge_trace.get("canonical_bridge_source")


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
                    SELECT c.external_id, c.source, c.title, c.description, c.company,
                           location, country, publication_date, start_date,
                           payload_json, contract_type,
                           e.needs_ai_review, e.job_family, e.primary_function, e.purity_score, e.hybrid_score
                    FROM clean_offers c
                    LEFT JOIN offer_domain_enrichment e
                      ON e.source = c.source AND e.external_id = c.external_id
                    WHERE c.source = %s
                    ORDER BY c.publication_date DESC NULLS LAST
                    """,
                    ("business_france",),
                )
                rows = cur.fetchall()
            offer_skills_rows = _fetch_business_france_offer_skills_rows(
                conn,
                [str(row[0]) for row in rows if row and row[0]],
            )
        offers = []
        for row in rows:
            if len(row) > 15:
                needs_review = bool(row[11]) if row[11] is not None else None
                job_family = row[12]
                primary_function = row[13]
                purity_score = float(row[14]) if row[14] is not None else None
                hybrid_score = float(row[15]) if row[15] is not None else None
            else:
                needs_review = None
                job_family = row[11] if len(row) > 11 else None
                primary_function = row[12] if len(row) > 12 else None
                purity_score = float(row[13]) if len(row) > 13 and row[13] is not None else None
                hybrid_score = float(row[14]) if len(row) > 14 and row[14] is not None else None
            offers.append(
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
                    "payload_json": json.dumps(row[9], ensure_ascii=False) if isinstance(row[9], dict) else row[9],
                    "contract_type": row[10],
                    "job_family": job_family,
                    "primary_function": primary_function,
                    "purity_score": purity_score,
                    "hybrid_score": hybrid_score,
                    "needs_review": needs_review,
                }
            )
        for offer in offers:
            _attach_payload_fields(offer)
            _apply_runtime_offer_skills_enrichment(
                offer,
                offer_skills_rows.get(str(offer.get("id") or ""), []),
            )
            offer.pop("payload_json", None)
        return offers
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

    payload_skills_uri = _extract_skills_uri_from_payload(payload)
    if payload_skills_uri and not offer.get("skills_uri"):
        offer["skills_uri"] = payload_skills_uri
        offer["skills_source"] = offer.get("skills_source") or "payload"

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
