import os
import uuid

import pytest
from dotenv import dotenv_values


def _database_url() -> str | None:
    cfg = dotenv_values("apps/api/.env")
    return cfg.get("DATABASE_URL") or os.getenv("DATABASE_URL")


@pytest.mark.skipif(not _database_url(), reason="DATABASE_URL not configured")
def test_offer_skills_table_insert_and_idempotent_skip():
    import psycopg

    from api.utils.offer_skills_pg import (
        backfill_offer_skills_with_connection,
        ensure_offer_skills_table,
    )

    database_url = _database_url()
    assert database_url
    suffix = uuid.uuid4().hex[:8]
    clean_table = f"clean_offers_offer_skills_{suffix}"
    skills_table = f"offer_skills_{suffix}"

    def _builder(_offer):
        return {
            "offer_cluster": "DATA_ANALYTICS_AI",
            "canonical_skills": [
                {
                    "canonical_id": "skill:data_analysis",
                    "label": "Data Analysis",
                    "strategy": "synonym_match",
                    "confidence": 1.0,
                },
                {
                    "canonical_id": "skill:machine_learning",
                    "label": "Machine Learning",
                    "strategy": "synonym_match",
                    "confidence": 0.9,
                },
            ],
        }

    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE {clean_table} (
                    id BIGSERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    payload_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    cleaned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_{clean_table} UNIQUE (source, external_id)
                )
                """
            )
            cur.execute(
                f"""
                INSERT INTO {clean_table} (source, external_id, title, description)
                VALUES ('business_france', 'BF-SK-1', 'Data Analyst', 'Analyse de données et machine learning')
                """
            )
        ensure_offer_skills_table(conn, table_name=skills_table, clean_table=clean_table)
        conn.commit()

        first = backfill_offer_skills_with_connection(
            conn,
            clean_table=clean_table,
            offer_skills_table=skills_table,
            canonical_builder=_builder,
        )
        second = backfill_offer_skills_with_connection(
            conn,
            clean_table=clean_table,
            offer_skills_table=skills_table,
            canonical_builder=_builder,
        )

        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {skills_table}")
            assert cur.fetchone()[0] == 2
            cur.execute(
                f"""
                SELECT canonical_id, label, importance_level, source, confidence
                FROM {skills_table}
                ORDER BY canonical_id
                """
            )
            rows = cur.fetchall()
            assert rows == [
                ("skill:data_analysis", "Data Analysis", "CORE", "synonym_match", 1.0),
                ("skill:machine_learning", "Machine Learning", "CORE", "synonym_match", 0.9),
            ]
            cur.execute(f"DROP TABLE {skills_table}")
            cur.execute(f"DROP TABLE {clean_table}")
        conn.commit()

    assert first["offers_processed"] == 1
    assert first["rows_written"] == 2
    assert second["offers_processed"] == 0
    assert second["skipped_offers"] == 1


@pytest.mark.skipif(not _database_url(), reason="DATABASE_URL not configured")
def test_offer_skills_reprocesses_changed_content_without_duplicates():
    import psycopg

    from api.utils.offer_skills_pg import (
        backfill_offer_skills_with_connection,
        ensure_offer_skills_table,
    )

    database_url = _database_url()
    assert database_url
    suffix = uuid.uuid4().hex[:8]
    clean_table = f"clean_offers_offer_skills_{suffix}"
    skills_table = f"offer_skills_{suffix}"

    builders = [
        {
            "offer_cluster": "DATA_ANALYTICS_AI",
            "canonical_skills": [
                {
                    "canonical_id": "skill:data_analysis",
                    "label": "Data Analysis",
                    "strategy": "synonym_match",
                    "confidence": 1.0,
                }
            ],
        },
        {
            "offer_cluster": "DATA_ANALYTICS_AI",
            "canonical_skills": [
                {
                    "canonical_id": "skill:data_analysis",
                    "label": "Data Analysis",
                    "strategy": "synonym_match",
                    "confidence": 1.0,
                },
                {
                    "canonical_id": "skill:machine_learning",
                    "label": "Machine Learning",
                    "strategy": "synonym_match",
                    "confidence": 0.9,
                },
            ],
        },
    ]

    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE {clean_table} (
                    id BIGSERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    payload_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    cleaned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_{clean_table} UNIQUE (source, external_id)
                )
                """
            )
            cur.execute(
                f"""
                INSERT INTO {clean_table} (source, external_id, title, description)
                VALUES ('business_france', 'BF-SK-2', 'Data Analyst', 'Analyse de données')
                """
            )
        ensure_offer_skills_table(conn, table_name=skills_table, clean_table=clean_table)
        conn.commit()

        index = {"value": 0}

        def _builder(_offer):
            return builders[index["value"]]

        first = backfill_offer_skills_with_connection(
            conn,
            clean_table=clean_table,
            offer_skills_table=skills_table,
            canonical_builder=_builder,
        )

        with conn.cursor() as cur:
            cur.execute(f"UPDATE {clean_table} SET description = 'Analyse de données et machine learning' WHERE external_id = 'BF-SK-2'")
        conn.commit()
        index["value"] = 1

        second = backfill_offer_skills_with_connection(
            conn,
            clean_table=clean_table,
            offer_skills_table=skills_table,
            canonical_builder=_builder,
        )

        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {skills_table}")
            assert cur.fetchone()[0] == 2
            cur.execute(f"SELECT canonical_id FROM {skills_table} ORDER BY canonical_id")
            assert [row[0] for row in cur.fetchall()] == ["skill:data_analysis", "skill:machine_learning"]
            cur.execute(f"DROP TABLE {skills_table}")
            cur.execute(f"DROP TABLE {clean_table}")
        conn.commit()

    assert first["rows_written"] == 1
    assert second["offers_processed"] == 1
    assert second["rows_written"] == 2


@pytest.mark.skipif(not _database_url(), reason="DATABASE_URL not configured")
def test_offer_skills_ai_fallback_triggers_only_when_needed_and_persists_resolved_only():
    import psycopg

    from api.utils.offer_skills_pg import (
        backfill_offer_skills_with_connection,
        ensure_offer_skills_table,
    )

    database_url = _database_url()
    assert database_url
    suffix = uuid.uuid4().hex[:8]
    clean_table = f"clean_offers_offer_skills_{suffix}"
    skills_table = f"offer_skills_{suffix}"

    ai_calls: list[tuple[str, str]] = []

    def _builder(offer):
        skills = list(offer.get("skills") or [])
        if not skills:
            return {
                "offer_cluster": "MARKETING_SALES_GROWTH",
                "canonical_skills": [
                    {
                        "canonical_id": "skill:sales",
                        "label": "Sales",
                        "strategy": "synonym_match",
                        "confidence": 1.0,
                    },
                    {
                        "canonical_id": "skill:crm",
                        "label": "CRM",
                        "strategy": "synonym_match",
                        "confidence": 0.9,
                    },
                ],
            }
        if "sales prospecting" in skills or "lead generation" in skills:
            return {
                "offer_cluster": "MARKETING_SALES_GROWTH",
                "canonical_skills": [
                    {
                        "canonical_id": "skill:sales",
                        "label": "Sales",
                        "strategy": "synonym_match",
                        "confidence": 1.0,
                    },
                    {
                        "canonical_id": "skill:crm",
                        "label": "CRM",
                        "strategy": "synonym_match",
                        "confidence": 0.9,
                    },
                    {
                        "canonical_id": "skill:lead_generation",
                        "label": "Lead Generation",
                        "strategy": "synonym_match",
                        "confidence": 0.8,
                    },
                ],
            }
        return {
            "offer_cluster": "MARKETING_SALES_GROWTH",
            "canonical_skills": [],
        }

    def _ai_generator(*, title, description):
        ai_calls.append((title, description))
        return ["sales prospecting", "motivation", "sales prospecting"]

    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE {clean_table} (
                    id BIGSERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    payload_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    cleaned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_{clean_table} UNIQUE (source, external_id)
                )
                """
            )
            cur.execute(
                f"""
                INSERT INTO {clean_table} (source, external_id, title, description)
                VALUES ('business_france', 'BF-SK-AI-1', 'Sales Operations', 'Prospection commerciale et CRM')
                """
            )
        ensure_offer_skills_table(conn, table_name=skills_table, clean_table=clean_table)
        conn.commit()

        result = backfill_offer_skills_with_connection(
            conn,
            clean_table=clean_table,
            offer_skills_table=skills_table,
            enrichment_version="offer_skills_v2",
            canonical_builder=_builder,
            ai_skill_generator=_ai_generator,
        )

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT canonical_id, label, importance_level, source, confidence
                FROM {skills_table}
                ORDER BY canonical_id
                """
            )
            rows = cur.fetchall()
            assert rows == [
                ("skill:crm", "CRM", "CORE", "synonym_match", 0.9),
                ("skill:lead_generation", "Lead Generation", "SECONDARY", "ai_fallback", 0.6),
                ("skill:sales", "Sales", "SECONDARY", "synonym_match", 1.0),
            ]
            cur.execute(f"DROP TABLE {skills_table}")
            cur.execute(f"DROP TABLE {clean_table}")
        conn.commit()

    assert len(ai_calls) == 1
    assert result["rows_written"] == 3


@pytest.mark.skipif(not _database_url(), reason="DATABASE_URL not configured")
def test_offer_skills_ai_fallback_is_idempotent_and_unresolved_ai_skills_are_dropped():
    import psycopg

    from api.utils.offer_skills_pg import (
        backfill_offer_skills_with_connection,
        ensure_offer_skills_table,
    )

    database_url = _database_url()
    assert database_url
    suffix = uuid.uuid4().hex[:8]
    clean_table = f"clean_offers_offer_skills_{suffix}"
    skills_table = f"offer_skills_{suffix}"
    ai_calls = {"value": 0}

    def _builder(offer):
        skills = list(offer.get("skills") or [])
        if not skills:
            return {"offer_cluster": "GENERIC_TRANSVERSAL", "canonical_skills": []}
        return {"offer_cluster": "GENERIC_TRANSVERSAL", "canonical_skills": []}

    def _ai_generator(*, title, description):
        ai_calls["value"] += 1
        return ["motivation", "team spirit"]

    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE {clean_table} (
                    id BIGSERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    payload_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    cleaned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_{clean_table} UNIQUE (source, external_id)
                )
                """
            )
            cur.execute(
                f"""
                INSERT INTO {clean_table} (source, external_id, title, description)
                VALUES ('business_france', 'BF-SK-AI-2', 'Assistant', 'Support administratif')
                """
            )
        ensure_offer_skills_table(conn, table_name=skills_table, clean_table=clean_table)
        conn.commit()

        first = backfill_offer_skills_with_connection(
            conn,
            clean_table=clean_table,
            offer_skills_table=skills_table,
            enrichment_version="offer_skills_v2",
            canonical_builder=_builder,
            ai_skill_generator=_ai_generator,
        )
        second = backfill_offer_skills_with_connection(
            conn,
            clean_table=clean_table,
            offer_skills_table=skills_table,
            enrichment_version="offer_skills_v2",
            canonical_builder=_builder,
            ai_skill_generator=_ai_generator,
        )

        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {skills_table}")
            assert cur.fetchone()[0] == 0
            cur.execute(f"DROP TABLE {skills_table}")
            cur.execute(f"DROP TABLE {clean_table}")
        conn.commit()

    assert first["offers_processed"] == 1
    assert first["rows_written"] == 0
    assert second["offers_processed"] == 1
    assert second["rows_written"] == 0
    assert ai_calls["value"] == 2


@pytest.mark.skipif(not _database_url(), reason="DATABASE_URL not configured")
def test_offer_skills_ai_fallback_batches_multiple_offers_in_single_call():
    import psycopg

    from api.utils.offer_skills_pg import (
        backfill_offer_skills_with_connection,
        ensure_offer_skills_table,
    )

    database_url = _database_url()
    assert database_url
    suffix = uuid.uuid4().hex[:8]
    clean_table = f"clean_offers_offer_skills_{suffix}"
    skills_table = f"offer_skills_{suffix}"

    batch_calls: list[list[str]] = []

    canonical_by_label = {
        "sales prospecting": {"canonical_id": "skill:sales", "label": "Sales"},
        "lead generation": {"canonical_id": "skill:lead_generation", "label": "Lead Generation"},
        "crm management": {"canonical_id": "skill:crm", "label": "CRM"},
        "recruitment": {"canonical_id": "skill:recruitment", "label": "Recruitment"},
        "onboarding": {"canonical_id": "skill:onboarding", "label": "Onboarding"},
        "data analysis": {"canonical_id": "skill:data_analysis", "label": "Data Analysis"},
        "business intelligence": {"canonical_id": "skill:bi", "label": "Business Intelligence"},
        "python": {"canonical_id": "skill:python", "label": "Python"},
        "sql": {"canonical_id": "skill:sql", "label": "SQL"},
    }

    def _builder(offer):
        skills = [str(s).strip().lower() for s in (offer.get("skills") or [])]
        resolved: list[dict] = []
        seen: set[str] = set()
        for s in skills:
            entry = canonical_by_label.get(s)
            if not entry:
                continue
            if entry["canonical_id"] in seen:
                continue
            seen.add(entry["canonical_id"])
            resolved.append(
                {
                    "canonical_id": entry["canonical_id"],
                    "label": entry["label"],
                    "strategy": "ai_fallback",
                    "confidence": 0.6,
                }
            )
        return {"offer_cluster": "MARKETING_SALES_GROWTH", "canonical_skills": resolved}

    # Offer 1: 3 resolvable labels. Offer 2: 2 resolvable + 2 generic (blocklisted)
    # + 1 unresolved. Offer 3: 7 labels (to verify 5-cap).
    ai_responses = {
        "offer-1": ["sales prospecting", "crm management", "recruitment"],
        "offer-2": ["recruitment", "motivation", "team spirit", "onboarding", "made up skill xyz"],
        "offer-3": [
            "data analysis",
            "business intelligence",
            "python",
            "sql",
            "recruitment",
            "onboarding",
            "crm management",
        ],
    }

    def _batch_generator(items):
        batch_calls.append([str(item.get("offer_id")) for item in items])
        return {str(item.get("offer_id")): ai_responses.get(str(item.get("offer_id")), []) for item in items}

    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE {clean_table} (
                    id BIGSERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    payload_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    cleaned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_{clean_table} UNIQUE (source, external_id)
                )
                """
            )
            # Insert 3 offers with forced IDs so offer_id keys are deterministic.
            cur.execute(
                f"""
                INSERT INTO {clean_table} (id, source, external_id, title, description)
                VALUES
                    (1, 'business_france', 'BF-BATCH-1', 'SDR', 'Prospection B2B'),
                    (2, 'business_france', 'BF-BATCH-2', 'HR Officer', 'Recrutement et intégration'),
                    (3, 'business_france', 'BF-BATCH-3', 'Analyst', 'Analyse BI et Python')
                """
            )
            # Rename keys so they match our mocked AI response dict (stringified offer_id).
        ensure_offer_skills_table(conn, table_name=skills_table, clean_table=clean_table)
        conn.commit()

        # Translate the real offer_ids (1,2,3) to our response keys.
        ai_responses_real = {
            "1": ai_responses["offer-1"],
            "2": ai_responses["offer-2"],
            "3": ai_responses["offer-3"],
        }

        def _batch_generator_real(items):
            batch_calls.append([str(item.get("offer_id")) for item in items])
            return {str(item.get("offer_id")): ai_responses_real.get(str(item.get("offer_id")), []) for item in items}

        first = backfill_offer_skills_with_connection(
            conn,
            clean_table=clean_table,
            offer_skills_table=skills_table,
            enrichment_version="offer_skills_v2",
            canonical_builder=_builder,
            ai_batch_generator=_batch_generator_real,
            fallback_batch_size=15,
        )

        # Re-run: everything should be idempotent (same content_hash + version).
        second = backfill_offer_skills_with_connection(
            conn,
            clean_table=clean_table,
            offer_skills_table=skills_table,
            enrichment_version="offer_skills_v2",
            canonical_builder=_builder,
            ai_batch_generator=_batch_generator_real,
            fallback_batch_size=15,
        )

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT offer_id, canonical_id, importance_level, source, confidence
                FROM {skills_table}
                ORDER BY offer_id, canonical_id
                """
            )
            rows = cur.fetchall()
            by_offer: dict[int, list[tuple]] = {}
            for row in rows:
                by_offer.setdefault(row[0], []).append(row[1:])

            # Offer 1: 3 rows, all ai_fallback SECONDARY, confidence 0.6
            assert len(by_offer[1]) == 3
            for row in by_offer[1]:
                assert row[1] == "SECONDARY"
                assert row[2] == "ai_fallback"
                assert row[3] == 0.6
            # "sales prospecting" → "lead generation" (prospecting rule),
            # "crm management" → "crm management", "recruitment" → "recruitment"
            assert {r[0] for r in by_offer[1]} == {
                "skill:lead_generation",
                "skill:crm",
                "skill:recruitment",
            }

            # Offer 2: only 2 rows persist (recruitment + onboarding). Blocklisted
            # labels and unresolved "made up skill xyz" are discarded.
            assert {r[0] for r in by_offer[2]} == {"skill:recruitment", "skill:onboarding"}

            # Offer 3: max 5 cap — 7 labels provided, only 5 should reach the
            # builder and persist.
            assert len(by_offer[3]) == 5
            for row in by_offer[3]:
                assert row[1] == "SECONDARY"
                assert row[2] == "ai_fallback"

            cur.execute(f"DROP TABLE {skills_table}")
            cur.execute(f"DROP TABLE {clean_table}")
        conn.commit()

    # Exactly one batch call for 3 offers
    assert len(batch_calls) == 1
    assert sorted(batch_calls[0]) == ["1", "2", "3"]

    assert first["ai_triggered_offers"] == 3
    assert first["ai_batches_sent"] == 1
    assert first["fixed_offers"] == 3
    assert first["rows_written"] == 3 + 2 + 5  # 10

    # Second run: nothing needs reprocessing
    assert second["offers_processed"] == 0
    assert second["skipped_offers"] == 3
    assert second["ai_batches_sent"] == 0
    assert second["rows_written"] == 0


@pytest.mark.skipif(not _database_url(), reason="DATABASE_URL not configured")
def test_offer_skills_ai_fallback_batch_chunks_by_batch_size():
    import psycopg

    from api.utils.offer_skills_pg import (
        backfill_offer_skills_with_connection,
        ensure_offer_skills_table,
    )

    database_url = _database_url()
    assert database_url
    suffix = uuid.uuid4().hex[:8]
    clean_table = f"clean_offers_offer_skills_{suffix}"
    skills_table = f"offer_skills_{suffix}"

    batch_sizes: list[int] = []

    def _builder(offer):
        return {"offer_cluster": "GENERIC_TRANSVERSAL", "canonical_skills": []}

    def _batch_generator(items):
        batch_sizes.append(len(items))
        # Empty responses — still counts as a batch sent; no rows persisted.
        return {}

    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE {clean_table} (
                    id BIGSERIAL PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    payload_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                    cleaned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_{clean_table} UNIQUE (source, external_id)
                )
                """
            )
            values = ",".join(
                f"('business_france', 'BF-CHUNK-{i}', 'T{i}', 'D{i}')" for i in range(7)
            )
            cur.execute(
                f"INSERT INTO {clean_table} (source, external_id, title, description) VALUES {values}"
            )
        ensure_offer_skills_table(conn, table_name=skills_table, clean_table=clean_table)
        conn.commit()

        result = backfill_offer_skills_with_connection(
            conn,
            clean_table=clean_table,
            offer_skills_table=skills_table,
            enrichment_version="offer_skills_v2",
            canonical_builder=_builder,
            ai_batch_generator=_batch_generator,
            fallback_batch_size=3,
        )

        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE {skills_table}")
            cur.execute(f"DROP TABLE {clean_table}")
        conn.commit()

    # 7 offers, batch size 3 → 3 + 3 + 1
    assert batch_sizes == [3, 3, 1]
    assert result["ai_triggered_offers"] == 7
    assert result["ai_batches_sent"] == 3
    assert result["rows_written"] == 0
    assert result["fixed_offers"] == 0
