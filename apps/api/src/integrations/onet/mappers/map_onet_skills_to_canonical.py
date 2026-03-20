from __future__ import annotations

import hashlib
import json
from typing import Iterable

from compass.canonical.canonical_mapper import map_to_canonical
from compass.canonical.canonical_store import normalize_canonical_key

from ..repository import utc_now


def _hash_payload(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def map_onet_skills_to_canonical(skill_rows: Iterable[dict]) -> tuple[list[dict], list[dict]]:
    mappings: list[dict] = []
    unresolved: list[dict] = []
    now = utc_now()

    for row in skill_rows:
        raw_label = row.get("skill_name") or ""
        if not raw_label:
            continue
        result = map_to_canonical([raw_label])
        mapped = next((m for m in result.mappings if m.canonical_id), None)
        evidence = {
            "raw_label": raw_label,
            "skill_name_norm": normalize_canonical_key(raw_label),
            "source_table": row.get("source_table"),
            "match_candidates": [
                {
                    "canonical_id": m.canonical_id,
                    "label": m.label,
                    "strategy": m.strategy,
                    "confidence": m.confidence,
                }
                for m in result.mappings
            ],
        }
        if mapped:
            payload = {
                "external_skill_id": row["external_skill_id"],
                "canonical_skill_id": mapped.canonical_id,
                "canonical_label": mapped.label,
                "match_method": mapped.strategy,
                "confidence_score": float(mapped.confidence),
                "status": "mapped",
                "evidence_json": json.dumps(evidence, ensure_ascii=False, sort_keys=True),
                "source_hash": _hash_payload({"row": row, "mapped": mapped.canonical_id, "strategy": mapped.strategy}),
                "updated_at": now,
            }
            mappings.append(payload)
        else:
            unresolved.append(
                {
                    "external_skill_id": row["external_skill_id"],
                    "source_table": row["source_table"],
                    "skill_name": raw_label,
                    "skill_name_norm": normalize_canonical_key(raw_label),
                    "reason": "no_canonical_match",
                    "evidence_json": json.dumps(evidence, ensure_ascii=False, sort_keys=True),
                    "status": "unresolved",
                    "source_hash": _hash_payload({"row": row, "reason": "no_canonical_match"}),
                    "updated_at": now,
                }
            )

    return mappings, unresolved
