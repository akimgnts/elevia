import os
import uuid

import pytest
from dotenv import dotenv_values


def _database_url() -> str | None:
    cfg = dotenv_values("apps/api/.env")
    return cfg.get("DATABASE_URL") or os.getenv("DATABASE_URL")


@pytest.mark.skipif(not _database_url(), reason="DATABASE_URL not configured")
def test_build_clean_offer_record_maps_minimal_business_france_fields():
    from api.utils.clean_offers_pg import build_clean_offer_record

    payload = {
        "title": " Development Technician VIE (HR) (H/F) ",
        "company": "HUTCHINSON",
        "city": "HERNDON      -VA-",
        "country": "ESPAGNE",
        "missionType": "VIE",
        "description": "desc",
        "publicationDate": "2026-04-16T15:24:04Z",
        "startDate": "2026-09-01T00:00:00",
        "offerUrl": "https://mon-vie-via.businessfrance.fr/offres/242362",
        "is_vie": True,
    }

    row = build_clean_offer_record(
        source="business_france",
        external_id="BF-242362",
        payload=payload,
        cleaned_at="2026-04-23T00:00:00+00:00",
    )

    assert row["source"] == "business_france"
    assert row["external_id"] == "BF-242362"
    assert row["title"] == "Development Technician VIE (HR) (H/F)"
    assert row["company"] == "HUTCHINSON"
    assert row["location"] == "HERNDON -VA-"
    assert row["country"] == "ESPAGNE"
    assert row["contract_type"] == "VIE"
    assert row["description"] == "desc"
    assert row["publication_date"] == "2026-04-16T15:24:04Z"
    assert row["start_date"] == "2026-09-01"
    assert row["url"] == "https://mon-vie-via.businessfrance.fr/offres/242362"
    assert row["payload_json"]["is_vie"] is True
    assert row["cleaned_at"] == "2026-04-23T00:00:00+00:00"


@pytest.mark.skipif(not _database_url(), reason="DATABASE_URL not configured")
def test_load_business_france_raw_into_clean_is_idempotent_and_updates_rows():
    import psycopg

    from api.utils.clean_offers_pg import load_business_france_raw_into_clean_with_connection

    database_url = _database_url()
    assert database_url
    suffix = uuid.uuid4().hex[:8]
    raw_table = f"raw_offers_test_{suffix}"
    clean_table = f"clean_offers_test_{suffix}"

    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE {raw_table} (
                    id BIGSERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    payload_json JSONB NOT NULL,
                    scraped_at TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_{raw_table} UNIQUE (source, external_id)
                )
                """
            )
            cur.execute(
                f"""
                CREATE TABLE {clean_table} (
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
                    CONSTRAINT uq_{clean_table} UNIQUE (source, external_id)
                )
                """
            )
            cur.execute(
                f"""
                INSERT INTO {raw_table} (source, external_id, payload_json, scraped_at)
                VALUES (
                    'business_france',
                    'BF-1',
                    %s::jsonb,
                    '2026-04-23T10:00:00Z'
                )
                """,
                [
                    """
                    {
                      "title": "Offer One",
                      "company": "AIRBUS",
                      "city": "MADRID",
                      "country": "ESPAGNE",
                      "missionType": "VIE",
                      "description": "desc v1",
                      "publicationDate": "2026-04-16T15:24:04Z",
                      "startDate": "2026-09-01T00:00:00",
                      "offerUrl": "https://example.com/1",
                      "is_vie": true
                    }
                    """
                ],
            )
        conn.commit()

        first = load_business_france_raw_into_clean_with_connection(
            conn,
            raw_table=raw_table,
            clean_table=clean_table,
        )
        second = load_business_france_raw_into_clean_with_connection(
            conn,
            raw_table=raw_table,
            clean_table=clean_table,
        )

        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {clean_table}")
            assert cur.fetchone()[0] == 1
            cur.execute(f"SELECT title, company, location, contract_type, url, payload_json->>'is_vie' FROM {clean_table}")
            title, company, location, contract_type, url, is_vie = cur.fetchone()
            assert (title, company, location, contract_type, url, is_vie) == (
                "Offer One",
                "AIRBUS",
                "MADRID",
                "VIE",
                "https://example.com/1",
                "true",
            )

            cur.execute(
                f"""
                UPDATE {raw_table}
                SET payload_json = %s::jsonb,
                    scraped_at = '2026-04-23T11:00:00Z'
                WHERE source = 'business_france' AND external_id = 'BF-1'
                """,
                [
                    """
                    {
                      "title": "Offer One Updated",
                      "company": "AIRBUS",
                      "city": "MADRID",
                      "country": "ESPAGNE",
                      "missionType": "VIE",
                      "description": "desc v2",
                      "publicationDate": "2026-04-16T15:24:04Z",
                      "startDate": "2026-09-01T00:00:00",
                      "offerUrl": "https://example.com/1b",
                      "is_vie": true
                    }
                    """
                ],
            )
        conn.commit()

        third = load_business_france_raw_into_clean_with_connection(
            conn,
            raw_table=raw_table,
            clean_table=clean_table,
        )

        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {clean_table}")
            assert cur.fetchone()[0] == 1
            cur.execute(f"SELECT title, description, url FROM {clean_table}")
            assert cur.fetchone() == ("Offer One Updated", "desc v2", "https://example.com/1b")

            cur.execute(f"DROP TABLE {clean_table}")
            cur.execute(f"DROP TABLE {raw_table}")
        conn.commit()

    assert first.attempted == 1
    assert first.persisted == 1
    assert second.attempted == 1
    assert second.persisted == 1
    assert third.attempted == 1
    assert third.persisted == 1
