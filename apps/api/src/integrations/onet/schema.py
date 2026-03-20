SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ingestion_run (
    run_id TEXT PRIMARY KEY,
    source_system TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    source_api_version TEXT,
    source_db_version TEXT,
    source_db_version_name TEXT,
    source_db_version_url TEXT,
    config_json TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS ingestion_resource (
    run_id TEXT NOT NULL,
    resource_name TEXT NOT NULL,
    endpoint_path TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    next_start INTEGER,
    last_end INTEGER,
    pages_fetched INTEGER NOT NULL DEFAULT 0,
    rows_seen INTEGER NOT NULL DEFAULT 0,
    rows_staged INTEGER NOT NULL DEFAULT 0,
    rows_normalized INTEGER NOT NULL DEFAULT 0,
    rows_mapped INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    error_message TEXT,
    PRIMARY KEY (run_id, resource_name)
);

CREATE TABLE IF NOT EXISTS source_version (
    source_system TEXT NOT NULL,
    api_version TEXT,
    database_version TEXT,
    database_version_name TEXT,
    database_version_url TEXT,
    recorded_at TEXT NOT NULL,
    raw_payload_hash TEXT NOT NULL,
    PRIMARY KEY (source_system, recorded_at)
);

CREATE TABLE IF NOT EXISTS onet_raw_payload (
    payload_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    resource_name TEXT NOT NULL,
    page_start INTEGER,
    page_end INTEGER,
    source_id TEXT,
    payload_sha256 TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    http_status INTEGER,
    fetched_at TEXT NOT NULL,
    processing_status TEXT NOT NULL,
    UNIQUE(run_id, resource_name, payload_sha256)
);

CREATE TABLE IF NOT EXISTS onet_database_table (
    table_id TEXT PRIMARY KEY,
    table_name TEXT,
    category TEXT,
    description TEXT,
    row_count INTEGER,
    source_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS onet_database_column (
    table_id TEXT NOT NULL,
    column_id TEXT NOT NULL,
    column_name TEXT,
    data_type TEXT,
    ordinal_position INTEGER,
    source_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (table_id, column_id)
);

CREATE TABLE IF NOT EXISTS onet_occupation (
    onetsoc_code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    title_norm TEXT NOT NULL,
    description TEXT,
    source_db_version_name TEXT,
    source_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS onet_occupation_alt_title (
    onetsoc_code TEXT NOT NULL,
    alt_title TEXT NOT NULL,
    alt_title_norm TEXT NOT NULL,
    short_title TEXT,
    sources TEXT,
    source_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (onetsoc_code, alt_title_norm)
);

CREATE TABLE IF NOT EXISTS onet_skill (
    external_skill_id TEXT PRIMARY KEY,
    source_table TEXT NOT NULL,
    source_key TEXT,
    skill_name TEXT NOT NULL,
    skill_name_norm TEXT NOT NULL,
    content_element_id TEXT,
    commodity_code TEXT,
    commodity_title TEXT,
    scale_id TEXT,
    scale_name TEXT,
    source_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS onet_occupation_skill (
    onetsoc_code TEXT NOT NULL,
    external_skill_id TEXT NOT NULL,
    scale_name TEXT NOT NULL,
    data_value REAL,
    n INTEGER,
    recommend_suppress TEXT,
    not_relevant TEXT,
    domain_source TEXT,
    source_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (onetsoc_code, external_skill_id, scale_name)
);

CREATE TABLE IF NOT EXISTS onet_occupation_technology_skill (
    onetsoc_code TEXT NOT NULL,
    external_skill_id TEXT NOT NULL,
    technology_label TEXT NOT NULL,
    technology_label_norm TEXT NOT NULL,
    commodity_code TEXT,
    commodity_title TEXT,
    hot_technology TEXT,
    in_demand TEXT,
    source_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (onetsoc_code, external_skill_id)
);

CREATE TABLE IF NOT EXISTS onet_occupation_tool (
    onetsoc_code TEXT NOT NULL,
    external_skill_id TEXT NOT NULL,
    tool_label TEXT NOT NULL,
    tool_label_norm TEXT NOT NULL,
    commodity_code TEXT,
    commodity_title TEXT,
    source_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (onetsoc_code, external_skill_id)
);

CREATE TABLE IF NOT EXISTS onet_skill_mapping_to_canonical (
    external_skill_id TEXT NOT NULL,
    canonical_skill_id TEXT NOT NULL,
    canonical_label TEXT,
    match_method TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    status TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (external_skill_id, canonical_skill_id)
);

CREATE TABLE IF NOT EXISTS onet_canonical_promotion_candidate (
    external_skill_id TEXT PRIMARY KEY,
    proposed_canonical_id TEXT NOT NULL,
    proposed_label TEXT NOT NULL,
    proposed_entity_type TEXT NOT NULL,
    source_table TEXT NOT NULL,
    status TEXT NOT NULL,
    review_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    match_weight_policy TEXT NOT NULL,
    display_policy TEXT NOT NULL,
    promotion_score REAL,
    promotion_tier TEXT,
    triage_reason TEXT,
    evidence_json TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS onet_unresolved_skill (
    external_skill_id TEXT PRIMARY KEY,
    source_table TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    skill_name_norm TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    status TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ingestion_run_status ON ingestion_run(status);
CREATE INDEX IF NOT EXISTS idx_ingestion_resource_status ON ingestion_resource(status);
CREATE INDEX IF NOT EXISTS idx_raw_payload_resource ON onet_raw_payload(run_id, resource_name);
CREATE INDEX IF NOT EXISTS idx_raw_payload_status ON onet_raw_payload(processing_status);
CREATE INDEX IF NOT EXISTS idx_onet_occupation_title_norm ON onet_occupation(title_norm);
CREATE INDEX IF NOT EXISTS idx_onet_alt_title_norm ON onet_occupation_alt_title(alt_title_norm);
CREATE INDEX IF NOT EXISTS idx_onet_skill_name_norm ON onet_skill(skill_name_norm);
CREATE INDEX IF NOT EXISTS idx_onet_skill_source_table ON onet_skill(source_table);
CREATE INDEX IF NOT EXISTS idx_onet_occ_skill_occ ON onet_occupation_skill(onetsoc_code);
CREATE INDEX IF NOT EXISTS idx_onet_occ_skill_skill ON onet_occupation_skill(external_skill_id);
CREATE INDEX IF NOT EXISTS idx_onet_tech_occ ON onet_occupation_technology_skill(onetsoc_code);
CREATE INDEX IF NOT EXISTS idx_onet_tool_occ ON onet_occupation_tool(onetsoc_code);
CREATE INDEX IF NOT EXISTS idx_onet_mapping_status ON onet_skill_mapping_to_canonical(status);
CREATE INDEX IF NOT EXISTS idx_onet_mapping_canonical ON onet_skill_mapping_to_canonical(canonical_skill_id);
CREATE INDEX IF NOT EXISTS idx_onet_promotion_review ON onet_canonical_promotion_candidate(review_status);
CREATE INDEX IF NOT EXISTS idx_onet_promotion_type ON onet_canonical_promotion_candidate(proposed_entity_type);
CREATE INDEX IF NOT EXISTS idx_onet_unresolved_status ON onet_unresolved_skill(status);
"""
