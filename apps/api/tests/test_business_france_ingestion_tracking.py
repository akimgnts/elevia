import os
import uuid

import pytest
from dotenv import dotenv_values


def _database_url() -> str | None:
    cfg = dotenv_values("apps/api/.env")
    return cfg.get("DATABASE_URL") or os.getenv("DATABASE_URL")


@pytest.mark.skipif(not _database_url(), reason="DATABASE_URL not configured")
def test_business_france_tracking_first_second_and_missing_runs():
    import psycopg

    from api.utils.clean_offers_pg import (
        count_active_business_france_offers_with_connection,
        get_business_france_active_ids_with_connection,
        get_latest_business_france_raw_ids_with_connection,
        load_business_france_raw_into_clean_with_connection,
        persist_ingestion_run_with_connection,
        sync_business_france_offer_presence_with_connection,
    )
    from api.utils.raw_offers_pg import persist_raw_offer_records_with_connection

    database_url = _database_url()
    assert database_url
    suffix = uuid.uuid4().hex[:8]
    raw_table = f"raw_offers_track_{suffix}"
    clean_table = f"clean_offers_track_{suffix}"
    runs_table = f"ingestion_runs_track_{suffix}"

    def _payload(external_id: str, title: str) -> dict:
        return {
            "id": external_id,
            "title": title,
            "company": "BF",
            "city": "Madrid",
            "country": "Espagne",
            "missionType": "VIE",
            "description": f"desc {title}",
            "publicationDate": "2026-04-23T10:00:00Z",
            "startDate": "2026-09-01T00:00:00",
            "offerUrl": f"https://example.com/{external_id}",
            "is_vie": True,
        }

    with psycopg.connect(database_url, connect_timeout=5) as conn:
        # Run 1: all offers are new.
        persist_raw_offer_records_with_connection(
            conn,
            "business_france",
            [
                {"external_id": "BF-1", "scraped_at": "2026-04-23T10:00:00Z", "payload": _payload("BF-1", "Offer 1")},
                {"external_id": "BF-2", "scraped_at": "2026-04-23T10:00:00Z", "payload": _payload("BF-2", "Offer 2")},
                {"external_id": "BF-3", "scraped_at": "2026-04-23T10:00:00Z", "payload": _payload("BF-3", "Offer 3")},
            ],
            table_name=raw_table,
        )
        previous_ids = get_business_france_active_ids_with_connection(conn, clean_table=clean_table)
        assert previous_ids == set()
        current_ids = get_latest_business_france_raw_ids_with_connection(conn, raw_table=raw_table)
        assert current_ids == {"BF-1", "BF-2", "BF-3"}
        first_load = load_business_france_raw_into_clean_with_connection(
            conn,
            raw_table=raw_table,
            clean_table=clean_table,
        )
        first_stats = sync_business_france_offer_presence_with_connection(
            conn,
            current_ids=current_ids,
            previous_active_ids=previous_ids,
            clean_table=clean_table,
            source="business_france",
            seen_at="2026-04-23T10:05:00Z",
        )
        persist_ingestion_run_with_connection(
            conn,
            runs_table=runs_table,
            run_data={
                "source": "business_france",
                "started_at": "2026-04-23T10:00:00Z",
                "finished_at": "2026-04-23T10:06:00Z",
                "status": "success",
                "fetched_count": 3,
                "persisted_count_raw": 3,
                "attempted_count_clean": first_load.attempted,
                "persisted_count_clean": first_load.persisted,
                "new_count": first_stats["new_count"],
                "existing_count": first_stats["existing_count"],
                "missing_count": first_stats["missing_count"],
                "active_total": first_stats["active_total"],
                "error": None,
            },
        )
        assert first_stats == {
            "new_count": 3,
            "existing_count": 0,
            "missing_count": 0,
            "active_total": 3,
        }
        assert count_active_business_france_offers_with_connection(conn, clean_table=clean_table) == 3

        # Run 2: identical set, all existing.
        persist_raw_offer_records_with_connection(
            conn,
            "business_france",
            [
                {"external_id": "BF-1", "scraped_at": "2026-04-23T18:00:00Z", "payload": _payload("BF-1", "Offer 1")},
                {"external_id": "BF-2", "scraped_at": "2026-04-23T18:00:00Z", "payload": _payload("BF-2", "Offer 2")},
                {"external_id": "BF-3", "scraped_at": "2026-04-23T18:00:00Z", "payload": _payload("BF-3", "Offer 3")},
            ],
            table_name=raw_table,
        )
        previous_ids = get_business_france_active_ids_with_connection(conn, clean_table=clean_table)
        current_ids = get_latest_business_france_raw_ids_with_connection(conn, raw_table=raw_table)
        second_load = load_business_france_raw_into_clean_with_connection(
            conn,
            raw_table=raw_table,
            clean_table=clean_table,
        )
        second_stats = sync_business_france_offer_presence_with_connection(
            conn,
            current_ids=current_ids,
            previous_active_ids=previous_ids,
            clean_table=clean_table,
            source="business_france",
            seen_at="2026-04-23T18:05:00Z",
        )
        persist_ingestion_run_with_connection(
            conn,
            runs_table=runs_table,
            run_data={
                "source": "business_france",
                "started_at": "2026-04-23T18:00:00Z",
                "finished_at": "2026-04-23T18:06:00Z",
                "status": "success",
                "fetched_count": 3,
                "persisted_count_raw": 3,
                "attempted_count_clean": second_load.attempted,
                "persisted_count_clean": second_load.persisted,
                "new_count": second_stats["new_count"],
                "existing_count": second_stats["existing_count"],
                "missing_count": second_stats["missing_count"],
                "active_total": second_stats["active_total"],
                "error": None,
            },
        )
        assert second_stats == {
            "new_count": 0,
            "existing_count": 3,
            "missing_count": 0,
            "active_total": 3,
        }

        # Run 3: one ID disappears, it must become inactive.
        persist_raw_offer_records_with_connection(
            conn,
            "business_france",
            [
                {"external_id": "BF-1", "scraped_at": "2026-04-24T10:00:00Z", "payload": _payload("BF-1", "Offer 1")},
                {"external_id": "BF-3", "scraped_at": "2026-04-24T10:00:00Z", "payload": _payload("BF-3", "Offer 3")},
            ],
            table_name=raw_table,
        )
        previous_ids = get_business_france_active_ids_with_connection(conn, clean_table=clean_table)
        current_ids = get_latest_business_france_raw_ids_with_connection(conn, raw_table=raw_table)
        third_load = load_business_france_raw_into_clean_with_connection(
            conn,
            raw_table=raw_table,
            clean_table=clean_table,
        )
        third_stats = sync_business_france_offer_presence_with_connection(
            conn,
            current_ids=current_ids,
            previous_active_ids=previous_ids,
            clean_table=clean_table,
            source="business_france",
            seen_at="2026-04-24T10:05:00Z",
        )
        persist_ingestion_run_with_connection(
            conn,
            runs_table=runs_table,
            run_data={
                "source": "business_france",
                "started_at": "2026-04-24T10:00:00Z",
                "finished_at": "2026-04-24T10:06:00Z",
                "status": "success",
                "fetched_count": 2,
                "persisted_count_raw": 2,
                "attempted_count_clean": third_load.attempted,
                "persisted_count_clean": third_load.persisted,
                "new_count": third_stats["new_count"],
                "existing_count": third_stats["existing_count"],
                "missing_count": third_stats["missing_count"],
                "active_total": third_stats["active_total"],
                "error": None,
            },
        )
        assert third_stats == {
            "new_count": 0,
            "existing_count": 2,
            "missing_count": 1,
            "active_total": 2,
        }

        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {clean_table}")
            assert cur.fetchone()[0] == 3
            cur.execute(
                f"SELECT external_id, is_active FROM {clean_table} WHERE source='business_france' ORDER BY external_id"
            )
            assert cur.fetchall() == [("BF-1", True), ("BF-2", False), ("BF-3", True)]
            cur.execute(f"SELECT COUNT(*) FROM {runs_table}")
            assert cur.fetchone()[0] == 3
            cur.execute(
                f"""
                SELECT new_count, existing_count, missing_count, active_total
                FROM {runs_table}
                ORDER BY started_at
                """
            )
            assert cur.fetchall() == [
                (3, 0, 0, 3),
                (0, 3, 0, 3),
                (0, 2, 1, 2),
            ]

            cur.execute(f"DROP TABLE {runs_table}")
            cur.execute(f"DROP TABLE {clean_table}")
            cur.execute(f"DROP TABLE {raw_table}")
        conn.commit()
