-- ============================================================================
-- SCHEMA ANOTEA - SCHEMA-ON-READ (Incassable)
-- ============================================================================
-- Version: 2.0
-- Date: 2026-01-12
-- Stratégie: Stockage JSON brut PUIS normalisation optionnelle
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TABLE PRIMAIRE: anotea_records (JSON brut)
-- Description: Stockage immutable de tous les payloads API Anotea
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS anotea_records (
    -- Clé primaire composite
    entity_type TEXT NOT NULL,           -- "avis", "formations", "organismes", "sessions", "actions"
    record_id TEXT NOT NULL,             -- ID depuis l'API (ou payload_hash si absent)
    
    -- Payload brut
    payload_json TEXT NOT NULL,          -- JSON complet tel que reçu de l'API
    payload_hash TEXT NOT NULL,          -- MD5(payload_json) pour déduplication
    
    -- Métadonnées d'ingestion
    fetched_at TEXT NOT NULL,            -- ISO 8601 timestamp
    source_page INTEGER,                 -- Numéro de page source
    source_endpoint TEXT,                -- Endpoint source (ex: /anotea/v1/avis)
    
    -- Lifecycle
    is_deleted INTEGER DEFAULT 0,        -- Soft delete
    last_seen_at TEXT,                   -- Dernière fois vu dans un scan
    
    -- Contraintes
    PRIMARY KEY (entity_type, record_id),
    CHECK (is_deleted IN (0, 1)),
    CHECK (entity_type IN ('avis', 'formations', 'organismes', 'sessions', 'actions'))
);

CREATE INDEX idx_anotea_records_hash ON anotea_records(payload_hash);
CREATE INDEX idx_anotea_records_fetched ON anotea_records(fetched_at);
CREATE INDEX idx_anotea_records_deleted ON anotea_records(is_deleted);
CREATE INDEX idx_anotea_records_entity ON anotea_records(entity_type, is_deleted);


-- ----------------------------------------------------------------------------
-- TABLES NORMALISÉES (DÉRIVÉES - OPTIONNELLES)
-- Description: Vues matérialisées pour requêtes rapides
-- IMPORTANT: Ces tables sont reconstruites depuis anotea_records
-- ----------------------------------------------------------------------------

-- Table avis (dérivée)
CREATE TABLE IF NOT EXISTS avis_normalized (
    avis_id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL,             -- FK vers anotea_records
    
    -- Champs CONFIRMÉS uniquement (à adapter selon payload réel)
    note_globale REAL,
    date_avis TEXT,
    commentaire TEXT,
    
    -- Métadonnées
    normalized_at TEXT NOT NULL,
    is_deleted INTEGER DEFAULT 0,
    
    FOREIGN KEY (record_id) REFERENCES anotea_records(record_id),
    CHECK (is_deleted IN (0, 1))
);

CREATE INDEX idx_avis_normalized_record ON avis_normalized(record_id);
CREATE INDEX idx_avis_normalized_deleted ON avis_normalized(is_deleted);


-- ----------------------------------------------------------------------------
-- TABLE: sync_metadata (inchangée)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_metadata (
    sync_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    nb_records_fetched INTEGER,
    nb_records_inserted INTEGER,
    nb_records_updated INTEGER,
    nb_records_deleted INTEGER,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_seconds REAL,
    status TEXT NOT NULL,
    error_message TEXT,
    CHECK (sync_type IN ('full_snapshot', 'incremental')),
    CHECK (status IN ('success', 'partial', 'failed'))
);

CREATE INDEX idx_sync_entity ON sync_metadata(entity_type);
CREATE INDEX idx_sync_date ON sync_metadata(started_at);
CREATE INDEX idx_sync_status ON sync_metadata(status);
