"""
clean_offers_pg.py - Minimal deterministic loader from raw_offers to clean_offers.

Scope:
- source = business_france only
- upsert by (source, external_id)
- preserve payload_json
- preserve contract_type and payload_json.is_vie
- no scoring / skills_uri / enrichment logic
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


_WS_RE = re.compile(r"\s+")


@dataclass
class LoadResult:
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


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return _WS_RE.sub(" ", text)


def _date_only(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if "T" in text:
        return text.split("T", 1)[0]
    return text[:10] if len(text) >= 10 else text


def _resolve_location(payload: Mapping[str, Any]) -> str | None:
    return _clean_text(
        payload.get("city")
        or payload.get("cityName")
        or payload.get("cityAffectation")
        or payload.get("location")
    )


def _resolve_contract_type(payload: Mapping[str, Any]) -> str | None:
    mission_type = _clean_text(payload.get("missionType") or payload.get("contract_type"))
    if mission_type:
        return mission_type
    if payload.get("is_vie") is True:
        return "VIE"
    if payload.get("is_vie") is False:
        return "VIA"
    return None


def build_clean_offer_record(
    *,
    source: str,
    external_id: str,
    payload: Mapping[str, Any],
    cleaned_at: str | None = None,
) -> dict[str, Any]:
    if source != "business_france":
        raise ValueError(f"Unsupported source for clean_offers loader: {source}")

    return {
        "source": source,
        "external_id": str(external_id).strip(),
        "title": _clean_text(payload.get("title")),
        "company": _clean_text(payload.get("company") or payload.get("organizationName")),
        "location": _resolve_location(payload),
        "country": _clean_text(payload.get("country") or payload.get("countryName")),
        "contract_type": _resolve_contract_type(payload),
        "description": _clean_text(payload.get("description") or payload.get("missionDescription")),
        "publication_date": _clean_text(payload.get("publicationDate") or payload.get("creationDate")),
        "start_date": _date_only(payload.get("startDate") or payload.get("missionStartDate")),
        "salary": _clean_text(payload.get("indemnite") or payload.get("salary")),
        "url": _clean_text(payload.get("offerUrl") or payload.get("contactURL")),
        "payload_json": dict(payload),
        "cleaned_at": cleaned_at or _utc_now(),
    }


def ensure_clean_offers_table(conn, *, table_name: str = "clean_offers") -> None:
    from psycopg import sql

    with conn.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id BIGSERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT,
                    company TEXT,
                    location TEXT,
                    country TEXT,
                    contract_type TEXT,
                    description TEXT,
                    publication_date TIMESTAMPTZ,
                    start_date DATE,
                    salary TEXT,
                    url TEXT,
                    payload_json JSONB NOT NULL,
                    cleaned_at TIMESTAMPTZ NOT NULL,
                    CONSTRAINT {uq_name} UNIQUE (source, external_id)
                )
                """
            ).format(
                table_name=sql.Identifier(table_name),
                uq_name=sql.Identifier(f"{table_name}_source_external_id_key"),
            )
        )
        cursor.execute(
            sql.SQL("ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ").format(
                table_name=sql.Identifier(table_name)
            )
        )
        cursor.execute(
            sql.SQL("ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ").format(
                table_name=sql.Identifier(table_name)
            )
        )
        cursor.execute(
            sql.SQL("ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE").format(
                table_name=sql.Identifier(table_name)
            )
        )


def ensure_ingestion_runs_table(conn, *, table_name: str = "ingestion_runs") -> None:
    from psycopg import sql

    with conn.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                """
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id BIGSERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    started_at TIMESTAMPTZ NOT NULL,
                    finished_at TIMESTAMPTZ NOT NULL,
                    status TEXT NOT NULL,
                    fetched_count INTEGER NOT NULL DEFAULT 0,
                    persisted_count_raw INTEGER NOT NULL DEFAULT 0,
                    attempted_count_clean INTEGER NOT NULL DEFAULT 0,
                    persisted_count_clean INTEGER NOT NULL DEFAULT 0,
                    new_count INTEGER NOT NULL DEFAULT 0,
                    existing_count INTEGER NOT NULL DEFAULT 0,
                    missing_count INTEGER NOT NULL DEFAULT 0,
                    active_total INTEGER NOT NULL DEFAULT 0,
                    error TEXT
                )
                """
            ).format(table_name=sql.Identifier(table_name))
        )


def load_business_france_raw_into_clean_with_connection(
    conn,
    *,
    raw_table: str = "raw_offers",
    clean_table: str = "clean_offers",
) -> LoadResult:
    from psycopg import sql
    from psycopg.types.json import Json

    ensure_clean_offers_table(conn, table_name=clean_table)

    attempted = 0
    persisted = 0
    cleaned_at = _utc_now()

    select_sql = sql.SQL(
        """
        SELECT external_id, payload_json
        FROM {raw_table}
        WHERE source = %s
        ORDER BY scraped_at DESC
        """
    ).format(raw_table=sql.Identifier(raw_table))

    upsert_sql = sql.SQL(
        """
        INSERT INTO {clean_table} (
            source, external_id, title, company, location, country,
            contract_type, description, publication_date, start_date,
            salary, url, payload_json, cleaned_at
        )
        VALUES (
            %(source)s, %(external_id)s, %(title)s, %(company)s, %(location)s, %(country)s,
            %(contract_type)s, %(description)s, %(publication_date)s, %(start_date)s,
            %(salary)s, %(url)s, %(payload_json)s::jsonb, %(cleaned_at)s
        )
        ON CONFLICT (source, external_id)
        DO UPDATE SET
            title = EXCLUDED.title,
            company = EXCLUDED.company,
            location = EXCLUDED.location,
            country = EXCLUDED.country,
            contract_type = EXCLUDED.contract_type,
            description = EXCLUDED.description,
            publication_date = EXCLUDED.publication_date,
            start_date = EXCLUDED.start_date,
            salary = EXCLUDED.salary,
            url = EXCLUDED.url,
            payload_json = EXCLUDED.payload_json,
            cleaned_at = EXCLUDED.cleaned_at
        """
    ).format(clean_table=sql.Identifier(clean_table))

    with conn.cursor() as cursor:
        cursor.execute(select_sql, ("business_france",))
        rows = cursor.fetchall()
        for external_id, payload in rows:
            attempted += 1
            row = build_clean_offer_record(
                source="business_france",
                external_id=str(external_id),
                payload=payload if isinstance(payload, Mapping) else {},
                cleaned_at=cleaned_at,
            )
            row["payload_json"] = Json(row["payload_json"])
            cursor.execute(upsert_sql, row)
            persisted += 1

    conn.commit()
    return LoadResult(attempted=attempted, persisted=persisted)


def get_business_france_active_ids_with_connection(
    conn,
    *,
    clean_table: str = "clean_offers",
    source: str = "business_france",
) -> set[str]:
    from psycopg import sql

    ensure_clean_offers_table(conn, table_name=clean_table)
    with conn.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                """
                SELECT external_id
                FROM {clean_table}
                WHERE source = %s
                  AND COALESCE(is_active, TRUE) = TRUE
                """
            ).format(clean_table=sql.Identifier(clean_table)),
            (source,),
        )
        return {str(row[0]) for row in cursor.fetchall()}


def count_active_business_france_offers_with_connection(
    conn,
    *,
    clean_table: str = "clean_offers",
    source: str = "business_france",
) -> int:
    from psycopg import sql

    ensure_clean_offers_table(conn, table_name=clean_table)
    with conn.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                """
                SELECT COUNT(*)
                FROM {clean_table}
                WHERE source = %s
                  AND COALESCE(is_active, TRUE) = TRUE
                """
            ).format(clean_table=sql.Identifier(clean_table)),
            (source,),
        )
        row = cursor.fetchone()
        return int(row[0] if row else 0)


def get_latest_business_france_raw_ids_with_connection(
    conn,
    *,
    raw_table: str = "raw_offers",
    source: str = "business_france",
) -> set[str]:
    from psycopg import sql

    with conn.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                """
                SELECT MAX(scraped_at)
                FROM {raw_table}
                WHERE source = %s
                """
            ).format(raw_table=sql.Identifier(raw_table)),
            (source,),
        )
        row = cursor.fetchone()
        latest_scraped_at = row[0] if row else None
        if latest_scraped_at is None:
            return set()
        cursor.execute(
            sql.SQL(
                """
                SELECT external_id
                FROM {raw_table}
                WHERE source = %s
                  AND scraped_at = %s
                """
            ).format(raw_table=sql.Identifier(raw_table)),
            (source, latest_scraped_at),
        )
        return {str(found[0]) for found in cursor.fetchall()}


def sync_business_france_offer_presence_with_connection(
    conn,
    *,
    current_ids: set[str],
    previous_active_ids: set[str],
    clean_table: str = "clean_offers",
    source: str = "business_france",
    seen_at: str | None = None,
) -> dict[str, int]:
    from psycopg import sql

    ensure_clean_offers_table(conn, table_name=clean_table)
    seen_at_value = seen_at or _utc_now()
    normalized_current_ids = sorted({str(external_id).strip() for external_id in current_ids if str(external_id).strip()})
    normalized_previous_ids = {str(external_id).strip() for external_id in previous_active_ids if str(external_id).strip()}

    new_ids = set(normalized_current_ids) - normalized_previous_ids
    existing_ids = set(normalized_current_ids) & normalized_previous_ids
    missing_ids = normalized_previous_ids - set(normalized_current_ids)

    with conn.cursor() as cursor:
        if normalized_current_ids:
            cursor.execute(
                sql.SQL(
                    """
                    UPDATE {clean_table}
                    SET
                        is_active = TRUE,
                        last_seen_at = %s,
                        first_seen_at = COALESCE(first_seen_at, %s)
                    WHERE source = %s
                      AND external_id = ANY(%s)
                    """
                ).format(clean_table=sql.Identifier(clean_table)),
                (seen_at_value, seen_at_value, source, normalized_current_ids),
            )
        if missing_ids:
            cursor.execute(
                sql.SQL(
                    """
                    UPDATE {clean_table}
                    SET is_active = FALSE
                    WHERE source = %s
                      AND external_id = ANY(%s)
                    """
                ).format(clean_table=sql.Identifier(clean_table)),
                (source, sorted(missing_ids)),
            )

    conn.commit()
    return {
        "new_count": len(new_ids),
        "existing_count": len(existing_ids),
        "missing_count": len(missing_ids),
        "active_total": count_active_business_france_offers_with_connection(
            conn,
            clean_table=clean_table,
            source=source,
        ),
    }


def persist_ingestion_run_with_connection(
    conn,
    *,
    run_data: Mapping[str, Any],
    runs_table: str = "ingestion_runs",
) -> None:
    from psycopg import sql

    ensure_ingestion_runs_table(conn, table_name=runs_table)
    with conn.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                """
                INSERT INTO {runs_table} (
                    source,
                    started_at,
                    finished_at,
                    status,
                    fetched_count,
                    persisted_count_raw,
                    attempted_count_clean,
                    persisted_count_clean,
                    new_count,
                    existing_count,
                    missing_count,
                    active_total,
                    error
                )
                VALUES (
                    %(source)s,
                    %(started_at)s,
                    %(finished_at)s,
                    %(status)s,
                    %(fetched_count)s,
                    %(persisted_count_raw)s,
                    %(attempted_count_clean)s,
                    %(persisted_count_clean)s,
                    %(new_count)s,
                    %(existing_count)s,
                    %(missing_count)s,
                    %(active_total)s,
                    %(error)s
                )
                """
            ).format(runs_table=sql.Identifier(runs_table)),
            dict(run_data),
        )
    conn.commit()


def load_business_france_raw_into_clean(*, database_url: str | None = None) -> LoadResult:
    url = database_url or get_database_url()
    if not url:
        return LoadResult(attempted=0, persisted=0, error="DATABASE_URL is not set")

    conn = None
    try:
        conn = _connect(url)
        return load_business_france_raw_into_clean_with_connection(conn)
    except Exception as exc:
        return LoadResult(attempted=0, persisted=0, error=str(exc))
    finally:
        if conn is not None:
            conn.close()
