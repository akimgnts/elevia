from __future__ import annotations

from typing import Any, Callable

from api.utils.obs_logger import obs_log

from ..client import OnetClient
from ..config import OnetConfig
from ..fetchers.fetch_database import (
    fetch_about,
    fetch_database_info,
    fetch_database_listing,
    fetch_version_info,
    stable_hash,
)
from ..mappers.map_onet_typed_canonical import classify_onet_skills_for_typed_canonical
from ..normalizers.normalize_alt_titles import normalize_alt_title_rows
from ..normalizers.normalize_occupations import normalize_occupation_rows
from ..normalizers.normalize_skills import (
    normalize_skill_rows,
    normalize_technology_skill_rows,
    normalize_tool_rows,
)
from ..repository import OnetRepository
from ..storage.raw_store import OnetRawStore


class OnetSyncRunner:
    def __init__(self, config: OnetConfig):
        self.config = config
        self.repo = OnetRepository(config.db_path)
        self.raw_store = OnetRawStore(config.raw_root)
        self.client = OnetClient(config)

    def bootstrap(self) -> None:
        self.repo.ensure_schema()

    def run_discovery(self) -> str:
        self.bootstrap()
        version_info = fetch_version_info(self.client)
        api_version = version_info.get("api_version") or version_info.get("api")
        database = version_info.get("database") if isinstance(version_info.get("database"), dict) else {}
        db_name = database.get("name") if isinstance(database, dict) else None
        db_url = database.get("url") if isinstance(database, dict) else None
        version_hash = stable_hash(version_info)
        self.repo.record_source_version(
            source_system="onet",
            api_version=str(api_version) if api_version is not None else None,
            database_version_name=str(db_name) if db_name is not None else None,
            database_version_url=str(db_url) if db_url is not None else None,
            raw_payload_hash=version_hash,
        )
        run_id = self.repo.create_run(
            source_system="onet",
            trigger_type="cli",
            source_api_version=str(api_version) if api_version is not None else None,
            source_db_version_name=str(db_name) if db_name is not None else None,
            source_db_version_url=str(db_url) if db_url is not None else None,
            config=self.config.to_safe_dict(),
        )
        try:
            self._sync_single_payload(run_id, resource_name="about", endpoint_path="about", payload=fetch_about(self.client))
            listing = self._sync_single_payload(
                run_id,
                resource_name="database_listing",
                endpoint_path="database",
                payload=fetch_database_listing(self.client),
            )
            self._normalize_listing(listing)
            self.repo.finish_run(run_id, status="published")
            return run_id
        except Exception as exc:
            self.repo.finish_run(run_id, status="failed", error_message=str(exc))
            raise

    def run_table_info(self, table_id: str) -> str:
        self.bootstrap()
        run_id = self.repo.create_run(
            source_system="onet",
            trigger_type="cli",
            source_api_version=None,
            source_db_version_name=None,
            source_db_version_url=None,
            config=self.config.to_safe_dict(),
        )
        resource_name = f"database_info:{table_id}"
        try:
            payload = self._sync_single_payload(
                run_id,
                resource_name=resource_name,
                endpoint_path=f"database/info/{table_id}",
                payload=fetch_database_info(self.client, table_id),
            )
            self._normalize_table_info(table_id, payload)
            self.repo.finish_run(run_id, status="published")
            return run_id
        except Exception as exc:
            self.repo.finish_run(run_id, status="failed", error_message=str(exc))
            raise

    def run_table_rows(self, table_id: str, *, max_pages: int | None = None) -> str:
        self.bootstrap()
        run_id = self.repo.create_run(
            source_system="onet",
            trigger_type="cli",
            source_api_version=None,
            source_db_version_name=None,
            source_db_version_url=None,
            config=self.config.to_safe_dict(),
        )
        resource_name = f"database_rows:{table_id}"
        self._stage_rows_only(run_id, resource_name=resource_name, table_id=table_id, max_pages=max_pages)
        self.repo.finish_run(run_id, status="published")
        return run_id

    def run_sprint_core(self, *, include_tech: bool = False) -> str:
        self.bootstrap()
        version_info = fetch_version_info(self.client)
        api_version = version_info.get("api_version") or version_info.get("api")
        database = version_info.get("database") if isinstance(version_info.get("database"), dict) else {}
        db_name = database.get("name") if isinstance(database, dict) else None
        db_url = database.get("url") if isinstance(database, dict) else None
        run_id = self.repo.create_run(
            source_system="onet",
            trigger_type="cli",
            source_api_version=str(api_version) if api_version is not None else None,
            source_db_version_name=str(db_name) if db_name is not None else None,
            source_db_version_url=str(db_url) if db_url is not None else None,
            config=self.config.to_safe_dict(),
        )
        try:
            self._sync_dataset(
                run_id,
                table_id="occupation_data",
                normalizer=lambda rows: self.repo.upsert_occupations(
                    normalize_occupation_rows(rows, source_db_version_name=str(db_name) if db_name else None)
                ),
            )
            self._sync_dataset(
                run_id,
                table_id="alternate_titles",
                normalizer=lambda rows: self.repo.upsert_alt_titles(normalize_alt_title_rows(rows)),
            )
            self._sync_dataset(
                run_id,
                table_id="skills",
                normalizer=self._normalize_skills_page,
            )
            if include_tech:
                self._sync_dataset(run_id, table_id="technology_skills", normalizer=self._normalize_technology_page)
                self._sync_dataset(run_id, table_id="tools_used", normalizer=self._normalize_tools_page)
            mapped = self._map_all_skills(run_id, include_tech=include_tech)
            self.repo.finish_run(run_id, status="published")
            obs_log("onet_sprint_core", status="success", extra={"run_id": run_id, "include_tech": include_tech, "mapped_rows": mapped})
            return run_id
        except Exception as exc:
            self.repo.finish_run(run_id, status="failed", error_message=str(exc))
            raise

    def _stage_rows_only(self, run_id: str, *, resource_name: str, table_id: str, max_pages: int | None = None) -> None:
        self.repo.start_resource(run_id, resource_name=resource_name, endpoint_path=f"database/rows/{table_id}", next_start=1)
        try:
            pages = 0
            rows_seen = 0
            for page in self.client.paginate_rows(table_id, max_pages=max_pages):
                refs = self.raw_store.write_payload(
                    run_id=run_id,
                    resource_name=resource_name,
                    payload=page.payload,
                    page_start=page.start,
                    page_end=page.end,
                )
                self.repo.record_raw_payload(
                    run_id=run_id,
                    resource_name=resource_name,
                    page_start=page.start,
                    page_end=page.end,
                    source_id=table_id,
                    payload_sha256=refs["payload_sha256"],
                    storage_path=refs["storage_path"],
                    http_status=200,
                    processing_status="staged",
                )
                self.repo.update_resource_progress(
                    run_id,
                    resource_name=resource_name,
                    pages_delta=1,
                    rows_seen_delta=len(page.rows),
                    rows_staged_delta=len(page.rows),
                    next_start=page.end + 1,
                    last_end=page.end,
                )
                pages += 1
                rows_seen += len(page.rows)
            self.repo.finish_resource(run_id, resource_name=resource_name, status="staged")
            obs_log("onet_table_rows_sync", status="success", extra={"run_id": run_id, "table_id": table_id, "pages": pages, "rows_seen": rows_seen})
        except Exception as exc:
            self.repo.fail_resource(run_id, resource_name=resource_name, error_code=type(exc).__name__, error_message=str(exc))
            raise

    def _sync_dataset(self, run_id: str, *, table_id: str, normalizer: Callable[[list[dict[str, Any]]], int]) -> None:
        info_payload = self._sync_single_payload(
            run_id,
            resource_name=f"database_info:{table_id}",
            endpoint_path=f"database/info/{table_id}",
            payload=fetch_database_info(self.client, table_id),
        )
        self._normalize_table_info(table_id, info_payload)

        resource_name = f"database_rows:{table_id}"
        self.repo.start_resource(run_id, resource_name=resource_name, endpoint_path=f"database/rows/{table_id}", next_start=1)
        try:
            for page in self.client.paginate_rows(table_id):
                refs = self.raw_store.write_payload(
                    run_id=run_id,
                    resource_name=resource_name,
                    payload=page.payload,
                    page_start=page.start,
                    page_end=page.end,
                )
                self.repo.record_raw_payload(
                    run_id=run_id,
                    resource_name=resource_name,
                    page_start=page.start,
                    page_end=page.end,
                    source_id=table_id,
                    payload_sha256=refs["payload_sha256"],
                    storage_path=refs["storage_path"],
                    http_status=200,
                    processing_status="staged",
                )
                normalized_count = normalizer(page.rows)
                self.repo.update_resource_progress(
                    run_id,
                    resource_name=resource_name,
                    pages_delta=1,
                    rows_seen_delta=len(page.rows),
                    rows_staged_delta=len(page.rows),
                    rows_normalized_delta=normalized_count,
                    next_start=page.end + 1,
                    last_end=page.end,
                )
            self.repo.finish_resource(run_id, resource_name=resource_name, status="normalized")
        except Exception as exc:
            self.repo.fail_resource(run_id, resource_name=resource_name, error_code=type(exc).__name__, error_message=str(exc))
            raise

    def _normalize_skills_page(self, rows: list[dict[str, Any]]) -> int:
        skill_rows, link_rows = normalize_skill_rows(rows, source_table="skills")
        self.repo.upsert_skills(skill_rows)
        self.repo.upsert_occupation_skills(link_rows)
        return len(link_rows)

    def _normalize_technology_page(self, rows: list[dict[str, Any]]) -> int:
        skill_rows, link_rows = normalize_technology_skill_rows(rows)
        self.repo.upsert_skills(skill_rows)
        self.repo.upsert_occupation_technology_skills(link_rows)
        return len(link_rows)

    def _normalize_tools_page(self, rows: list[dict[str, Any]]) -> int:
        skill_rows, link_rows = normalize_tool_rows(rows)
        self.repo.upsert_skills(skill_rows)
        self.repo.upsert_occupation_tools(link_rows)
        return len(link_rows)

    def _map_all_skills(self, run_id: str, *, include_tech: bool) -> int:
        source_tables = ["skills"]
        if include_tech:
            source_tables.extend(["technology_skills", "tools_used"])
        skills = [dict(row) for row in self.repo.list_skills_for_mapping(source_tables=source_tables)]
        mappings, proposals, rejected = classify_onet_skills_for_typed_canonical(skills)
        mapped_count, proposed_count, rejected_count = self.repo.replace_typed_skill_mapping_outcomes(
            mappings,
            proposals,
            rejected,
        )
        self.repo.update_resource_progress(
            run_id,
            resource_name="database_rows:skills",
            rows_mapped_delta=mapped_count,
            next_start=None,
            last_end=None,
        )
        obs_log(
            "onet_skill_mapping",
            status="success",
            extra={
                "run_id": run_id,
                "mapped_count": mapped_count,
                "proposed_count": proposed_count,
                "rejected_count": rejected_count,
                "include_tech": include_tech,
            },
        )
        return mapped_count

    def _sync_single_payload(self, run_id: str, *, resource_name: str, endpoint_path: str, payload: Any) -> Any:
        self.repo.start_resource(run_id, resource_name=resource_name, endpoint_path=endpoint_path)
        refs = self.raw_store.write_payload(run_id=run_id, resource_name=resource_name, payload=payload)
        self.repo.record_raw_payload(
            run_id=run_id,
            resource_name=resource_name,
            page_start=None,
            page_end=None,
            source_id=None,
            payload_sha256=refs["payload_sha256"],
            storage_path=refs["storage_path"],
            http_status=200,
            processing_status="staged",
        )
        self.repo.update_resource_progress(
            run_id,
            resource_name=resource_name,
            pages_delta=1,
            rows_seen_delta=1,
            rows_staged_delta=1,
            next_start=None,
            last_end=None,
        )
        self.repo.finish_resource(run_id, resource_name=resource_name, status="staged")
        return payload

    def _normalize_listing(self, payload: Any) -> None:
        if isinstance(payload, list):
            tables = payload
        elif isinstance(payload, dict):
            tables = payload.get("database") or payload.get("tables") or []
        else:
            return
        if not isinstance(tables, list):
            return
        for table in tables:
            table_id = str(table.get("table_id") or table.get("name") or table.get("id") or "").strip()
            if not table_id:
                continue
            self.repo.upsert_database_table(
                table_id=table_id,
                table_name=table.get("title") or table.get("name"),
                category=table.get("category"),
                description=table.get("description"),
                row_count=table.get("rows") if isinstance(table.get("rows"), int) else None,
                source_hash=stable_hash(table),
            )

    def _normalize_table_info(self, table_id: str, payload: dict[str, Any]) -> None:
        self.repo.upsert_database_table(
            table_id=table_id,
            table_name=payload.get("name") or payload.get("title") or table_id,
            category=payload.get("category"),
            description=payload.get("description"),
            row_count=payload.get("total") if isinstance(payload.get("total"), int) else None,
            source_hash=stable_hash(payload),
        )
        columns = payload.get("column") or payload.get("columns") or payload.get("fields") or []
        if isinstance(columns, list):
            self.repo.replace_database_columns(table_id=table_id, columns=columns, source_hash=stable_hash({"table_id": table_id, "columns": columns}))
