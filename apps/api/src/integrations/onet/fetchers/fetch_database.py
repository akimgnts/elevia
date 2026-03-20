from __future__ import annotations

import hashlib
import json
from typing import Any

from ..client import OnetClient
from ..endpoints import ABOUT, DATABASE_LISTING, VERSION_INFO, database_info


def fetch_about(client: OnetClient) -> Any:
    return client.request_json(ABOUT)


def fetch_version_info(client: OnetClient) -> dict[str, Any]:
    payload = client.request_json(VERSION_INFO)
    if not isinstance(payload, dict):
        raise ValueError("about endpoint returned non-object payload")
    return payload


def fetch_database_listing(client: OnetClient) -> list[dict[str, Any]]:
    payload = client.request_json(DATABASE_LISTING)
    if not isinstance(payload, list):
        raise ValueError("database/listing returned non-list payload")
    return payload


def fetch_database_info(client: OnetClient, table_id: str) -> dict[str, Any]:
    payload = client.request_json(database_info(table_id))
    if not isinstance(payload, dict):
        raise ValueError(f"database/info/{table_id} returned non-object payload")
    return payload


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
