from __future__ import annotations

import hashlib
import json
from typing import Any

from compass.canonical.canonical_store import normalize_canonical_key

from ..repository import utc_now


def _row_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def normalize_occupation_rows(rows: list[dict[str, Any]], *, source_db_version_name: str | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    now = utc_now()
    for row in rows:
        code = str(row.get("onetsoc_code") or "").strip()
        title = str(row.get("title") or "").strip()
        if not code or not title:
            continue
        normalized.append(
            {
                "onetsoc_code": code,
                "title": title,
                "title_norm": normalize_canonical_key(title),
                "description": str(row.get("description") or "").strip() or None,
                "source_db_version_name": source_db_version_name,
                "source_hash": _row_hash(row),
                "status": "active",
                "updated_at": now,
            }
        )
    return normalized
