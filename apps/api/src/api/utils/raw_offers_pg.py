"""
raw_offers_pg.py - Minimal PostgreSQL persistence for scraped raw offers.

This keeps raw scraped payloads in PostgreSQL via DATABASE_URL while the
existing SQLite flow remains in place as a temporary safety net.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


CREATE_RAW_OFFERS_SQL = """
CREATE TABLE IF NOT EXISTS raw_offers (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    scraped_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_raw_offers_source_external_id UNIQUE (source, external_id)
);
"""

CREATE_RAW_OFFERS_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_raw_offers_source_scraped_at
ON raw_offers (source, scraped_at DESC);
"""

UPSERT_RAW_OFFER_SQL = """
INSERT INTO raw_offers (source, external_id, payload_json, scraped_at)
VALUES (%s, %s, %s::jsonb, %s)
ON CONFLICT (source, external_id)
DO UPDATE SET
    payload_json = EXCLUDED.payload_json,
    scraped_at = EXCLUDED.scraped_at,
    updated_at = NOW();
"""


@dataclass
class PersistResult:
    attempted: int
    persisted: int
    error: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_database_url() -> str | None:
    value = os.getenv("DATABASE_URL", "").strip()
    return value or None


def _connect(database_url: str):
    import psycopg

    return psycopg.connect(database_url)


def ensure_raw_offers_table(conn) -> None:
    with conn.cursor() as cursor:
        cursor.execute(CREATE_RAW_OFFERS_SQL)
        cursor.execute(CREATE_RAW_OFFERS_INDEX_SQL)


def _stable_payload_hash(source: str, payload: Mapping[str, Any]) -> str:
    stable_json = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha1(f"{source}:{stable_json}".encode("utf-8")).hexdigest()


def build_external_id(source: str, payload: Mapping[str, Any]) -> str:
    if source == "france_travail":
        raw_id = payload.get("id")
        if raw_id is not None and str(raw_id).strip():
            return str(raw_id).strip()

    if source == "business_france":
        for key in ("id", "offerId", "reference", "ref", "uuid", "slug"):
            raw_id = payload.get(key)
            if raw_id is not None and str(raw_id).strip():
                return str(raw_id).strip()

    raw_id = payload.get("id")
    if raw_id is not None and str(raw_id).strip():
        return str(raw_id).strip()

    return _stable_payload_hash(source, payload)


def persist_raw_offers_with_connection(
    conn,
    source: str,
    offers: Iterable[Mapping[str, Any]],
    scraped_at: str,
) -> PersistResult:
    attempted = 0
    persisted = 0

    ensure_raw_offers_table(conn)

    with conn.cursor() as cursor:
        for offer in offers:
            attempted += 1
            payload = dict(offer)
            external_id = build_external_id(source, payload)
            payload_json = json.dumps(payload, ensure_ascii=False, default=str)
            cursor.execute(
                UPSERT_RAW_OFFER_SQL,
                (source, external_id, payload_json, scraped_at),
            )
            persisted += 1

    conn.commit()
    return PersistResult(attempted=attempted, persisted=persisted)


def persist_raw_offer_records_with_connection(
    conn,
    source: str,
    records: Iterable[Mapping[str, Any]],
    default_scraped_at: str | None = None,
) -> PersistResult:
    attempted = 0
    persisted = 0

    ensure_raw_offers_table(conn)

    with conn.cursor() as cursor:
        for record in records:
            attempted += 1
            payload_obj = record.get("payload")
            payload = payload_obj if isinstance(payload_obj, Mapping) else record
            payload = dict(payload)
            scraped_at = (
                record.get("scraped_at")
                or record.get("fetched_at")
                or default_scraped_at
                or _utc_now()
            )
            external_id = record.get("external_id") or build_external_id(source, payload)
            payload_json = json.dumps(payload, ensure_ascii=False, default=str)
            cursor.execute(
                UPSERT_RAW_OFFER_SQL,
                (source, external_id, payload_json, scraped_at),
            )
            persisted += 1

    conn.commit()
    return PersistResult(attempted=attempted, persisted=persisted)


def persist_raw_offers(
    source: str,
    offers: Iterable[Mapping[str, Any]],
    scraped_at: str,
    *,
    database_url: str | None = None,
) -> PersistResult:
    offer_list = [dict(offer) for offer in offers]
    url = database_url or get_database_url()
    if not url:
        return PersistResult(
            attempted=len(offer_list),
            persisted=0,
            error="DATABASE_URL is not set",
        )

    conn = None
    try:
        conn = _connect(url)
        return persist_raw_offers_with_connection(conn, source, offer_list, scraped_at)
    except Exception as exc:
        return PersistResult(
            attempted=len(offer_list),
            persisted=0,
            error=str(exc),
        )
    finally:
        if conn is not None:
            conn.close()


def persist_raw_offer_records(
    source: str,
    records: Iterable[Mapping[str, Any]],
    *,
    default_scraped_at: str | None = None,
    database_url: str | None = None,
) -> PersistResult:
    record_list = [dict(record) for record in records]
    url = database_url or get_database_url()
    if not url:
        return PersistResult(
            attempted=len(record_list),
            persisted=0,
            error="DATABASE_URL is not set",
        )

    conn = None
    try:
        conn = _connect(url)
        return persist_raw_offer_records_with_connection(
            conn,
            source,
            record_list,
            default_scraped_at=default_scraped_at,
        )
    except Exception as exc:
        return PersistResult(
            attempted=len(record_list),
            persisted=0,
            error=str(exc),
        )
    finally:
        if conn is not None:
            conn.close()
