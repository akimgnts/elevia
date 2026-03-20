from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from compass.roles.occupation_signature_calibration import calibrate_occupation_signature_rows
from compass.roles.occupation_signature_filter import filter_occupation_signature_rows
from compass.roles.occupation_signature_role_context import (
    RoleContextRefinementConfig,
    refine_occupation_signature_rows,
)

from .schema import SCHEMA_SQL


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class OnetRepository:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            self._ensure_column(conn, "ingestion_run", "source_db_version_name", "TEXT")
            self._ensure_column(conn, "ingestion_run", "source_db_version_url", "TEXT")
            self._ensure_column(conn, "ingestion_resource", "rows_normalized", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "ingestion_resource", "rows_mapped", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "source_version", "database_version_name", "TEXT")
            self._ensure_column(conn, "source_version", "database_version_url", "TEXT")
            self._ensure_column(conn, "onet_canonical_promotion_candidate", "promotion_score", "REAL")
            self._ensure_column(conn, "onet_canonical_promotion_candidate", "promotion_tier", "TEXT")
            self._ensure_column(conn, "onet_canonical_promotion_candidate", "triage_reason", "TEXT")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_onet_promotion_tier ON onet_canonical_promotion_candidate(promotion_tier)"
            )
            self._sanitize_existing_config_rows(conn)
            conn.commit()

    def create_run(
        self,
        *,
        source_system: str,
        trigger_type: str,
        source_api_version: str | None,
        source_db_version_name: str | None,
        source_db_version_url: str | None,
        config: Any,
    ) -> str:
        run_id = str(uuid.uuid4())
        config_json = self._to_json(config)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO ingestion_run (
                    run_id, source_system, started_at, status, trigger_type,
                    source_api_version, source_db_version, source_db_version_name,
                    source_db_version_url, config_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    source_system,
                    utc_now(),
                    "running",
                    trigger_type,
                    source_api_version,
                    source_db_version_name,
                    source_db_version_name,
                    source_db_version_url,
                    config_json,
                ),
            )
            conn.commit()
        return run_id

    def finish_run(self, run_id: str, *, status: str, error_message: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE ingestion_run SET status=?, finished_at=?, error_message=? WHERE run_id=?",
                (status, utc_now(), error_message, run_id),
            )
            conn.commit()

    def record_source_version(
        self,
        *,
        source_system: str,
        api_version: str | None,
        database_version_name: str | None,
        database_version_url: str | None,
        raw_payload_hash: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO source_version (
                    source_system, api_version, database_version, database_version_name,
                    database_version_url, recorded_at, raw_payload_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_system,
                    api_version,
                    database_version_name,
                    database_version_name,
                    database_version_url,
                    utc_now(),
                    raw_payload_hash,
                ),
            )
            conn.commit()

    def start_resource(self, run_id: str, *, resource_name: str, endpoint_path: str, next_start: int | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO ingestion_resource (
                    run_id, resource_name, endpoint_path, status, started_at, next_start
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, resource_name) DO UPDATE SET
                    endpoint_path=excluded.endpoint_path,
                    status=excluded.status,
                    started_at=excluded.started_at,
                    next_start=excluded.next_start,
                    error_code=NULL,
                    error_message=NULL
                """,
                (run_id, resource_name, endpoint_path, "running", utc_now(), next_start),
            )
            conn.commit()

    def update_resource_progress(
        self,
        run_id: str,
        *,
        resource_name: str,
        pages_delta: int = 0,
        rows_seen_delta: int = 0,
        rows_staged_delta: int = 0,
        rows_normalized_delta: int = 0,
        rows_mapped_delta: int = 0,
        next_start: int | None,
        last_end: int | None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE ingestion_resource
                SET pages_fetched = pages_fetched + ?,
                    rows_seen = rows_seen + ?,
                    rows_staged = rows_staged + ?,
                    rows_normalized = rows_normalized + ?,
                    rows_mapped = rows_mapped + ?,
                    next_start = ?,
                    last_end = ?
                WHERE run_id = ? AND resource_name = ?
                """,
                (
                    pages_delta,
                    rows_seen_delta,
                    rows_staged_delta,
                    rows_normalized_delta,
                    rows_mapped_delta,
                    next_start,
                    last_end,
                    run_id,
                    resource_name,
                ),
            )
            conn.commit()

    def finish_resource(self, run_id: str, *, resource_name: str, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE ingestion_resource SET status=?, finished_at=? WHERE run_id=? AND resource_name=?",
                (status, utc_now(), run_id, resource_name),
            )
            conn.commit()

    def fail_resource(self, run_id: str, *, resource_name: str, error_code: str, error_message: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE ingestion_resource
                SET status='failed', finished_at=?, error_code=?, error_message=?
                WHERE run_id=? AND resource_name=?
                """,
                (utc_now(), error_code, error_message, run_id, resource_name),
            )
            conn.commit()

    def record_raw_payload(
        self,
        *,
        run_id: str,
        resource_name: str,
        page_start: int | None,
        page_end: int | None,
        source_id: str | None,
        payload_sha256: str,
        storage_path: str,
        http_status: int,
        processing_status: str,
    ) -> None:
        payload_id = str(uuid.uuid4())
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO onet_raw_payload (
                    payload_id, run_id, resource_name, page_start, page_end, source_id,
                    payload_sha256, storage_path, http_status, fetched_at, processing_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload_id,
                    run_id,
                    resource_name,
                    page_start,
                    page_end,
                    source_id,
                    payload_sha256,
                    storage_path,
                    http_status,
                    utc_now(),
                    processing_status,
                ),
            )
            conn.commit()

    def upsert_database_table(
        self,
        *,
        table_id: str,
        table_name: str | None,
        category: str | None,
        description: str | None,
        row_count: int | None,
        source_hash: str,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO onet_database_table (
                    table_id, table_name, category, description, row_count, source_hash, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(table_id) DO UPDATE SET
                    table_name=excluded.table_name,
                    category=excluded.category,
                    description=excluded.description,
                    row_count=excluded.row_count,
                    source_hash=excluded.source_hash,
                    updated_at=excluded.updated_at
                """,
                (table_id, table_name, category, description, row_count, source_hash, utc_now()),
            )
            conn.commit()

    def replace_database_columns(self, *, table_id: str, columns: list[dict[str, Any]], source_hash: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM onet_database_column WHERE table_id = ?", (table_id,))
            for index, column in enumerate(columns, start=1):
                conn.execute(
                    """
                    INSERT INTO onet_database_column (
                        table_id, column_id, column_name, data_type, ordinal_position, source_hash, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        table_id,
                        str(column.get("column_id") or column.get("id") or column.get("name") or index),
                        column.get("title") or column.get("name") or column.get("label"),
                        column.get("type"),
                        index,
                        source_hash,
                        utc_now(),
                    ),
                )
            conn.commit()

    def upsert_occupations(self, rows: Iterable[dict[str, Any]]) -> int:
        data = list(rows)
        if not data:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO onet_occupation (
                    onetsoc_code, title, title_norm, description, source_db_version_name,
                    source_hash, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(onetsoc_code) DO UPDATE SET
                    title=excluded.title,
                    title_norm=excluded.title_norm,
                    description=excluded.description,
                    source_db_version_name=excluded.source_db_version_name,
                    source_hash=excluded.source_hash,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                [
                    (
                        row["onetsoc_code"],
                        row["title"],
                        row["title_norm"],
                        row.get("description"),
                        row.get("source_db_version_name"),
                        row["source_hash"],
                        row["status"],
                        row["updated_at"],
                    )
                    for row in data
                ],
            )
            conn.commit()
        return len(data)

    def upsert_alt_titles(self, rows: Iterable[dict[str, Any]]) -> int:
        data = list(rows)
        if not data:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO onet_occupation_alt_title (
                    onetsoc_code, alt_title, alt_title_norm, short_title, sources,
                    source_hash, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(onetsoc_code, alt_title_norm) DO UPDATE SET
                    alt_title=excluded.alt_title,
                    short_title=excluded.short_title,
                    sources=excluded.sources,
                    source_hash=excluded.source_hash,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                [
                    (
                        row["onetsoc_code"],
                        row["alt_title"],
                        row["alt_title_norm"],
                        row.get("short_title"),
                        row.get("sources"),
                        row["source_hash"],
                        row["status"],
                        row["updated_at"],
                    )
                    for row in data
                ],
            )
            conn.commit()
        return len(data)

    def upsert_skills(self, rows: Iterable[dict[str, Any]]) -> int:
        data = list(rows)
        if not data:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO onet_skill (
                    external_skill_id, source_table, source_key, skill_name, skill_name_norm,
                    content_element_id, commodity_code, commodity_title, scale_id, scale_name,
                    source_hash, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(external_skill_id) DO UPDATE SET
                    source_table=excluded.source_table,
                    source_key=excluded.source_key,
                    skill_name=excluded.skill_name,
                    skill_name_norm=excluded.skill_name_norm,
                    content_element_id=excluded.content_element_id,
                    commodity_code=excluded.commodity_code,
                    commodity_title=excluded.commodity_title,
                    scale_id=excluded.scale_id,
                    scale_name=excluded.scale_name,
                    source_hash=excluded.source_hash,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                [
                    (
                        row["external_skill_id"],
                        row["source_table"],
                        row.get("source_key"),
                        row["skill_name"],
                        row["skill_name_norm"],
                        row.get("content_element_id"),
                        row.get("commodity_code"),
                        row.get("commodity_title"),
                        row.get("scale_id"),
                        row.get("scale_name"),
                        row["source_hash"],
                        row["status"],
                        row["updated_at"],
                    )
                    for row in data
                ],
            )
            conn.commit()
        return len(data)

    def upsert_occupation_skills(self, rows: Iterable[dict[str, Any]]) -> int:
        data = list(rows)
        if not data:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO onet_occupation_skill (
                    onetsoc_code, external_skill_id, scale_name, data_value, n,
                    recommend_suppress, not_relevant, domain_source, source_hash, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(onetsoc_code, external_skill_id, scale_name) DO UPDATE SET
                    data_value=excluded.data_value,
                    n=excluded.n,
                    recommend_suppress=excluded.recommend_suppress,
                    not_relevant=excluded.not_relevant,
                    domain_source=excluded.domain_source,
                    source_hash=excluded.source_hash,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                [
                    (
                        row["onetsoc_code"],
                        row["external_skill_id"],
                        row["scale_name"],
                        row.get("data_value"),
                        row.get("n"),
                        row.get("recommend_suppress"),
                        row.get("not_relevant"),
                        row.get("domain_source"),
                        row["source_hash"],
                        row["status"],
                        row["updated_at"],
                    )
                    for row in data
                ],
            )
            conn.commit()
        return len(data)

    def upsert_occupation_technology_skills(self, rows: Iterable[dict[str, Any]]) -> int:
        data = list(rows)
        if not data:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO onet_occupation_technology_skill (
                    onetsoc_code, external_skill_id, technology_label, technology_label_norm,
                    commodity_code, commodity_title, hot_technology, in_demand,
                    source_hash, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(onetsoc_code, external_skill_id) DO UPDATE SET
                    technology_label=excluded.technology_label,
                    technology_label_norm=excluded.technology_label_norm,
                    commodity_code=excluded.commodity_code,
                    commodity_title=excluded.commodity_title,
                    hot_technology=excluded.hot_technology,
                    in_demand=excluded.in_demand,
                    source_hash=excluded.source_hash,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                [
                    (
                        row["onetsoc_code"],
                        row["external_skill_id"],
                        row["technology_label"],
                        row["technology_label_norm"],
                        row.get("commodity_code"),
                        row.get("commodity_title"),
                        row.get("hot_technology"),
                        row.get("in_demand"),
                        row["source_hash"],
                        row["status"],
                        row["updated_at"],
                    )
                    for row in data
                ],
            )
            conn.commit()
        return len(data)

    def upsert_occupation_tools(self, rows: Iterable[dict[str, Any]]) -> int:
        data = list(rows)
        if not data:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO onet_occupation_tool (
                    onetsoc_code, external_skill_id, tool_label, tool_label_norm,
                    commodity_code, commodity_title, source_hash, status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(onetsoc_code, external_skill_id) DO UPDATE SET
                    tool_label=excluded.tool_label,
                    tool_label_norm=excluded.tool_label_norm,
                    commodity_code=excluded.commodity_code,
                    commodity_title=excluded.commodity_title,
                    source_hash=excluded.source_hash,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                [
                    (
                        row["onetsoc_code"],
                        row["external_skill_id"],
                        row["tool_label"],
                        row["tool_label_norm"],
                        row.get("commodity_code"),
                        row.get("commodity_title"),
                        row["source_hash"],
                        row["status"],
                        row["updated_at"],
                    )
                    for row in data
                ],
            )
            conn.commit()
        return len(data)

    def replace_skill_mappings(self, mappings: Iterable[dict[str, Any]], unresolved: Iterable[dict[str, Any]]) -> tuple[int, int]:
        mapping_rows = list(mappings)
        unresolved_rows = list(unresolved)
        with self.connect() as conn:
            if mapping_rows:
                conn.executemany(
                    """
                    INSERT INTO onet_skill_mapping_to_canonical (
                        external_skill_id, canonical_skill_id, canonical_label, match_method,
                        confidence_score, status, evidence_json, source_hash, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(external_skill_id, canonical_skill_id) DO UPDATE SET
                        canonical_label=excluded.canonical_label,
                        match_method=excluded.match_method,
                        confidence_score=excluded.confidence_score,
                        status=excluded.status,
                        evidence_json=excluded.evidence_json,
                        source_hash=excluded.source_hash,
                        updated_at=excluded.updated_at
                    """,
                    [
                        (
                            row["external_skill_id"],
                            row["canonical_skill_id"],
                            row.get("canonical_label"),
                            row["match_method"],
                            row["confidence_score"],
                            row["status"],
                            row["evidence_json"],
                            row["source_hash"],
                            row["updated_at"],
                        )
                        for row in mapping_rows
                    ],
                )
                conn.executemany(
                    "DELETE FROM onet_unresolved_skill WHERE external_skill_id = ?",
                    [(row["external_skill_id"],) for row in mapping_rows],
                )
            if unresolved_rows:
                conn.executemany(
                    """
                    INSERT INTO onet_unresolved_skill (
                        external_skill_id, source_table, skill_name, skill_name_norm,
                        reason, evidence_json, status, source_hash, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(external_skill_id) DO UPDATE SET
                        source_table=excluded.source_table,
                        skill_name=excluded.skill_name,
                        skill_name_norm=excluded.skill_name_norm,
                        reason=excluded.reason,
                        evidence_json=excluded.evidence_json,
                        status=excluded.status,
                        source_hash=excluded.source_hash,
                        updated_at=excluded.updated_at
                    """,
                    [
                        (
                            row["external_skill_id"],
                            row["source_table"],
                            row["skill_name"],
                            row["skill_name_norm"],
                            row["reason"],
                            row["evidence_json"],
                            row["status"],
                            row["source_hash"],
                            row["updated_at"],
                        )
                        for row in unresolved_rows
                    ],
                )
                conn.executemany(
                    "DELETE FROM onet_skill_mapping_to_canonical WHERE external_skill_id = ?",
                    [(row["external_skill_id"],) for row in unresolved_rows],
                )
            conn.commit()
        return len(mapping_rows), len(unresolved_rows)

    def replace_typed_skill_mapping_outcomes(
        self,
        mappings: Iterable[dict[str, Any]],
        proposals: Iterable[dict[str, Any]],
        rejected: Iterable[dict[str, Any]],
    ) -> tuple[int, int, int]:
        mapping_rows = list(mappings)
        proposal_rows = list(proposals)
        rejected_rows = list(rejected)
        with self.connect() as conn:
            if mapping_rows:
                conn.executemany(
                    """
                    INSERT INTO onet_skill_mapping_to_canonical (
                        external_skill_id, canonical_skill_id, canonical_label, match_method,
                        confidence_score, status, evidence_json, source_hash, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(external_skill_id, canonical_skill_id) DO UPDATE SET
                        canonical_label=excluded.canonical_label,
                        match_method=excluded.match_method,
                        confidence_score=excluded.confidence_score,
                        status=excluded.status,
                        evidence_json=excluded.evidence_json,
                        source_hash=excluded.source_hash,
                        updated_at=excluded.updated_at
                    """,
                    [
                        (
                            row["external_skill_id"],
                            row["canonical_skill_id"],
                            row.get("canonical_label"),
                            row["match_method"],
                            row["confidence_score"],
                            row["status"],
                            row["evidence_json"],
                            row["source_hash"],
                            row["updated_at"],
                        )
                        for row in mapping_rows
                    ],
                )
                conn.executemany(
                    "DELETE FROM onet_unresolved_skill WHERE external_skill_id = ?",
                    [(row["external_skill_id"],) for row in mapping_rows],
                )
                conn.executemany(
                    "DELETE FROM onet_canonical_promotion_candidate WHERE external_skill_id = ?",
                    [(row["external_skill_id"],) for row in mapping_rows],
                )
            if proposal_rows:
                conn.executemany(
                    """
                    INSERT INTO onet_canonical_promotion_candidate (
                        external_skill_id, proposed_canonical_id, proposed_label, proposed_entity_type,
                        source_table, status, review_status, reason, match_weight_policy,
                        display_policy, promotion_score, promotion_tier, triage_reason,
                        evidence_json, source_hash, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(external_skill_id) DO UPDATE SET
                        proposed_canonical_id=excluded.proposed_canonical_id,
                        proposed_label=excluded.proposed_label,
                        proposed_entity_type=excluded.proposed_entity_type,
                        source_table=excluded.source_table,
                        status=excluded.status,
                        review_status=excluded.review_status,
                        reason=excluded.reason,
                        match_weight_policy=excluded.match_weight_policy,
                        display_policy=excluded.display_policy,
                        promotion_score=excluded.promotion_score,
                        promotion_tier=excluded.promotion_tier,
                        triage_reason=excluded.triage_reason,
                        evidence_json=excluded.evidence_json,
                        source_hash=excluded.source_hash,
                        updated_at=excluded.updated_at
                    """,
                    [
                        (
                            row["external_skill_id"],
                            row["proposed_canonical_id"],
                            row["proposed_label"],
                            row["proposed_entity_type"],
                            row["source_table"],
                            row["status"],
                            row["review_status"],
                            row["reason"],
                            row["match_weight_policy"],
                            row["display_policy"],
                            row.get("promotion_score"),
                            row.get("promotion_tier"),
                            row.get("triage_reason"),
                            row["evidence_json"],
                            row["source_hash"],
                            row["updated_at"],
                        )
                        for row in proposal_rows
                    ],
                )
                conn.executemany(
                    "DELETE FROM onet_skill_mapping_to_canonical WHERE external_skill_id = ?",
                    [(row["external_skill_id"],) for row in proposal_rows],
                )
                conn.executemany(
                    "DELETE FROM onet_unresolved_skill WHERE external_skill_id = ?",
                    [(row["external_skill_id"],) for row in proposal_rows],
                )
            if rejected_rows:
                conn.executemany(
                    """
                    INSERT INTO onet_unresolved_skill (
                        external_skill_id, source_table, skill_name, skill_name_norm,
                        reason, evidence_json, status, source_hash, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(external_skill_id) DO UPDATE SET
                        source_table=excluded.source_table,
                        skill_name=excluded.skill_name,
                        skill_name_norm=excluded.skill_name_norm,
                        reason=excluded.reason,
                        evidence_json=excluded.evidence_json,
                        status=excluded.status,
                        source_hash=excluded.source_hash,
                        updated_at=excluded.updated_at
                    """,
                    [
                        (
                            row["external_skill_id"],
                            row["source_table"],
                            row["skill_name"],
                            row["skill_name_norm"],
                            row["reason"],
                            row["evidence_json"],
                            row["status"],
                            row["source_hash"],
                            row["updated_at"],
                        )
                        for row in rejected_rows
                    ],
                )
                conn.executemany(
                    "DELETE FROM onet_skill_mapping_to_canonical WHERE external_skill_id = ?",
                    [(row["external_skill_id"],) for row in rejected_rows],
                )
                conn.executemany(
                    "DELETE FROM onet_canonical_promotion_candidate WHERE external_skill_id = ?",
                    [(row["external_skill_id"],) for row in rejected_rows],
                )
            conn.commit()
        return len(mapping_rows), len(proposal_rows), len(rejected_rows)

    def upsert_skill_mappings(self, mappings: Iterable[dict[str, Any]]) -> int:
        mapping_rows = list(mappings)
        if not mapping_rows:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO onet_skill_mapping_to_canonical (
                    external_skill_id, canonical_skill_id, canonical_label, match_method,
                    confidence_score, status, evidence_json, source_hash, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(external_skill_id, canonical_skill_id) DO UPDATE SET
                    canonical_label=excluded.canonical_label,
                    match_method=excluded.match_method,
                    confidence_score=excluded.confidence_score,
                    status=excluded.status,
                    evidence_json=excluded.evidence_json,
                    source_hash=excluded.source_hash,
                    updated_at=excluded.updated_at
                """,
                [
                    (
                        row["external_skill_id"],
                        row["canonical_skill_id"],
                        row.get("canonical_label"),
                        row["match_method"],
                        row["confidence_score"],
                        row["status"],
                        row["evidence_json"],
                        row["source_hash"],
                        row["updated_at"],
                    )
                    for row in mapping_rows
                ],
            )
            conn.commit()
        return len(mapping_rows)

    def upsert_canonical_promotion_candidates(self, proposals: Iterable[dict[str, Any]]) -> int:
        proposal_rows = list(proposals)
        if not proposal_rows:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """
                INSERT INTO onet_canonical_promotion_candidate (
                    external_skill_id, proposed_canonical_id, proposed_label, proposed_entity_type,
                    source_table, status, review_status, reason, match_weight_policy,
                    display_policy, promotion_score, promotion_tier, triage_reason,
                    evidence_json, source_hash, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(external_skill_id) DO UPDATE SET
                    proposed_canonical_id=excluded.proposed_canonical_id,
                    proposed_label=excluded.proposed_label,
                    proposed_entity_type=excluded.proposed_entity_type,
                    source_table=excluded.source_table,
                    status=excluded.status,
                    review_status=excluded.review_status,
                    reason=excluded.reason,
                    match_weight_policy=excluded.match_weight_policy,
                    display_policy=excluded.display_policy,
                    promotion_score=excluded.promotion_score,
                    promotion_tier=excluded.promotion_tier,
                    triage_reason=excluded.triage_reason,
                    evidence_json=excluded.evidence_json,
                    source_hash=excluded.source_hash,
                    updated_at=excluded.updated_at
                """,
                [
                    (
                        row["external_skill_id"],
                        row["proposed_canonical_id"],
                        row["proposed_label"],
                        row["proposed_entity_type"],
                        row["source_table"],
                        row["status"],
                        row["review_status"],
                        row["reason"],
                        row["match_weight_policy"],
                        row["display_policy"],
                        row.get("promotion_score"),
                        row.get("promotion_tier"),
                        row.get("triage_reason"),
                        row["evidence_json"],
                        row["source_hash"],
                        row["updated_at"],
                    )
                    for row in proposal_rows
                ],
            )
            conn.commit()
        return len(proposal_rows)

    def delete_canonical_promotion_candidates(self, external_skill_ids: Iterable[str]) -> int:
        ids = [str(external_skill_id) for external_skill_id in external_skill_ids if external_skill_id]
        if not ids:
            return 0
        with self.connect() as conn:
            conn.executemany(
                "DELETE FROM onet_canonical_promotion_candidate WHERE external_skill_id = ?",
                [(external_skill_id,) for external_skill_id in ids],
            )
            conn.commit()
        return len(ids)

    def list_skills_for_mapping(self, *, source_tables: list[str] | None = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM onet_skill"
        params: list[Any] = []
        if source_tables:
            placeholders = ",".join("?" for _ in source_tables)
            query += f" WHERE source_table IN ({placeholders})"
            params.extend(source_tables)
        query += " ORDER BY external_skill_id"
        with self.connect() as conn:
            return conn.execute(query, params).fetchall()

    def find_occupations_by_title_norms(self, title_norms: list[str]) -> list[sqlite3.Row]:
        if not title_norms:
            return []
        placeholders = ",".join("?" for _ in title_norms)
        query = f"""
            SELECT onetsoc_code, title, title_norm, 'title' AS match_source
            FROM onet_occupation
            WHERE title_norm IN ({placeholders})
            UNION ALL
            SELECT onetsoc_code, alt_title AS title, alt_title_norm AS title_norm, 'alt_title' AS match_source
            FROM onet_occupation_alt_title
            WHERE alt_title_norm IN ({placeholders})
        """
        params = title_norms + title_norms
        with self.connect() as conn:
            return conn.execute(query, params).fetchall()

    def list_occupation_title_candidates(self) -> list[sqlite3.Row]:
        query = """
            SELECT onetsoc_code, title AS candidate_title, title_norm AS candidate_title_norm, 'title' AS source
            FROM onet_occupation
            UNION ALL
            SELECT onetsoc_code, alt_title AS candidate_title, alt_title_norm AS candidate_title_norm, 'alt_title' AS source
            FROM onet_occupation_alt_title
        """
        with self.connect() as conn:
            return conn.execute(query).fetchall()

    def list_occupations(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT onetsoc_code, title, title_norm, description FROM onet_occupation ORDER BY onetsoc_code"
            ).fetchall()

    def count_occupations(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM onet_occupation").fetchone()
        return int(row[0] if row else 0)

    def _fetch_occupation_mapped_skill_rows(self, *, onetsoc_codes: list[str] | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT DISTINCT
                COALESCE(occ.onetsoc_code, tech.onetsoc_code, tool.onetsoc_code) AS onetsoc_code,
                m.canonical_skill_id,
                m.canonical_label,
                m.confidence_score,
                s.skill_name,
                s.skill_name_norm,
                s.source_table
            FROM onet_skill_mapping_to_canonical m
            JOIN onet_skill s ON s.external_skill_id = m.external_skill_id
            LEFT JOIN onet_occupation_skill occ ON occ.external_skill_id = s.external_skill_id
            LEFT JOIN onet_occupation_technology_skill tech ON tech.external_skill_id = s.external_skill_id
            LEFT JOIN onet_occupation_tool tool ON tool.external_skill_id = s.external_skill_id
            WHERE m.status IN ('mapped', 'mapped_existing')
              AND COALESCE(occ.onetsoc_code, tech.onetsoc_code, tool.onetsoc_code) IS NOT NULL
        """
        params: list[Any] = []
        if onetsoc_codes:
            placeholders = ",".join("?" for _ in onetsoc_codes)
            query += f"""
              AND (
                  occ.onetsoc_code IN ({placeholders}) OR
                  tech.onetsoc_code IN ({placeholders}) OR
                  tool.onetsoc_code IN ({placeholders})
              )
            """
            params.extend(onetsoc_codes)
            params.extend(onetsoc_codes)
            params.extend(onetsoc_codes)
        query += " ORDER BY onetsoc_code ASC, m.confidence_score DESC, m.canonical_skill_id ASC"
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def list_occupation_mapped_skills(
        self,
        *,
        apply_signature_filter: bool = True,
        apply_signature_calibration: bool = True,
        apply_signature_role_context: bool = True,
        apply_signature_role_context_phase2: bool = True,
        apply_signature_domain_refinement: bool = True,
    ) -> list[dict[str, Any]]:
        rows = self._fetch_occupation_mapped_skill_rows()
        if not apply_signature_filter:
            return rows
        total_occupations = self.count_occupations()
        filtered_rows = filter_occupation_signature_rows(rows, total_occupations=total_occupations)
        if not apply_signature_calibration:
            return filtered_rows
        calibrated_rows = calibrate_occupation_signature_rows(filtered_rows, total_occupations=total_occupations)
        if not apply_signature_role_context:
            return calibrated_rows
        return refine_occupation_signature_rows(
            calibrated_rows,
            config=RoleContextRefinementConfig(
                enable_phase2=apply_signature_role_context_phase2,
                enable_domain_refinement=apply_signature_domain_refinement,
            ),
        )

    def get_mapped_canonical_for_occupations(
        self,
        onetsoc_codes: list[str],
        *,
        apply_signature_filter: bool = True,
        apply_signature_calibration: bool = True,
        apply_signature_role_context: bool = True,
        apply_signature_role_context_phase2: bool = True,
        apply_signature_domain_refinement: bool = True,
    ) -> list[dict[str, Any]]:
        if not onetsoc_codes:
            return []
        rows = self._fetch_occupation_mapped_skill_rows(onetsoc_codes=onetsoc_codes)
        if not apply_signature_filter:
            return rows
        total_occupations = self.count_occupations()
        filtered_rows = filter_occupation_signature_rows(rows, total_occupations=total_occupations)
        if not apply_signature_calibration:
            return filtered_rows
        calibrated_rows = calibrate_occupation_signature_rows(filtered_rows, total_occupations=total_occupations)
        if not apply_signature_role_context:
            return calibrated_rows
        return refine_occupation_signature_rows(
            calibrated_rows,
            config=RoleContextRefinementConfig(
                enable_phase2=apply_signature_role_context_phase2,
                enable_domain_refinement=apply_signature_domain_refinement,
            ),
        )

    def list_canonical_promotion_candidates(
        self,
        *,
        review_status: str | None = None,
        promotion_tier: str | None = None,
        top: int | None = None,
    ) -> list[sqlite3.Row]:
        query = "SELECT * FROM onet_canonical_promotion_candidate"
        params: list[Any] = []
        clauses: list[str] = []
        if review_status:
            clauses.append("review_status = ?")
            params.append(review_status)
        if promotion_tier:
            clauses.append("promotion_tier = ?")
            params.append(promotion_tier)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY COALESCE(promotion_score, 0) DESC, proposed_entity_type ASC, proposed_canonical_id ASC"
        if top is not None:
            query += " LIMIT ?"
            params.append(int(top))
        with self.connect() as conn:
            return conn.execute(query, params).fetchall()

    def set_canonical_promotion_review_status(self, external_skill_id: str, *, review_status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE onet_canonical_promotion_candidate SET review_status = ?, updated_at = ? WHERE external_skill_id = ?",
                (review_status, utc_now(), external_skill_id),
            )
            conn.commit()

    def update_canonical_promotion_triage(self, ranked_rows: Iterable[Any]) -> int:
        data = list(ranked_rows)
        if not data:
            return 0
        with self.connect() as conn:
            conn.executemany(
                """
                UPDATE onet_canonical_promotion_candidate
                SET promotion_score = ?,
                    promotion_tier = ?,
                    triage_reason = ?,
                    updated_at = ?
                WHERE external_skill_id = ?
                """,
                [
                    (
                        float(getattr(row, "score")),
                        str(getattr(row, "tier")),
                        str(getattr(row, "triage_reason")),
                        utc_now(),
                        str(getattr(row, "external_skill_id")),
                    )
                    for row in data
                ],
            )
            conn.commit()
        return len(data)

    @staticmethod
    def _to_json(value: Any) -> str:
        if is_dataclass(value):
            value = asdict(value)
        if isinstance(value, dict):
            value = dict(value)
            value.pop("api_key", None)
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_def: str) -> None:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
        if column_name not in existing:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")

    def _sanitize_existing_config_rows(self, conn: sqlite3.Connection) -> None:
        rows = conn.execute("SELECT run_id, config_json FROM ingestion_run WHERE config_json IS NOT NULL").fetchall()
        for run_id, config_json in rows:
            try:
                parsed = json.loads(config_json)
            except Exception:
                continue
            if not isinstance(parsed, dict) or "api_key" not in parsed:
                continue
            parsed.pop("api_key", None)
            conn.execute(
                "UPDATE ingestion_run SET config_json = ? WHERE run_id = ?",
                (json.dumps(parsed, ensure_ascii=False, sort_keys=True, default=str), run_id),
            )
