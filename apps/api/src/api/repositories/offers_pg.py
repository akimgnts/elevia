from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any


def get_database_url() -> str | None:
    value = os.getenv("DATABASE_URL", "").strip()
    return value or None


def _connect():
    import psycopg
    from psycopg.rows import dict_row

    database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(database_url, row_factory=dict_row)


class OffersPgRepository:
    def __init__(self, connection_factory: Callable[[], Any] | None = None):
        self._connection_factory = connection_factory or _connect

    def _run_fetchall(self, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        conn = self._connection_factory()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return list(cursor.fetchall())
        finally:
            close = getattr(conn, "close", None)
            if callable(close):
                close()

    def _run_fetchone(self, query: str, params: tuple[Any, ...]) -> Any | None:
        conn = self._connection_factory()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchone()
        finally:
            close = getattr(conn, "close", None)
            if callable(close):
                close()

    def fetch_recent_offers(
        self,
        limit: int,
        country: str | None = None,
        source: str = "business_france",
    ) -> list[dict[str, Any]]:
        query = """
            SELECT
                id,
                source,
                external_id,
                title,
                company,
                location,
                country,
                contract_type,
                publication_date,
                start_date,
                url,
                last_seen_at
            FROM clean_offers
            WHERE source = %s
              AND is_active = TRUE
        """
        params: list[Any] = [source]
        if country:
            query += "\n              AND country = %s"
            params.append(country)
        query += """
            ORDER BY last_seen_at DESC, publication_date DESC, id DESC
            LIMIT %s
        """
        params.append(limit)

        return self._run_fetchall(query, tuple(params))

    def fetch_offer_detail(self, offer_id: int) -> dict[str, Any] | None:
        query = """
            SELECT
                co.id,
                co.source,
                co.external_id,
                co.title,
                co.company,
                co.location,
                co.country,
                co.contract_type,
                co.description,
                co.publication_date,
                co.start_date,
                co.salary,
                co.url,
                co.payload_json,
                co.first_seen_at,
                co.last_seen_at,
                co.is_active,
                ode.domain_tag,
                ode.confidence,
                ode.method,
                COALESCE(ode.evidence, '[]'::jsonb) AS evidence,
                ode.needs_ai_review,
                ode.job_family,
                ode.primary_function,
                ode.purity_score,
                ode.hybrid_score
            FROM clean_offers AS co
            LEFT JOIN offer_domain_enrichment AS ode
              ON ode.source = co.source
             AND ode.external_id = co.external_id
            WHERE co.id = %s
        """
        return self._run_fetchone(query, (offer_id,))

    def fetch_latest_ingestion(
        self,
        source: str = "business_france",
    ) -> dict[str, Any] | None:
        query = """
            SELECT
                id,
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
            FROM ingestion_runs
            WHERE source = %s
            ORDER BY started_at DESC
            LIMIT 1
        """
        return self._run_fetchone(query, (source,))

    def fetch_latest_ingestion_timestamp(
        self,
        source: str = "business_france",
    ) -> Any | None:
        query = """
            SELECT started_at
            FROM ingestion_runs
            WHERE source = %s
            ORDER BY started_at DESC
            LIMIT 1
        """
        row = self._run_fetchone(query, (source,))
        if row is None:
            return None
        if isinstance(row, dict):
            return row.get("started_at")
        return row[0]
