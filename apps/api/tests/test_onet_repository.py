import sqlite3

from integrations.onet.repository import OnetRepository


def test_onet_repository_creates_schema_and_upserts_table(tmp_path):
    repo = OnetRepository(tmp_path / "onet.db")
    repo.ensure_schema()

    repo.upsert_database_table(
        table_id="occupation_data",
        table_name="Occupation Data",
        category="database",
        description="desc",
        row_count=12,
        source_hash="hash-1",
    )
    repo.upsert_database_table(
        table_id="occupation_data",
        table_name="Occupation Data Updated",
        category="database",
        description="desc2",
        row_count=13,
        source_hash="hash-2",
    )

    conn = sqlite3.connect(str(tmp_path / "onet.db"))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM onet_database_table WHERE table_id = 'occupation_data'").fetchone()
    conn.close()

    assert row["table_name"] == "Occupation Data Updated"
    assert row["row_count"] == 13
    assert row["source_hash"] == "hash-2"


def test_onet_repository_stores_typed_mapping_outcomes(tmp_path):
    repo = OnetRepository(tmp_path / "onet.db")
    repo.ensure_schema()

    mapped, proposed, rejected = repo.replace_typed_skill_mapping_outcomes(
        mappings=[
            {
                "external_skill_id": "skills:python",
                "canonical_skill_id": "skill:statistical_programming",
                "canonical_label": "Statistical Programming",
                "match_method": "tool_match",
                "confidence_score": 0.8,
                "status": "mapped_existing",
                "evidence_json": "{}",
                "source_hash": "m1",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ],
        proposals=[
            {
                "external_skill_id": "skills:hris",
                "proposed_canonical_id": "skill:hris",
                "proposed_label": "HRIS",
                "proposed_entity_type": "skill_domain",
                "source_table": "skills",
                "status": "proposed_from_onet",
                "review_status": "pending",
                "reason": "discriminant_external_skill",
                "match_weight_policy": "matching_core",
                "display_policy": "standard",
                "evidence_json": "{}",
                "source_hash": "p1",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ],
        rejected=[
            {
                "external_skill_id": "skills:active_listening",
                "source_table": "skills",
                "skill_name": "Active Listening",
                "skill_name_norm": "active listening",
                "reason": "generic_non_discriminant_skill",
                "evidence_json": "{}",
                "status": "rejected_noise",
                "source_hash": "r1",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ],
    )

    assert (mapped, proposed, rejected) == (1, 1, 1)

    conn = sqlite3.connect(str(tmp_path / "onet.db"))
    conn.row_factory = sqlite3.Row
    mapped_row = conn.execute("SELECT status FROM onet_skill_mapping_to_canonical WHERE external_skill_id='skills:python'").fetchone()
    proposed_row = conn.execute("SELECT review_status FROM onet_canonical_promotion_candidate WHERE external_skill_id='skills:hris'").fetchone()
    rejected_row = conn.execute("SELECT status FROM onet_unresolved_skill WHERE external_skill_id='skills:active_listening'").fetchone()
    conn.close()

    assert mapped_row["status"] == "mapped_existing"
    assert proposed_row["review_status"] == "pending"
    assert rejected_row["status"] == "rejected_noise"


def test_onet_repository_can_upsert_mappings_and_governance_rows_independently(tmp_path):
    repo = OnetRepository(tmp_path / "onet.db")
    repo.ensure_schema()

    inserted_mappings = repo.upsert_skill_mappings(
        [
            {
                "external_skill_id": "technology_skills:sap",
                "canonical_skill_id": "skill:erp_usage",
                "canonical_label": "ERP Usage",
                "match_method": "governed_high_priority_review",
                "confidence_score": 0.96,
                "status": "mapped_existing",
                "evidence_json": '{"review":"approved"}',
                "source_hash": "map-1",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ]
    )
    inserted_proposals = repo.upsert_canonical_promotion_candidates(
        [
            {
                "external_skill_id": "technology_skills:screen_reader",
                "proposed_canonical_id": "skill:digital_accessibility",
                "proposed_label": "Digital Accessibility",
                "proposed_entity_type": "skill_technical",
                "source_table": "technology_skills",
                "status": "proposed_from_onet",
                "review_status": "approved",
                "reason": "governed_high_priority_technical_skill",
                "match_weight_policy": "matching_core",
                "display_policy": "standard",
                "promotion_score": 0.8,
                "promotion_tier": "high_priority",
                "triage_reason": "governed_high_priority_approved",
                "evidence_json": '{"review":"approved"}',
                "source_hash": "proposal-1",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ]
    )

    assert inserted_mappings == 1
    assert inserted_proposals == 1

    conn = sqlite3.connect(str(tmp_path / "onet.db"))
    conn.row_factory = sqlite3.Row
    mapped_row = conn.execute(
        "SELECT canonical_skill_id, status FROM onet_skill_mapping_to_canonical WHERE external_skill_id='technology_skills:sap'"
    ).fetchone()
    proposal_row = conn.execute(
        "SELECT proposed_canonical_id, review_status FROM onet_canonical_promotion_candidate WHERE external_skill_id='technology_skills:screen_reader'"
    ).fetchone()
    conn.close()

    assert mapped_row["canonical_skill_id"] == "skill:erp_usage"
    assert mapped_row["status"] == "mapped_existing"
    assert proposal_row["proposed_canonical_id"] == "skill:digital_accessibility"
    assert proposal_row["review_status"] == "approved"


def test_onet_repository_filters_low_discriminant_skills_from_occupation_signatures(tmp_path):
    repo = OnetRepository(tmp_path / "onet.db")
    repo.ensure_schema()

    with repo.connect() as conn:
        conn.executemany(
            """
            INSERT INTO onet_occupation (onetsoc_code, title, title_norm, description, source_db_version_name, source_hash, status, updated_at)
            VALUES (?, ?, ?, '', '', ?, 'active', '2026-01-01T00:00:00Z')
            """,
            [
                ("15-1252.00", "Software Developers", "software developers", "occ-1"),
                ("13-1081.00", "Logisticians", "logisticians", "occ-2"),
                ("41-4011.00", "Sales Representatives", "sales representatives", "occ-3"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO onet_skill (
                external_skill_id, source_table, source_key, skill_name, skill_name_norm, source_hash, status, updated_at
            ) VALUES (?, 'technology_skills', ?, ?, ?, ?, 'active', '2026-01-01T00:00:00Z')
            """,
            [
                ("skills:ps1", "ps1", "Problem Solving", "problem solving", "hash-ps1"),
                ("skills:ps2", "ps2", "Problem Solving", "problem solving", "hash-ps2"),
                ("skills:ps3", "ps3", "Problem Solving", "problem solving", "hash-ps3"),
                ("skills:erp", "erp", "SAP", "sap", "hash-erp"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO onet_occupation_technology_skill (
                onetsoc_code, external_skill_id, technology_label, technology_label_norm, commodity_code, commodity_title, source_hash, status, updated_at
            ) VALUES (?, ?, ?, ?, '', '', ?, 'active', '2026-01-01T00:00:00Z')
            """,
            [
                ("15-1252.00", "skills:ps1", "Problem Solving", "problem solving", "link-1"),
                ("13-1081.00", "skills:ps2", "Problem Solving", "problem solving", "link-2"),
                ("41-4011.00", "skills:ps3", "Problem Solving", "problem solving", "link-3"),
                ("13-1081.00", "skills:erp", "SAP", "sap", "link-4"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO onet_skill_mapping_to_canonical (
                external_skill_id, canonical_skill_id, canonical_label, match_method,
                confidence_score, status, evidence_json, source_hash, updated_at
            ) VALUES (?, ?, ?, 'governed_high_priority_review', 0.9, 'mapped_existing', '{}', ?, '2026-01-01T00:00:00Z')
            """,
            [
                ("skills:ps1", "skill:problem_solving", "Problem Solving", "map-1"),
                ("skills:ps2", "skill:problem_solving", "Problem Solving", "map-2"),
                ("skills:ps3", "skill:problem_solving", "Problem Solving", "map-3"),
                ("skills:erp", "skill:erp_usage", "ERP Usage", "map-4"),
            ],
        )
        conn.commit()

    raw_rows = repo.list_occupation_mapped_skills(apply_signature_filter=False)
    filtered_rows = repo.list_occupation_mapped_skills(apply_signature_filter=True, apply_signature_calibration=False)

    assert {row["canonical_skill_id"] for row in raw_rows} == {"skill:problem_solving", "skill:erp_usage"}
    assert [row["canonical_skill_id"] for row in filtered_rows] == ["skill:erp_usage"]


def test_onet_repository_applies_cluster_calibration_to_medium_signal_skills(tmp_path):
    repo = OnetRepository(tmp_path / "onet.db")
    repo.ensure_schema()

    with repo.connect() as conn:
        conn.executemany(
            """
            INSERT INTO onet_occupation (onetsoc_code, title, title_norm, description, source_db_version_name, source_hash, status, updated_at)
            VALUES (?, ?, ?, '', '', ?, 'active', '2026-01-01T00:00:00Z')
            """,
            [
                ("13-1081.00", "Logisticians", "logisticians", "occ-1"),
                ("41-4011.00", "Sales Representatives", "sales representatives", "occ-2"),
                ("15-1252.00", "Software Developers", "software developers", "occ-3"),
                ("15-1244.00", "Network and Computer Systems Administrators", "network and computer systems administrators", "occ-4"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO onet_skill (
                external_skill_id, source_table, source_key, skill_name, skill_name_norm, source_hash, status, updated_at
            ) VALUES (?, 'technology_skills', ?, ?, ?, ?, 'active', '2026-01-01T00:00:00Z')
            """,
            [
                ("skills:erp1", "erp1", "ERP", "erp", "hash-erp1"),
                ("skills:erp2", "erp2", "ERP", "erp", "hash-erp2"),
                ("skills:pm1", "pm1", "Project Management", "project management", "hash-pm1"),
                ("skills:pm2", "pm2", "Project Management", "project management", "hash-pm2"),
                ("skills:scm", "scm", "Supply Chain", "supply chain", "hash-scm"),
                ("skills:crm1", "crm1", "CRM", "crm", "hash-crm1"),
                ("skills:crm2", "crm2", "CRM", "crm", "hash-crm2"),
                ("skills:lead1", "lead1", "Lead Generation", "lead generation", "hash-lead1"),
                ("skills:lead2", "lead2", "Lead Generation", "lead generation", "hash-lead2"),
                ("skills:backend", "backend", "Backend", "backend", "hash-backend"),
                ("skills:webapi", "webapi", "Web API", "web api", "hash-webapi"),
                ("skills:linux", "linux", "Linux", "linux", "hash-linux"),
                ("skills:linux2", "linux2", "Linux", "linux", "hash-linux2"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO onet_occupation_technology_skill (
                onetsoc_code, external_skill_id, technology_label, technology_label_norm, commodity_code, commodity_title, source_hash, status, updated_at
            ) VALUES (?, ?, ?, ?, '', '', ?, 'active', '2026-01-01T00:00:00Z')
            """,
            [
                ("13-1081.00", "skills:erp1", "ERP", "erp", "link-1"),
                ("13-1081.00", "skills:scm", "Supply Chain", "supply chain", "link-2"),
                ("41-4011.00", "skills:erp2", "ERP", "erp", "link-3"),
                ("15-1252.00", "skills:pm1", "Project Management", "project management", "link-4"),
                ("15-1252.00", "skills:backend", "Backend", "backend", "link-5"),
                ("15-1252.00", "skills:webapi", "Web API", "web api", "link-6"),
                ("15-1244.00", "skills:pm2", "Project Management", "project management", "link-7"),
                ("15-1244.00", "skills:linux", "Linux", "linux", "link-8"),
                ("41-4011.00", "skills:crm1", "CRM", "crm", "link-9"),
                ("41-4011.00", "skills:lead1", "Lead Generation", "lead generation", "link-10"),
                ("15-1252.00", "skills:crm2", "CRM", "crm", "link-11"),
                ("15-1252.00", "skills:lead2", "Lead Generation", "lead generation", "link-12"),
                ("15-1252.00", "skills:linux2", "Linux", "linux", "link-13"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO onet_skill_mapping_to_canonical (
                external_skill_id, canonical_skill_id, canonical_label, match_method,
                confidence_score, status, evidence_json, source_hash, updated_at
            ) VALUES (?, ?, ?, 'governed_high_priority_review', 0.9, 'mapped_existing', '{}', ?, '2026-01-01T00:00:00Z')
            """,
            [
                ("skills:erp1", "skill:erp_usage", "ERP Usage", "map-1"),
                ("skills:erp2", "skill:erp_usage", "ERP Usage", "map-2"),
                ("skills:pm1", "skill:project_management", "Project Management", "map-3"),
                ("skills:pm2", "skill:project_management", "Project Management", "map-4"),
                ("skills:scm", "skill:supply_chain_management", "Supply Chain Management", "map-5"),
                ("skills:crm1", "skill:crm_management", "CRM Management", "map-6"),
                ("skills:crm2", "skill:crm_management", "CRM Management", "map-7"),
                ("skills:lead1", "skill:lead_generation", "Lead Generation", "map-8"),
                ("skills:lead2", "skill:lead_generation", "Lead Generation", "map-9"),
                ("skills:backend", "skill:backend_development", "Backend Development", "map-10"),
                ("skills:webapi", "skill:web_service_api", "Web Service API", "map-11"),
                ("skills:linux", "skill:linux_administration", "Linux Administration", "map-12"),
                ("skills:linux2", "skill:linux_administration", "Linux Administration", "map-13"),
            ],
        )
        conn.commit()

    low_filtered_rows = repo.list_occupation_mapped_skills(apply_signature_filter=True, apply_signature_calibration=False)
    calibrated_rows = repo.list_occupation_mapped_skills(
        apply_signature_filter=True,
        apply_signature_calibration=True,
        apply_signature_role_context=False,
    )
    refined_rows = repo.list_occupation_mapped_skills()

    def _skills(rows, onetsoc_code):
        return sorted(row["canonical_skill_id"] for row in rows if row["onetsoc_code"] == onetsoc_code)

    assert "skill:erp_usage" in _skills(low_filtered_rows, "41-4011.00")
    assert "skill:project_management" in _skills(low_filtered_rows, "15-1244.00")

    assert "skill:erp_usage" in _skills(calibrated_rows, "13-1081.00")
    assert "skill:erp_usage" not in _skills(calibrated_rows, "41-4011.00")
    assert "skill:project_management" in _skills(calibrated_rows, "15-1252.00")
    assert "skill:project_management" in _skills(calibrated_rows, "15-1244.00")

    refined_rows = repo.list_occupation_mapped_skills(
        apply_signature_domain_refinement=False,
    )

    assert "skill:project_management" in _skills(refined_rows, "15-1252.00")
    assert "skill:project_management" not in _skills(refined_rows, "15-1244.00")


def test_onet_repository_applies_phase2_context_refinement_for_broad_technical_skills(tmp_path):
    repo = OnetRepository(tmp_path / "onet.db")
    repo.ensure_schema()

    with repo.connect() as conn:
        conn.executemany(
            """
            INSERT INTO onet_occupation (onetsoc_code, title, title_norm, description, source_db_version_name, source_hash, status, updated_at)
            VALUES (?, ?, ?, '', '', ?, 'active', '2026-01-01T00:00:00Z')
            """,
            [
                ("15-1252.00", "Software Developers", "software developers", "occ-1"),
                ("13-1081.00", "Logisticians", "logisticians", "occ-2"),
                ("17-2112.00", "Industrial Engineers", "industrial engineers", "occ-3"),
                ("11-1021.00", "General and Operations Managers", "general and operations managers", "occ-4"),
                ("15-2051.01", "Business Intelligence Analysts", "business intelligence analysts", "occ-5"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO onet_skill (
                external_skill_id, source_table, source_key, skill_name, skill_name_norm, source_hash, status, updated_at
            ) VALUES (?, 'technology_skills', ?, ?, ?, ?, 'active', '2026-01-01T00:00:00Z')
            """,
            [
                ("skills:script_sw", "script_sw", "Scripting", "scripting", "hash-1"),
                ("skills:backend", "backend", "Backend", "backend", "hash-2"),
                ("skills:webapi", "webapi", "Web API", "web api", "hash-3"),
                ("skills:script_ops", "script_ops", "Scripting", "scripting", "hash-4"),
                ("skills:scm", "scm", "Supply Chain", "supply chain", "hash-5"),
                ("skills:proc", "proc", "Procurement", "procurement", "hash-6"),
                ("skills:erp", "erp", "ERP", "erp", "hash-7"),
                ("skills:vendor", "vendor", "Vendor", "vendor", "hash-8"),
                ("skills:process", "process", "Process Mapping", "process mapping", "hash-9"),
                ("skills:cad", "cad", "CAD", "cad", "hash-10"),
                ("skills:td", "td", "Technical Drawing", "technical drawing", "hash-11"),
                ("skills:md", "md", "Mechanical Design", "mechanical design", "hash-12"),
                ("skills:ia", "ia", "Industrial Automation", "industrial automation", "hash-12b"),
                ("skills:ops", "ops", "Operations Management", "operations management", "hash-13"),
                ("skills:ws", "ws", "Workforce Scheduling", "workforce scheduling", "hash-14"),
                ("skills:wh", "wh", "Warehouse", "warehouse", "hash-15"),
                ("skills:dm", "dm", "Data Modeling", "data modeling", "hash-16"),
                ("skills:ml", "ml", "Machine Learning", "machine learning", "hash-17"),
                ("skills:stat", "stat", "Statistical Programming", "statistical programming", "hash-18"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO onet_occupation_technology_skill (
                onetsoc_code, external_skill_id, technology_label, technology_label_norm, commodity_code, commodity_title, source_hash, status, updated_at
            ) VALUES (?, ?, ?, ?, '', '', ?, 'active', '2026-01-01T00:00:00Z')
            """,
            [
                ("15-1252.00", "skills:script_sw", "Scripting", "scripting", "link-1"),
                ("15-1252.00", "skills:backend", "Backend", "backend", "link-2"),
                ("15-1252.00", "skills:webapi", "Web API", "web api", "link-3"),
                ("13-1081.00", "skills:script_ops", "Scripting", "scripting", "link-4"),
                ("13-1081.00", "skills:scm", "Supply Chain", "supply chain", "link-5"),
                ("13-1081.00", "skills:proc", "Procurement", "procurement", "link-6"),
                ("13-1081.00", "skills:erp", "ERP", "erp", "link-7"),
                ("13-1081.00", "skills:vendor", "Vendor", "vendor", "link-8"),
                ("13-1081.00", "skills:process", "Process Mapping", "process mapping", "link-9"),
                ("17-2112.00", "skills:cad", "CAD", "cad", "link-10"),
                ("17-2112.00", "skills:td", "Technical Drawing", "technical drawing", "link-11"),
                ("17-2112.00", "skills:md", "Mechanical Design", "mechanical design", "link-12"),
                ("17-2112.00", "skills:ia", "Industrial Automation", "industrial automation", "link-12b"),
                ("11-1021.00", "skills:ops", "Operations Management", "operations management", "link-13"),
                ("11-1021.00", "skills:ws", "Workforce Scheduling", "workforce scheduling", "link-14"),
                ("11-1021.00", "skills:wh", "Warehouse", "warehouse", "link-15"),
                ("11-1021.00", "skills:vendor", "Vendor", "vendor", "link-16"),
                ("15-2051.01", "skills:dm", "Data Modeling", "data modeling", "link-17"),
                ("15-2051.01", "skills:ml", "Machine Learning", "machine learning", "link-18"),
                ("15-2051.01", "skills:stat", "Statistical Programming", "statistical programming", "link-19"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO onet_skill_mapping_to_canonical (
                external_skill_id, canonical_skill_id, canonical_label, match_method,
                confidence_score, status, evidence_json, source_hash, updated_at
            ) VALUES (?, ?, ?, 'governed_high_priority_review', 0.9, 'mapped_existing', '{}', ?, '2026-01-01T00:00:00Z')
            """,
            [
                ("skills:script_sw", "skill:scripting_automation", "Scripting Automation", "map-1"),
                ("skills:backend", "skill:backend_development", "Backend Development", "map-2"),
                ("skills:webapi", "skill:web_service_api", "Web Service API", "map-3"),
                ("skills:script_ops", "skill:scripting_automation", "Scripting Automation", "map-4"),
                ("skills:scm", "skill:supply_chain_management", "Supply Chain Management", "map-5"),
                ("skills:proc", "skill:procurement_basics", "Procurement Basics", "map-6"),
                ("skills:erp", "skill:erp_usage", "ERP Usage", "map-7"),
                ("skills:vendor", "skill:vendor_management", "Vendor Management", "map-8"),
                ("skills:process", "skill:process_mapping", "Process Mapping", "map-9"),
                ("skills:cad", "skill:cad_modeling", "CAD Modeling", "map-10"),
                ("skills:td", "skill:technical_drawing", "Technical Drawing", "map-11"),
                ("skills:md", "skill:mechanical_design", "Mechanical Design", "map-12"),
                ("skills:ia", "skill:industrial_automation", "Industrial Automation", "map-12b"),
                ("skills:ops", "skill:operations_management", "Operations Management", "map-13"),
                ("skills:ws", "skill:workforce_scheduling", "Workforce Scheduling", "map-14"),
                ("skills:wh", "skill:warehouse_operations", "Warehouse Operations", "map-15"),
                ("skills:dm", "skill:data_modeling", "Data Modeling", "map-16"),
                ("skills:ml", "skill:machine_learning", "Machine Learning", "map-17"),
                ("skills:stat", "skill:statistical_programming", "Statistical Programming", "map-18"),
            ],
        )
        conn.commit()

    phase1_rows = repo.list_occupation_mapped_skills(
        apply_signature_filter=True,
        apply_signature_calibration=True,
        apply_signature_role_context=True,
        apply_signature_role_context_phase2=False,
    )
    refined_rows = repo.list_occupation_mapped_skills()

    def _skills(rows, onetsoc_code):
        return sorted(row["canonical_skill_id"] for row in rows if row["onetsoc_code"] == onetsoc_code)

    assert "skill:scripting_automation" in _skills(phase1_rows, "13-1081.00")
    assert "skill:scripting_automation" not in _skills(refined_rows, "13-1081.00")
    assert "skill:scripting_automation" in _skills(refined_rows, "15-1252.00")
    assert "skill:statistical_programming" in _skills(refined_rows, "15-2051.01")
    assert "skill:cad_modeling" in _skills(refined_rows, "17-2112.00")


def test_onet_repository_applies_domain_refinement_for_broad_domain_skills(tmp_path):
    repo = OnetRepository(tmp_path / "onet.db")
    repo.ensure_schema()

    with repo.connect() as conn:
        conn.executemany(
            """
            INSERT INTO onet_occupation (onetsoc_code, title, title_norm, description, source_db_version_name, source_hash, status, updated_at)
            VALUES (?, ?, ?, '', '', ?, 'active', '2026-01-01T00:00:00Z')
            """,
                [
                    ("15-1252.00", "Software Developers", "software developers", "occ-1"),
                    ("15-1299.09", "Information Technology Project Managers", "information technology project managers", "occ-2"),
                    ("41-4011.00", "Sales Representatives", "sales representatives", "occ-3"),
                    ("13-2011.00", "Accountants and Auditors", "accountants and auditors", "occ-4"),
                ],
            )
        conn.executemany(
            """
            INSERT INTO onet_skill (
                external_skill_id, source_table, source_key, skill_name, skill_name_norm, source_hash, status, updated_at
            ) VALUES (?, 'technology_skills', ?, ?, ?, ?, 'active', '2026-01-01T00:00:00Z')
            """,
                [
                    ("skills:pm_sw", "pm_sw", "Project Management", "project management", "hash-1"),
                ("skills:backend_sw", "backend_sw", "Backend", "backend", "hash-2"),
                ("skills:webapi_sw", "webapi_sw", "Web API", "web api", "hash-3"),
                ("skills:linux_sw", "linux_sw", "Linux", "linux", "hash-4"),
                    ("skills:pm_it", "pm_it", "Project Management", "project management", "hash-5"),
                    ("skills:backend_it", "backend_it", "Backend", "backend", "hash-6"),
                    ("skills:webapi_it", "webapi_it", "Web API", "web api", "hash-7"),
                    ("skills:version_it", "version_it", "Version Control", "version control", "hash-8"),
                    ("skills:crm_sales", "crm_sales", "CRM", "crm", "hash-9"),
                    ("skills:acct_fin", "acct_fin", "Accounting", "accounting", "hash-10"),
                ],
            )
        conn.executemany(
            """
            INSERT INTO onet_occupation_technology_skill (
                onetsoc_code, external_skill_id, technology_label, technology_label_norm, commodity_code, commodity_title, source_hash, status, updated_at
            ) VALUES (?, ?, ?, ?, '', '', ?, 'active', '2026-01-01T00:00:00Z')
            """,
                [
                ("15-1252.00", "skills:pm_sw", "Project Management", "project management", "link-1"),
                ("15-1252.00", "skills:backend_sw", "Backend", "backend", "link-2"),
                ("15-1252.00", "skills:webapi_sw", "Web API", "web api", "link-3"),
                ("15-1252.00", "skills:linux_sw", "Linux", "linux", "link-4"),
                ("15-1299.09", "skills:pm_it", "Project Management", "project management", "link-5"),
                    ("15-1299.09", "skills:backend_it", "Backend", "backend", "link-6"),
                    ("15-1299.09", "skills:webapi_it", "Web API", "web api", "link-7"),
                    ("15-1299.09", "skills:version_it", "Version Control", "version control", "link-8"),
                    ("41-4011.00", "skills:crm_sales", "CRM", "crm", "link-9"),
                    ("13-2011.00", "skills:acct_fin", "Accounting", "accounting", "link-10"),
                ],
            )
        conn.executemany(
            """
            INSERT INTO onet_skill_mapping_to_canonical (
                external_skill_id, canonical_skill_id, canonical_label, match_method,
                confidence_score, status, evidence_json, source_hash, updated_at
            ) VALUES (?, ?, ?, 'governed_high_priority_review', 0.9, 'mapped_existing', '{}', ?, '2026-01-01T00:00:00Z')
            """,
                [
                ("skills:pm_sw", "skill:project_management", "Project Management", "map-1"),
                ("skills:backend_sw", "skill:backend_development", "Backend Development", "map-2"),
                ("skills:webapi_sw", "skill:web_service_api", "Web Service API", "map-3"),
                ("skills:linux_sw", "skill:linux_administration", "Linux Administration", "map-4"),
                    ("skills:pm_it", "skill:project_management", "Project Management", "map-5"),
                    ("skills:backend_it", "skill:backend_development", "Backend Development", "map-6"),
                    ("skills:webapi_it", "skill:web_service_api", "Web Service API", "map-7"),
                    ("skills:version_it", "skill:version_control", "Version Control", "map-8"),
                    ("skills:crm_sales", "skill:crm_management", "CRM Management", "map-9"),
                    ("skills:acct_fin", "skill:accounting_basics", "Accounting Basics", "map-10"),
                ],
            )
        conn.commit()

    phase2_rows = repo.list_occupation_mapped_skills(
        apply_signature_filter=True,
        apply_signature_calibration=True,
        apply_signature_role_context=True,
        apply_signature_role_context_phase2=True,
        apply_signature_domain_refinement=False,
    )
    refined_rows = repo.list_occupation_mapped_skills()

    def _skills(rows, onetsoc_code):
        return sorted(row["canonical_skill_id"] for row in rows if row["onetsoc_code"] == onetsoc_code)

    assert "skill:project_management" in _skills(phase2_rows, "15-1252.00")
    assert "skill:project_management" in _skills(phase2_rows, "15-1299.09")
    assert "skill:project_management" not in _skills(refined_rows, "15-1252.00")
    assert "skill:project_management" in _skills(refined_rows, "15-1299.09")
