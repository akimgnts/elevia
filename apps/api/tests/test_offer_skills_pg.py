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
                SELECT canonical_id, label, importance_level, source_method, confidence,
                       source, external_id
                FROM {skills_table}
                ORDER BY canonical_id
                """
            )
            rows = cur.fetchall()
            assert rows == [
                ("skill:data_analysis", "Data Analysis", "CORE", "synonym_match", 1.0,
                 "business_france", "BF-SK-1"),
                ("skill:machine_learning", "Machine Learning", "CORE", "synonym_match", 0.9,
                 "business_france", "BF-SK-1"),
            ]
            # Identity consistency: offer_skills natural key matches clean_offers.
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {skills_table} os
                JOIN {clean_table} co ON co.id = os.offer_id
                WHERE os.source <> co.source OR os.external_id <> co.external_id
                """
            )
            assert cur.fetchone()[0] == 0
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
                SELECT canonical_id, label, importance_level, source_method, confidence,
                       source, external_id
                FROM {skills_table}
                ORDER BY canonical_id
                """
            )
            rows = cur.fetchall()
            assert rows == [
                ("skill:crm", "CRM", "CORE", "synonym_match", 0.9,
                 "business_france", "BF-SK-AI-1"),
                ("skill:lead_generation", "Lead Generation", "SECONDARY", "ai_fallback", 0.6,
                 "business_france", "BF-SK-AI-1"),
                ("skill:sales", "Sales", "SECONDARY", "synonym_match", 1.0,
                 "business_france", "BF-SK-AI-1"),
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
                SELECT offer_id, canonical_id, importance_level, source_method, confidence,
                       source, external_id
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
                assert row[4] == "business_france"
                assert row[5] == "BF-BATCH-1"
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
            for row in by_offer[2]:
                assert row[4] == "business_france"
                assert row[5] == "BF-BATCH-2"

            # Offer 3: max 5 cap — 7 labels provided, only 5 should reach the
            # builder and persist.
            assert len(by_offer[3]) == 5
            for row in by_offer[3]:
                assert row[1] == "SECONDARY"
                assert row[2] == "ai_fallback"
                assert row[4] == "business_france"
                assert row[5] == "BF-BATCH-3"

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


@pytest.mark.skipif(not _database_url(), reason="DATABASE_URL not configured")
def test_ensure_offer_skills_table_migrates_legacy_rows_to_natural_key():
    """Legacy offer_skills table (no source/external_id) is migrated idempotently.

    Simulates the pre-patch schema and verifies that ensure_offer_skills_table
    renames the old `source` column to `source_method`, adds `source` and
    `external_id`, backfills them from clean_offers, and enforces NOT NULL.
    """

    import psycopg

    from api.utils.offer_skills_pg import ensure_offer_skills_table

    database_url = _database_url()
    assert database_url
    suffix = uuid.uuid4().hex[:8]
    clean_table = f"clean_offers_offer_skills_{suffix}"
    skills_table = f"offer_skills_{suffix}"

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
                    CONSTRAINT uq_{clean_table} UNIQUE (source, external_id)
                )
                """
            )
            cur.execute(
                f"""
                INSERT INTO {clean_table} (source, external_id, title, description)
                VALUES
                    ('business_france', 'BF-LEGACY-1', 'Data Analyst', 'desc1'),
                    ('business_france', 'BF-LEGACY-2', 'Sales Manager', 'desc2')
                RETURNING id
                """
            )
            ids = [r[0] for r in cur.fetchall()]
            # Legacy schema: `source` column stores enrichment method, no
            # external_id column at all.
            cur.execute(
                f"""
                CREATE TABLE {skills_table} (
                    id BIGSERIAL PRIMARY KEY,
                    offer_id BIGINT NOT NULL REFERENCES {clean_table}(id) ON DELETE CASCADE,
                    canonical_id TEXT NOT NULL,
                    label TEXT NOT NULL,
                    importance_level TEXT NOT NULL CHECK (importance_level IN ('CORE', 'SECONDARY')),
                    source TEXT NOT NULL,
                    confidence DOUBLE PRECISION,
                    enrichment_version TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    CONSTRAINT uq_{skills_table} UNIQUE (offer_id, canonical_id)
                )
                """
            )
            cur.execute(
                f"""
                INSERT INTO {skills_table}
                    (offer_id, canonical_id, label, importance_level, source, confidence,
                     enrichment_version, content_hash, created_at)
                VALUES
                    (%s, 'skill:sql', 'SQL', 'CORE', 'synonym_match', 1.0, 'offer_skills_v1', 'hash1', NOW()),
                    (%s, 'skill:python', 'Python', 'CORE', 'tool_match', 0.9, 'offer_skills_v1', 'hash1', NOW()),
                    (%s, 'skill:sales', 'Sales', 'CORE', 'synonym_match', 1.0, 'offer_skills_v1', 'hash2', NOW())
                """,
                (ids[0], ids[0], ids[1]),
            )
        conn.commit()

        ensure_offer_skills_table(conn, table_name=skills_table, clean_table=clean_table)
        conn.commit()

        with conn.cursor() as cur:
            # New columns exist and are NOT NULL
            cur.execute(
                """
                SELECT column_name, is_nullable FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s
                  AND column_name IN ('source', 'external_id', 'source_method')
                ORDER BY column_name
                """,
                (skills_table,),
            )
            cols = {r[0]: r[1] for r in cur.fetchall()}
            assert cols == {"external_id": "NO", "source": "NO", "source_method": "NO"}

            # Backfill: natural key matches the parent clean_offers row
            cur.execute(
                f"""
                SELECT canonical_id, source, external_id, source_method
                FROM {skills_table}
                ORDER BY canonical_id
                """
            )
            rows = cur.fetchall()
            assert rows == [
                ("skill:python", "business_france", "BF-LEGACY-1", "tool_match"),
                ("skill:sales", "business_france", "BF-LEGACY-2", "synonym_match"),
                ("skill:sql", "business_france", "BF-LEGACY-1", "synonym_match"),
            ]

            # Identity invariant across the join
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {skills_table} os
                JOIN {clean_table} co ON co.id = os.offer_id
                WHERE os.source <> co.source OR os.external_id <> co.external_id
                """
            )
            assert cur.fetchone()[0] == 0

            # Idempotency: second call is a no-op
            ensure_offer_skills_table(conn, table_name=skills_table, clean_table=clean_table)
            cur.execute(f"SELECT COUNT(*) FROM {skills_table}")
            assert cur.fetchone()[0] == 3

            cur.execute(f"DROP TABLE {skills_table}")
            cur.execute(f"DROP TABLE {clean_table}")
        conn.commit()
