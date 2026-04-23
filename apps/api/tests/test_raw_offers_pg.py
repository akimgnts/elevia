import os
import uuid

import pytest
from dotenv import dotenv_values


def _database_url() -> str | None:
    cfg = dotenv_values("apps/api/.env")
    return cfg.get("DATABASE_URL") or os.getenv("DATABASE_URL")


@pytest.mark.skipif(not _database_url(), reason="DATABASE_URL not configured")
def test_persist_raw_offers_with_connection_upgrades_legacy_table_schema():
    import psycopg

    from api.utils.raw_offers_pg import persist_raw_offers_with_connection

    database_url = _database_url()
    assert database_url

    table_name = f"raw_offers_legacy_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE {table_name} (
                    id BIGSERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    payload_json JSONB,
                    scraped_at TIMESTAMP,
                    CONSTRAINT uq_{table_name} UNIQUE (source, external_id)
                )
                """
            )
        conn.commit()

        result = persist_raw_offers_with_connection(
            conn,
            "business_france",
            [{"id": 242600, "missionTitle": "Offer X"}],
            "2026-04-23T12:00:00+00:00",
            table_name=table_name,
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY column_name
                """,
                (table_name,),
            )
            columns = {row[0] for row in cur.fetchall()}
            cur.execute(f"SELECT source, external_id FROM {table_name}")
            row = cur.fetchone()
            cur.execute(f"DROP TABLE {table_name}")
        conn.commit()

    assert result.attempted == 1
    assert result.persisted == 1
    assert {"created_at", "updated_at"}.issubset(columns)
    assert row == ("business_france", "242600")
