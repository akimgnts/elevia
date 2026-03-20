from __future__ import annotations

import hashlib
import json
from typing import Any

from compass.canonical.canonical_store import normalize_canonical_key

from ..repository import utc_now


def _row_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def normalize_alt_title_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    now = utc_now()
    for row in rows:
        code = str(row.get("onetsoc_code") or "").strip()
        alt = str(row.get("alternate_title") or row.get("alt_title") or "").strip()
        if not code or not alt:
            continue
        normalized.append(
            {
                "onetsoc_code": code,
                "alt_title": alt,
                "alt_title_norm": normalize_canonical_key(alt),
                "short_title": str(row.get("short_title") or "").strip() or None,
                "sources": str(row.get("sources") or "").strip() or None,
                "source_hash": _row_hash(row),
                "status": "active",
                "updated_at": now,
            }
        )
    return normalized
