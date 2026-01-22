-- ============================================================================
-- SCHEMA ANOTEA - BASE DE DONNÉES NORMALISÉE
-- ============================================================================
-- Version: 1.0
-- Date: 2026-01-12
-- Moteur: SQLite 3.x (migration PostgreSQL compatible)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TABLE: organismes_formateurs
-- Description: Organismes de formation référencés
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS organismes_formateurs (
    organisme_id TEXT PRIMARY KEY,
    siret TEXT,
    uai TEXT,
    raison_sociale TEXT NOT NULL,
    numero_declaration TEXT,
    adresse TEXT,
    code_postal TEXT,
    ville TEXT,
    telephone TEXT,
    email TEXT,
    site_web TEXT,
    nb_avis_total INTEGER DEFAULT 0,
    note_moyenne REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_deleted INTEGER DEFAULT 0,
    CHECK (is_deleted IN (0, 1)),
    CHECK (note_moyenne IS NULL OR (note_moyenne >= 0 AND note_moyenne <= 5))
);

CREATE INDEX idx_organismes_siret ON organismes_formateurs(siret);
CREATE INDEX idx_organismes_ville ON organismes_formateurs(ville);
CREATE INDEX idx_organismes_deleted ON organismes_formateurs(is_deleted);


-- ----------------------------------------------------------------------------
-- TABLE: formations
-- Description: Formations proposées par les organismes
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS formations (
    formation_id TEXT PRIMARY KEY,
    organisme_id TEXT NOT NULL,
    intitule TEXT NOT NULL,
    formacode TEXT,
    certifications TEXT,
    objectifs TEXT,
    programme TEXT,
    duree_heures INTEGER,
    modalite TEXT,
    niveau_entree TEXT,
    niveau_sortie TEXT,
    nb_avis_total INTEGER DEFAULT 0,
    note_moyenne REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_deleted INTEGER DEFAULT 0,
    FOREIGN KEY (organisme_id) REFERENCES organismes_formateurs(organisme_id),
    CHECK (is_deleted IN (0, 1)),
    CHECK (note_moyenne IS NULL OR (note_moyenne >= 0 AND note_moyenne <= 5))
);

CREATE INDEX idx_formations_organisme ON formations(organisme_id);
CREATE INDEX idx_formations_deleted ON formations(is_deleted);
CREATE INDEX idx_formations_formacode ON formations(formacode);


-- ----------------------------------------------------------------------------
-- TABLE: sessions
-- Description: Sessions spécifiques d'une formation (dates, lieu)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    formation_id TEXT NOT NULL,
    organisme_id TEXT NOT NULL,
    date_debut TEXT,
    date_fin TEXT,
    lieu TEXT,
    code_postal TEXT,
    ville TEXT,
    region TEXT,
    nb_avis INTEGER DEFAULT 0,
    note_moyenne REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_deleted INTEGER DEFAULT 0,
    FOREIGN KEY (formation_id) REFERENCES formations(formation_id),
    FOREIGN KEY (organisme_id) REFERENCES organismes_formateurs(organisme_id),
    CHECK (is_deleted IN (0, 1)),
    CHECK (note_moyenne IS NULL OR (note_moyenne >= 0 AND note_moyenne <= 5))
);

CREATE INDEX idx_sessions_formation ON sessions(formation_id);
CREATE INDEX idx_sessions_organisme ON sessions(organisme_id);
CREATE INDEX idx_sessions_dates ON sessions(date_debut, date_fin);
CREATE INDEX idx_sessions_ville ON sessions(ville);
CREATE INDEX idx_sessions_deleted ON sessions(is_deleted);


-- ----------------------------------------------------------------------------
-- TABLE: avis
-- Description: Avis individuels des stagiaires sur les sessions
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS avis (
    avis_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    formation_id TEXT NOT NULL,
    organisme_id TEXT NOT NULL,
    note_globale REAL,
    note_contenu REAL,
    note_accompagnement REAL,
    note_equipement REAL,
    note_ambiance REAL,
    titre TEXT,
    commentaire TEXT,
    points_forts TEXT,
    points_amelioration TEXT,
    profil_age_tranche TEXT,
    profil_statut TEXT,
    certification_obtenue INTEGER,
    emploi_trouve INTEGER,
    statut_publication TEXT,
    date_moderation TEXT,
    payload_hash TEXT,
    date_avis TEXT NOT NULL,
    date_fin_formation TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_deleted INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (formation_id) REFERENCES formations(formation_id),
    FOREIGN KEY (organisme_id) REFERENCES organismes_formateurs(organisme_id),
    CHECK (is_deleted IN (0, 1)),
    CHECK (note_globale IS NULL OR (note_globale >= 1 AND note_globale <= 5)),
    CHECK (certification_obtenue IN (0, 1, NULL)),
    CHECK (emploi_trouve IN (0, 1, NULL))
);

CREATE INDEX idx_avis_session ON avis(session_id);
CREATE INDEX idx_avis_formation ON avis(formation_id);
CREATE INDEX idx_avis_organisme ON avis(organisme_id);
CREATE INDEX idx_avis_date ON avis(date_avis);
CREATE INDEX idx_avis_note ON avis(note_globale);
CREATE INDEX idx_avis_statut ON avis(statut_publication);
CREATE INDEX idx_avis_deleted ON avis(is_deleted);


-- ----------------------------------------------------------------------------
-- TABLE: sync_metadata
-- Description: Métadonnées des synchronisations (audit trail)
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
