import os
import uuid
import time

import pytest
from dotenv import dotenv_values


def _database_url() -> str | None:
    cfg = dotenv_values("apps/api/.env")
    return cfg.get("DATABASE_URL") or os.getenv("DATABASE_URL")


def test_classify_offer_domain_rules_data_offer():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Responsable Reporting & Data Analyst",
        description="SQL Python Power BI reporting dashboard business intelligence",
    )

    assert result["domain_tag"] == "data"
    assert result["method"] == "rules"
    assert result["needs_ai_review"] is False
    assert result["evidence"] in (["data analyst"], ["business intelligence"])


def test_classify_offer_domain_rules_phrase_first_forces_sales():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Business Development Analyst",
        description="client growth revenue analyst",
    )

    assert result == {
        "domain_tag": "sales",
        "confidence": 0.9,
        "method": "rules",
        "evidence": ["business development"],
        "needs_ai_review": False,
    }


def test_classify_offer_domain_rules_controller_override_forces_finance():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Business Controller",
        description="operations coordination reporting",
    )

    assert result["domain_tag"] == "finance"
    assert result["needs_ai_review"] is False
    assert result["evidence"] in (["business controller"], ["controller"], ["controle"])


def test_classify_offer_domain_rules_data_alone_does_not_autoclassify():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Data",
        description="data data data",
    )

    assert result["domain_tag"] == "other"
    assert result["needs_ai_review"] is True
    assert result["evidence"] == ["no_rule_match"]


def test_classify_offer_domain_rules_ignores_operations_when_sales_is_strong():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Key Account Manager Operations",
        description="client revenue operations coordination",
    )

    assert result["domain_tag"] == "sales"
    assert result["needs_ai_review"] is False
    assert result["evidence"] in (["key account"], ["account manager"], ["client relationship"])


def test_classify_offer_domain_rules_tie_requires_ai_review():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="HR Sales Coordinator",
        description="recruitment client coordination",
    )

    assert result["needs_ai_review"] is True
    assert result["domain_tag"] in {"hr", "sales", "admin", "operations"}


def test_compute_offer_content_hash_changes_with_title_or_description():
    from api.utils.offer_domain_enrichment import compute_offer_content_hash

    base = compute_offer_content_hash(title="Data Analyst", description="SQL reporting")
    same = compute_offer_content_hash(title="Data Analyst", description="SQL reporting")
    changed_title = compute_offer_content_hash(title="Senior Data Analyst", description="SQL reporting")
    changed_description = compute_offer_content_hash(title="Data Analyst", description="Python reporting")

    assert base == same
    assert base != changed_title
    assert base != changed_description


def test_normalize_ai_domain_result_rejects_invalid_domain_or_missing_fields():
    from api.utils.offer_domain_enrichment import normalize_ai_domain_result

    with pytest.raises(RuntimeError):
        normalize_ai_domain_result({"domain_tag": "unknown", "confidence": 0.5, "evidence": ["x"]})
    with pytest.raises(RuntimeError):
        normalize_ai_domain_result({"domain_tag": "data", "evidence": ["sql"]})
    with pytest.raises(RuntimeError):
        normalize_ai_domain_result({"domain_tag": "data", "confidence": 0.8})


@pytest.mark.skipif(not _database_url(), reason="DATABASE_URL not configured")
def test_offer_domain_enrichment_reprocesses_existing_ambiguous_rules_row_with_same_hash_for_ai():
    import psycopg

    from api.utils.offer_domain_enrichment import (
        classify_and_persist_business_france_offer_domains_with_connection,
        compute_offer_content_hash,
        ensure_offer_domain_enrichment_table,
    )

    database_url = _database_url()
    assert database_url
    suffix = uuid.uuid4().hex[:8]
    clean_table = f"clean_offers_domain_same_hash_ai_{suffix}"
    enrichment_table = f"offer_domain_enrichment_same_hash_ai_{suffix}"
    content_hash = compute_offer_content_hash(
        title="HR Sales Coordinator",
        description="recruitment client coordination",
    )

    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
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
        ensure_offer_domain_enrichment_table(conn, table_name=enrichment_table)
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {clean_table} (source, external_id, title, description, payload_json, cleaned_at)
                VALUES ('business_france', 'BF-AI-SAME', 'HR Sales Coordinator', 'recruitment client coordination', '{{}}'::jsonb, NOW())
                """
            )
            cur.execute(
                f"""
                INSERT INTO {enrichment_table} (
                    source, external_id, domain_tag, confidence, method, evidence, needs_ai_review, content_hash, created_at, updated_at
                ) VALUES (
                    'business_france', 'BF-AI-SAME', 'hr', 0.5, 'rules', '["recruitment"]'::jsonb, TRUE, %s, NOW(), NOW()
                )
                """,
                (content_hash,),
            )
        conn.commit()

        def fake_ai_classifier(*, title, description, skills_text=None):
            return {
                "domain_tag": "hr",
                "confidence": 0.91,
                "evidence": ["recruitment"],
            }

        result = classify_and_persist_business_france_offer_domains_with_connection(
            conn,
            clean_table=clean_table,
            enrichment_table=enrichment_table,
            enable_ai_fallback=True,
            ai_classifier=fake_ai_classifier,
        )

        with conn.cursor() as cur:
            cur.execute(
                f"SELECT method, needs_ai_review FROM {enrichment_table} WHERE external_id = 'BF-AI-SAME'"
            )
            assert cur.fetchone() == ("ai_fallback", False)
            cur.execute(f"DROP TABLE {enrichment_table}")
            cur.execute(f"DROP TABLE {clean_table}")
        conn.commit()

    assert result["ai_processed_count"] == 1
    assert result["ai_success_count"] == 1
    assert result["skipped_count"] == 0
    assert result["remaining_needs_review"] == 0


@pytest.mark.skipif(not _database_url(), reason="DATABASE_URL not configured")
def test_offer_domain_enrichment_ai_fallback_and_rerun_idempotent():
    import psycopg

    from api.utils.offer_domain_enrichment import (
        classify_and_persist_business_france_offer_domains_with_connection,
    )

    database_url = _database_url()
    assert database_url
    suffix = uuid.uuid4().hex[:8]
    clean_table = f"clean_offers_domain_{suffix}"
    enrichment_table = f"offer_domain_enrichment_{suffix}"

    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
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
                INSERT INTO {clean_table} (
                    source, external_id, title, description, payload_json, cleaned_at
                ) VALUES
                (
                    'business_france',
                    'BF-DATA-1',
                    'Data Analyst',
                    'SQL Python reporting Power BI',
                    '{{}}'::jsonb,
                    NOW()
                ),
                (
                    'business_france',
                    'BF-AMB-1',
                    'HR Sales Coordinator',
                    'recruitment client coordination',
                    '{{}}'::jsonb,
                    NOW()
                )
                """
            )
        conn.commit()

        def fake_ai_classifier(*, title, description, skills_text=None):
            return {
                "domain_tag": "hr",
                "confidence": 0.91,
                "evidence": ["payroll", "recruitment"],
            }

        first = classify_and_persist_business_france_offer_domains_with_connection(
            conn,
            clean_table=clean_table,
            enrichment_table=enrichment_table,
            enable_ai_fallback=True,
            ai_classifier=fake_ai_classifier,
        )
        second = classify_and_persist_business_france_offer_domains_with_connection(
            conn,
            clean_table=clean_table,
            enrichment_table=enrichment_table,
            enable_ai_fallback=True,
            ai_classifier=fake_ai_classifier,
        )

        time.sleep(0.05)
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {clean_table}
                SET title = 'Senior Data Analyst'
                WHERE source = 'business_france' AND external_id = 'BF-DATA-1'
                """
            )
        conn.commit()
        third = classify_and_persist_business_france_offer_domains_with_connection(
            conn,
            clean_table=clean_table,
            enrichment_table=enrichment_table,
            enable_ai_fallback=True,
            ai_classifier=fake_ai_classifier,
        )

        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {enrichment_table}")
            assert cur.fetchone()[0] == 2
            cur.execute(
                f"""
                SELECT external_id, domain_tag, method, needs_ai_review, content_hash, created_at, updated_at
                FROM {enrichment_table}
                ORDER BY external_id
                """
            )
            rows = cur.fetchall()
            assert rows[0][:4] == ("BF-AMB-1", "hr", "ai_fallback", False)
            assert rows[1][:4] == ("BF-DATA-1", "data", "rules", False)
            assert rows[0][4]
            assert rows[1][4]
            assert rows[0][5] == rows[0][6]
            assert rows[1][5] < rows[1][6]

            cur.execute(f"DROP TABLE {enrichment_table}")
            cur.execute(f"DROP TABLE {clean_table}")
        conn.commit()

    assert first["processed_count"] == 2
    assert first["classified_count"] == 2
    assert first["skipped_count"] == 0
    assert first["reclassified_count"] == 0
    assert first["ai_processed_count"] == 1
    assert first["ai_success_count"] == 1
    assert first["ai_failed_count"] == 0
    assert first["remaining_needs_review"] == 0
    assert first["ai_fallback_count"] == 1
    assert second["processed_count"] == 2
    assert second["classified_count"] == 0
    assert second["skipped_count"] == 2
    assert second["reclassified_count"] == 0
    assert second["ai_processed_count"] == 0
    assert second["ai_success_count"] == 0
    assert second["ai_failed_count"] == 0
    assert second["remaining_needs_review"] == 0
    assert third["processed_count"] == 2
    assert third["classified_count"] == 1
    assert third["skipped_count"] == 1
    assert third["reclassified_count"] == 1
    assert third["ai_processed_count"] == 0
    assert third["ai_success_count"] == 0
    assert third["ai_failed_count"] == 0
    assert third["remaining_needs_review"] == 0


@pytest.mark.skipif(not _database_url(), reason="DATABASE_URL not configured")
def test_offer_domain_enrichment_invalid_ai_output_keeps_rules_result_and_review():
    import psycopg

    from api.utils.offer_domain_enrichment import classify_and_persist_business_france_offer_domains_with_connection

    database_url = _database_url()
    assert database_url
    suffix = uuid.uuid4().hex[:8]
    clean_table = f"clean_offers_domain_bad_ai_{suffix}"
    enrichment_table = f"offer_domain_enrichment_bad_ai_{suffix}"

    with psycopg.connect(database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
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
                INSERT INTO {clean_table} (source, external_id, title, description, payload_json, cleaned_at)
                VALUES ('business_france', 'BF-AI-BAD', 'HR Sales Coordinator', 'recruitment client coordination', '{{}}'::jsonb, NOW())
                """
            )
        conn.commit()

        def bad_ai_classifier(*, title, description, skills_text=None):
            return {"domain_tag": "random", "confidence": 0.4}

        result = classify_and_persist_business_france_offer_domains_with_connection(
            conn,
            clean_table=clean_table,
            enrichment_table=enrichment_table,
            enable_ai_fallback=True,
            ai_classifier=bad_ai_classifier,
        )

        with conn.cursor() as cur:
            cur.execute(
                f"SELECT domain_tag, method, needs_ai_review FROM {enrichment_table} WHERE external_id = 'BF-AI-BAD'"
            )
            assert cur.fetchone() == ("hr", "rules", True)
            cur.execute(f"DROP TABLE {enrichment_table}")
            cur.execute(f"DROP TABLE {clean_table}")
        conn.commit()

    assert result["ai_processed_count"] == 1
    assert result["ai_success_count"] == 0
    assert result["ai_failed_count"] == 1
    assert result["remaining_needs_review"] == 1
