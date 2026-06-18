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


def test_classify_offer_domain_rules_support_alone_blocks_admin():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Support applicatif",
        description="",
    )

    assert result["domain_tag"] != "admin"
    assert result["domain_tag"] == "other"
    assert result["needs_ai_review"] is True


def test_classify_offer_domain_rules_communication_alone_blocks_marketing():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Chargé de communication RH",
        description="",
    )

    assert result["domain_tag"] != "marketing"
    assert result["needs_ai_review"] is True


def test_classify_offer_domain_rules_analyst_alone_blocks_data():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Senior Analyst",
        description="",
    )

    assert result["domain_tag"] != "data"
    assert result["needs_ai_review"] is True


def test_classify_offer_domain_rules_talent_acquisition_resolves_to_hr():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Talent acquisition specialist",
        description="",
    )

    assert result["domain_tag"] == "hr"
    assert result["needs_ai_review"] is False
    assert result["confidence"] == 0.9


def test_classify_offer_domain_rules_marketing_manager_resolves_to_marketing():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Marketing manager",
        description="",
    )

    assert result["domain_tag"] == "marketing"
    assert result["needs_ai_review"] is False
    assert result["confidence"] == 0.9


def test_classify_offer_domain_rules_low_evidence_returns_other():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Stagiaire",
        description="audit",
    )

    assert result["domain_tag"] == "other"
    assert result["needs_ai_review"] is True
    assert result["evidence"] == ["low_evidence"]


def test_classify_offer_domain_rules_strong_data_keywords_still_resolve():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Senior Analyst",
        description="SQL Python Power BI dashboards reporting",
    )

    assert result["domain_tag"] == "data"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_product_owner_resolves_to_operations():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Product Owner",
        description="Agile product backlog management requirements gathering stakeholder coordination",
    )

    assert result["domain_tag"] == "operations"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_user_acquisition_resolves_to_marketing():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="User Acquisition Specialist",
        description="performance marketing user acquisition campaigns campaign optimization",
    )

    assert result["domain_tag"] == "marketing"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_talent_recruiter_resolves_to_hr_not_engineering():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Talent Recruiter",
        description="candidate sourcing recruitment interviews employer branding",
    )

    assert result["domain_tag"] == "hr"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_corporate_recruiter_resolves_to_hr():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Corporate Recruiter – Campus & Employer Branding",
        description="talent acquisition campus recruitment employer branding interviews",
    )

    assert result["domain_tag"] == "hr"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_user_acquisition_never_falls_to_hr():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="User Acquisition Specialist",
        description="user acquisition campaigns performance marketing growth paid social",
    )

    assert result["domain_tag"] == "marketing"
    assert "hr" not in (result.get("evidence") or [])


def test_classify_offer_domain_rules_expert_irrigation_does_not_resolve_to_finance():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Expert Irrigation – Customer Success & Avant-Vente",
        description="customer success irrigation technical support avant-vente client relationship agronomy",
    )

    assert result["domain_tag"] in {"sales", "operations"}
    assert result["domain_tag"] != "finance"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_microelectronics_nanotechnology_engineer_resolves_to_engineering():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Microelectronics / Nanotechnology Engineer",
        description="device characterization micro and nanofabrication cleanroom process development",
    )

    assert result["domain_tag"] == "engineering"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_data_integration_expert_resolves_to_data():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Data Integration Expert",
        description="etl pipeline data integration data flows sql",
    )

    assert result["domain_tag"] == "data"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_design_verification_engineer_resolves_to_engineering():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Design Verification Engineer",
        description="verification and validation ibm doors system design testing",
    )

    assert result["domain_tag"] == "engineering"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_asset_operations_support_resolves_to_operations():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Junior Asset Operations Support",
        description="asset operations team operational management energy assets onboarding",
    )

    assert result["domain_tag"] == "operations"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_surveyor_resolves_to_engineering():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Surveyor",
        description="land surveyors spatially related land and sea information civil infrastructure",
    )

    assert result["domain_tag"] == "engineering"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_workforce_planner_resolves_to_operations():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Workforce Planner",
        description="workforce planning staffing levels operational efficiency s&op rofo",
    )

    assert result["domain_tag"] == "operations"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_mes_engineer_resolves_to_engineering():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="INGÉNIEUR MES",
        description="support d'exploitation distribution production optimization industrial facilities",
    )

    assert result["domain_tag"] == "engineering"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_quality_engineer_resolves_to_engineering():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Quality Engineer",
        description="quality management root cause analysis supplier performance quality control",
    )

    assert result["domain_tag"] == "engineering"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_business_manager_does_not_default_to_hr():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Business Manager",
        description="client relationship revenue growth key account sales pipeline",
    )

    assert result["domain_tag"] == "sales"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_business_manager_with_business_unit_language_resolves_to_sales():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Business Manager",
        description="business unit commercial development intrapreneur croissance commerciale",
    )

    assert result["domain_tag"] == "sales"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_business_manager_can_resolve_to_hr_if_recruitment_dominates():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="Business Manager",
        description="talent acquisition recruitment interviews candidate sourcing employer branding campus recruitment",
    )

    assert result["domain_tag"] == "hr"
    assert result["needs_ai_review"] is False


def test_classify_offer_domain_rules_it_buyer_resolves_to_supply():
    from api.utils.offer_domain_enrichment import classify_offer_domain_rules

    result = classify_offer_domain_rules(
        title="IT Buyer",
        description="procurement supplier relationship management contract negotiation",
    )

    assert result["domain_tag"] == "supply"
    assert result["needs_ai_review"] is False


def test_build_offer_intelligence_mvp_hr_recruitment_is_deterministic_and_specific():
    from api.utils.offer_domain_enrichment import build_offer_intelligence_mvp

    result = build_offer_intelligence_mvp(
        domain_tag="hr",
        title="Talent Acquisition Specialist",
        description="Candidate sourcing, onboarding, ATS management, recruitment interviews.",
        skills_text="candidate sourcing onboarding ats management recruitment interviews",
    )

    assert result["job_family"] == "Human Resources"
    assert result["primary_function"] == "Recruitment"
    assert result["purity_score"] == pytest.approx(1.0, abs=1e-6)
    assert result["hybrid_score"] == pytest.approx(0.0, abs=1e-6)


def test_build_offer_intelligence_mvp_detects_finance_data_hybrid_pressure():
    from api.utils.offer_domain_enrichment import build_offer_intelligence_mvp

    result = build_offer_intelligence_mvp(
        domain_tag="finance",
        title="Finance Data Analyst",
        description="Budgeting, financial analysis, reporting, SQL, Power BI dashboards.",
        skills_text="budgeting financial analysis sql power bi reporting",
    )

    assert result["job_family"] == "Finance"
    assert result["primary_function"] == "Controlling"
    assert result["purity_score"] == pytest.approx(0.3333, rel=1e-3)
    assert result["hybrid_score"] == pytest.approx(0.5, rel=1e-3)


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


@pytest.mark.skipif(not _database_url(), reason="DATABASE_URL not configured")
def test_offer_domain_enrichment_persists_offer_intelligence_mvp_fields():
    import psycopg

    from api.utils.offer_domain_enrichment import classify_and_persist_business_france_offer_domains_with_connection

    database_url = _database_url()
    assert database_url
    suffix = uuid.uuid4().hex[:8]
    clean_table = f"clean_offers_domain_offer_intel_{suffix}"
    enrichment_table = f"offer_domain_enrichment_offer_intel_{suffix}"

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
                VALUES (
                    'business_france',
                    'BF-OFFER-INTEL-1',
                    'Talent Acquisition Specialist',
                    'Candidate sourcing, onboarding, ATS management, recruitment interviews.',
                    '{{}}'::jsonb,
                    NOW()
                )
                """
            )
        conn.commit()

        result = classify_and_persist_business_france_offer_domains_with_connection(
            conn,
            clean_table=clean_table,
            enrichment_table=enrichment_table,
            enable_ai_fallback=False,
        )

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT job_family, primary_function, purity_score, hybrid_score
                FROM {enrichment_table}
                WHERE external_id = 'BF-OFFER-INTEL-1'
                """
            )
            row = cur.fetchone()
            assert row[0] == "Human Resources"
            assert row[1] == "Recruitment"
            assert float(row[2]) > 0.7
            assert float(row[3]) == pytest.approx(0.0, abs=1e-6)
            cur.execute(f"DROP TABLE {enrichment_table}")
            cur.execute(f"DROP TABLE {clean_table}")
        conn.commit()

    assert result["classified_count"] == 1
    assert result["remaining_needs_review"] == 0


@pytest.mark.skipif(not _database_url(), reason="DATABASE_URL not configured")
def test_offer_domain_enrichment_reprocesses_same_hash_row_when_offer_intelligence_fields_missing():
    import psycopg

    from api.utils.offer_domain_enrichment import (
        classify_and_persist_business_france_offer_domains_with_connection,
        compute_offer_content_hash,
        ensure_offer_domain_enrichment_table,
    )

    database_url = _database_url()
    assert database_url
    suffix = uuid.uuid4().hex[:8]
    clean_table = f"clean_offers_domain_offer_intel_missing_{suffix}"
    enrichment_table = f"offer_domain_enrichment_offer_intel_missing_{suffix}"
    content_hash = compute_offer_content_hash(
        title="Talent Acquisition Specialist",
        description="Candidate sourcing, onboarding, ATS management, recruitment interviews.",
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
            cur.execute(
                f"""
                INSERT INTO {clean_table} (source, external_id, title, description, payload_json, cleaned_at)
                VALUES (
                    'business_france',
                    'BF-OFFER-INTEL-MISSING',
                    'Talent Acquisition Specialist',
                    'Candidate sourcing, onboarding, ATS management, recruitment interviews.',
                    '{{}}'::jsonb,
                    NOW()
                )
                """
            )
        ensure_offer_domain_enrichment_table(conn, table_name=enrichment_table)
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {enrichment_table} (
                    source, external_id, domain_tag, confidence, method, evidence, needs_ai_review, content_hash
                ) VALUES (
                    'business_france', 'BF-OFFER-INTEL-MISSING', 'hr', 0.9, 'rules', '["talent acquisition"]'::jsonb, FALSE, %s
                )
                """,
                (content_hash,),
            )
        conn.commit()

        result = classify_and_persist_business_france_offer_domains_with_connection(
            conn,
            clean_table=clean_table,
            enrichment_table=enrichment_table,
            enable_ai_fallback=False,
        )

        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT job_family, primary_function, purity_score, hybrid_score
                FROM {enrichment_table}
                WHERE external_id = 'BF-OFFER-INTEL-MISSING'
                """
            )
            row = cur.fetchone()
            assert row[0] == "Human Resources"
            assert row[1] == "Recruitment"
            assert float(row[2]) > 0.7
            assert float(row[3]) == pytest.approx(0.0, abs=1e-6)
            cur.execute(f"DROP TABLE {enrichment_table}")
            cur.execute(f"DROP TABLE {clean_table}")
        conn.commit()

    assert result["classified_count"] == 1
    assert result["skipped_count"] == 0
