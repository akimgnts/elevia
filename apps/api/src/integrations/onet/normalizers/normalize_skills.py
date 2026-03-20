from __future__ import annotations

import hashlib
import json
from typing import Any

from compass.canonical.canonical_store import normalize_canonical_key

from ..repository import utc_now


def _row_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def normalize_skill_rows(rows: list[dict[str, Any]], *, source_table: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now = utc_now()
    skills: dict[str, dict[str, Any]] = {}
    links: list[dict[str, Any]] = []

    for row in rows:
        code = str(row.get("onetsoc_code") or "").strip()
        element_id = str(row.get("element_id") or "").strip()
        name = str(row.get("element_name") or "").strip()
        scale_name = str(row.get("scale_name") or "").strip() or "unknown"
        if not code or not element_id or not name:
            continue
        external_skill_id = f"{source_table}:{element_id}"
        skills[external_skill_id] = {
            "external_skill_id": external_skill_id,
            "source_table": source_table,
            "source_key": element_id,
            "skill_name": name,
            "skill_name_norm": normalize_canonical_key(name),
            "content_element_id": element_id,
            "commodity_code": None,
            "commodity_title": None,
            "scale_id": str(row.get("scale_id") or "").strip() or None,
            "scale_name": scale_name,
            "source_hash": _row_hash({"source_table": source_table, "element_id": element_id, "element_name": name}),
            "status": "active",
            "updated_at": now,
        }
        links.append(
            {
                "onetsoc_code": code,
                "external_skill_id": external_skill_id,
                "scale_name": scale_name,
                "data_value": row.get("data_value"),
                "n": row.get("n"),
                "recommend_suppress": row.get("recommend_suppress"),
                "not_relevant": row.get("not_relevant"),
                "domain_source": row.get("domain_source"),
                "source_hash": _row_hash(row),
                "status": "active",
                "updated_at": now,
            }
        )
    return list(skills.values()), links


def normalize_technology_skill_rows(rows: list[dict[str, Any]], *, source_table: str = "technology_skills") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now = utc_now()
    skills: dict[str, dict[str, Any]] = {}
    links: list[dict[str, Any]] = []
    for row in rows:
        code = str(row.get("onetsoc_code") or "").strip()
        label = str(row.get("example") or "").strip()
        if not code or not label:
            continue
        commodity_code = str(row.get("commodity_code") or "").strip() or None
        source_key = commodity_code or normalize_canonical_key(label)
        external_skill_id = f"{source_table}:{source_key}"
        skills[external_skill_id] = {
            "external_skill_id": external_skill_id,
            "source_table": source_table,
            "source_key": source_key,
            "skill_name": label,
            "skill_name_norm": normalize_canonical_key(label),
            "content_element_id": None,
            "commodity_code": commodity_code,
            "commodity_title": str(row.get("commodity_title") or "").strip() or None,
            "scale_id": None,
            "scale_name": None,
            "source_hash": _row_hash({"source_table": source_table, "source_key": source_key, "label": label}),
            "status": "active",
            "updated_at": now,
        }
        links.append(
            {
                "onetsoc_code": code,
                "external_skill_id": external_skill_id,
                "technology_label": label,
                "technology_label_norm": normalize_canonical_key(label),
                "commodity_code": commodity_code,
                "commodity_title": str(row.get("commodity_title") or "").strip() or None,
                "hot_technology": row.get("hot_technology"),
                "in_demand": row.get("in_demand"),
                "source_hash": _row_hash(row),
                "status": "active",
                "updated_at": now,
            }
        )
    return list(skills.values()), links


def normalize_tool_rows(rows: list[dict[str, Any]], *, source_table: str = "tools_used") -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    now = utc_now()
    skills: dict[str, dict[str, Any]] = {}
    links: list[dict[str, Any]] = []
    for row in rows:
        code = str(row.get("onetsoc_code") or "").strip()
        label = str(row.get("example") or "").strip()
        if not code or not label:
            continue
        commodity_code = str(row.get("commodity_code") or "").strip() or None
        source_key = commodity_code or normalize_canonical_key(label)
        external_skill_id = f"{source_table}:{source_key}"
        skills[external_skill_id] = {
            "external_skill_id": external_skill_id,
            "source_table": source_table,
            "source_key": source_key,
            "skill_name": label,
            "skill_name_norm": normalize_canonical_key(label),
            "content_element_id": None,
            "commodity_code": commodity_code,
            "commodity_title": str(row.get("commodity_title") or "").strip() or None,
            "scale_id": None,
            "scale_name": None,
            "source_hash": _row_hash({"source_table": source_table, "source_key": source_key, "label": label}),
            "status": "active",
            "updated_at": now,
        }
        links.append(
            {
                "onetsoc_code": code,
                "external_skill_id": external_skill_id,
                "tool_label": label,
                "tool_label_norm": normalize_canonical_key(label),
                "commodity_code": commodity_code,
                "commodity_title": str(row.get("commodity_title") or "").strip() or None,
                "source_hash": _row_hash(row),
                "status": "active",
                "updated_at": now,
            }
        )
    return list(skills.values()), links
