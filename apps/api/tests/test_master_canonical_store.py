from __future__ import annotations

import sqlite3
from pathlib import Path

from compass.canonical.canonical_store import CanonicalStore
from compass.canonical.entity_types import (
    ENTITY_TYPE_ROLE_FAMILY,
    ENTITY_TYPE_SECTOR,
    ENTITY_TYPE_SKILL_DOMAIN,
    ENTITY_TYPE_SKILL_TECHNICAL,
    ENTITY_TYPE_SKILL_TOOL,
)
from compass.canonical.master_store import _build_master_store
from integrations.onet.schema import SCHEMA_SQL


class DummyStore(CanonicalStore):
    pass


def _make_store() -> CanonicalStore:
    store = DummyStore()
    store.loaded = True
    store.id_to_skill = {
        "skill:sql": {
            "label": "SQL",
            "aliases": ["structured query language"],
            "concept_type": "concept",
            "skill_type": "core",
            "cluster_name": "DATA_ANALYTICS_AI",
            "genericity_score": 0.2,
        },
        "skill:power_bi": {
            "label": "Power BI",
            "aliases": ["powerbi"],
            "concept_type": "tool",
            "skill_type": "support",
            "cluster_name": "DATA_ANALYTICS_AI",
            "genericity_score": 0.1,
        },
        "skill:project_management": {
            "label": "Project Management",
            "aliases": ["gestion de projet"],
            "concept_type": "concept",
            "skill_type": "core",
            "cluster_name": "FINANCE_BUSINESS_OPERATIONS",
            "genericity_score": 0.5,
        },
    }
    store.hierarchy = {"skill:sql": "skill:project_management"}
    return store


def test_master_store_builds_typed_entities_and_internal_seeds(tmp_path: Path):
    master = _build_master_store(_make_store(), tmp_path / "missing.db")

    assert master.loaded is True
    assert master.get("skill:sql").type == ENTITY_TYPE_SKILL_TECHNICAL
    assert master.get("skill:sql").match_weight_policy == "matching_core"
    assert master.get("skill:power_bi").type == ENTITY_TYPE_SKILL_TOOL
    assert master.get("skill:power_bi").match_weight_policy == "matching_secondary"
    assert master.get("skill:project_management").type == ENTITY_TYPE_SKILL_DOMAIN
    assert master.get("role_family:data_analytics").type == ENTITY_TYPE_ROLE_FAMILY
    assert master.get("sector:DATA_IT").type == ENTITY_TYPE_SECTOR
    assert "skill:sql" in master.get("skill:project_management").children


def test_master_store_loads_approved_onet_proposals(tmp_path: Path):
    db_path = tmp_path / "onet.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_SQL)
    conn.execute(
        """
        INSERT INTO onet_canonical_promotion_candidate (
            external_skill_id, proposed_canonical_id, proposed_label, proposed_entity_type,
            source_table, status, review_status, reason, match_weight_policy,
            display_policy, evidence_json, source_hash, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "skills:hris",
            "skill:hris",
            "HRIS",
            ENTITY_TYPE_SKILL_DOMAIN,
            "skills",
            "proposed_from_onet",
            "approved",
            "discriminant_external_skill",
            "matching_core",
            "standard",
            '{"aliases": ["human resources information systems"], "parents": []}',
            "hash",
            "2026-01-01T00:00:00Z",
        ),
    )
    conn.commit()
    conn.close()

    master = _build_master_store(_make_store(), db_path)
    entity = master.get("skill:hris")
    assert entity is not None
    assert entity.type == ENTITY_TYPE_SKILL_DOMAIN
    assert entity.status == "proposed_from_onet"
    assert entity.metadata["review_status"] == "approved"
    assert entity.metadata["cluster_name"] == "FINANCE_BUSINESS_OPERATIONS"
