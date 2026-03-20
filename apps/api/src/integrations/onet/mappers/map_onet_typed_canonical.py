from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable

from compass.canonical.canonical_mapper import map_to_canonical
from compass.canonical.canonical_store import get_canonical_store, normalize_canonical_key
from compass.canonical.entity_types import (
    DISPLAY_ANALYTICS_ONLY,
    DISPLAY_STANDARD,
    ENTITY_TYPE_SKILL_DOMAIN,
    ENTITY_TYPE_SKILL_HUMAN,
    ENTITY_TYPE_SKILL_TECHNICAL,
    ENTITY_TYPE_SKILL_TOOL,
    POLICY_CONTEXT_ONLY,
    POLICY_MATCHING_CORE,
    POLICY_MATCHING_SECONDARY,
    STATUS_MAPPED_EXISTING,
    STATUS_PROPOSED_FROM_ONET,
    STATUS_REJECTED_NOISE,
    get_type_usage_policy,
)
from compass.canonical.master_store import get_master_canonical_store

from ..repository import utc_now

_GENERIC_REJECT_LABELS = {
    "active listening",
    "time management",
    "coordination",
    "social perceptiveness",
    "speaking",
    "reading comprehension",
    "writing",
    "monitoring",
    "judgment and decision making",
    "judgement and decision making",
    "management of personnel resources",
}

_HUMAN_SKILL_HINTS = {
    "communication",
    "listening",
    "negotiation",
    "leadership",
    "teamwork",
    "coordination",
    "adaptability",
    "time management",
}

_DOMAIN_HINTS = {
    "financial",
    "budget",
    "budgeting",
    "reporting",
    "accounting",
    "controlling",
    "supply chain",
    "procurement",
    "hris",
    "payroll",
    "project management",
    "business analysis",
}

_TECHNICAL_HINTS = {
    "programming",
    "object oriented",
    "object-oriented",
    "software",
    "automation",
    "engineering",
    "debugging",
    "api",
    "cloud",
    "database",
    "sql",
}

_PROMOTABLE_SKILL_HINTS = {
    "object oriented",
    "object-oriented",
    "programming",
    "software",
    "debugging",
    "automation",
    "financial controlling",
    "financial reporting",
    "budgeting",
    "forecasting",
    "supply chain planning",
    "procurement",
    "hris",
    "payroll",
    "business intelligence",
    "data visualization",
}

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _hash_payload(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _make_skill_id(label: str) -> str:
    slug = _SLUG_RE.sub("_", normalize_canonical_key(label)).strip("_")
    return f"skill:{slug}" if slug else "skill:unknown_candidate"


def _infer_entity_type(row: dict, label_norm: str) -> str:
    source_table = str(row.get("source_table") or "")
    if source_table in {"technology_skills", "tools_used"}:
        return ENTITY_TYPE_SKILL_TOOL
    if label_norm in _GENERIC_REJECT_LABELS or any(hint in label_norm for hint in _HUMAN_SKILL_HINTS):
        return ENTITY_TYPE_SKILL_HUMAN
    if any(hint in label_norm for hint in _TECHNICAL_HINTS):
        return ENTITY_TYPE_SKILL_TECHNICAL
    if any(hint in label_norm for hint in _DOMAIN_HINTS):
        return ENTITY_TYPE_SKILL_DOMAIN
    return ENTITY_TYPE_SKILL_DOMAIN


def _should_reject_noise(row: dict, label_norm: str) -> tuple[bool, str]:
    source_table = str(row.get("source_table") or "")
    if not label_norm:
        return True, "empty_label"
    if label_norm in _GENERIC_REJECT_LABELS:
        return True, "generic_non_discriminant_skill"
    if any(hint in label_norm for hint in _HUMAN_SKILL_HINTS):
        return True, "human_skill_out_of_matching_scope"
    if source_table == "skills" and not any(hint in label_norm for hint in _PROMOTABLE_SKILL_HINTS):
        return True, "low_signal_onet_skill"
    if len(label_norm.split()) == 1 and label_norm in {"management", "operations", "analysis"}:
        return True, "over_generic_label"
    return False, ""


def classify_onet_skills_for_typed_canonical(skill_rows: Iterable[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    mappings: list[dict] = []
    proposals: list[dict] = []
    rejected: list[dict] = []
    now = utc_now()
    master_store = get_master_canonical_store()
    base_store = get_canonical_store()

    for row in skill_rows:
        raw_label = row.get("skill_name") or ""
        if not raw_label:
            continue
        label_norm = normalize_canonical_key(raw_label)
        result = map_to_canonical([raw_label], store=base_store)
        mapped = next((m for m in result.mappings if m.canonical_id), None)
        evidence = {
            "raw_label": raw_label,
            "skill_name_norm": label_norm,
            "source_table": row.get("source_table"),
            "source_key": row.get("source_key"),
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
            entity = master_store.get(mapped.canonical_id)
            payload = {
                "external_skill_id": row["external_skill_id"],
                "canonical_skill_id": mapped.canonical_id,
                "canonical_label": mapped.label,
                "match_method": mapped.strategy,
                "confidence_score": float(mapped.confidence),
                "status": STATUS_MAPPED_EXISTING,
                "evidence_json": json.dumps({**evidence, "entity_type": entity.type if entity else None}, ensure_ascii=False, sort_keys=True),
                "source_hash": _hash_payload({"row": row, "mapped": mapped.canonical_id, "strategy": mapped.strategy}),
                "updated_at": now,
            }
            mappings.append(payload)
            continue

        reject, reason = _should_reject_noise(row, label_norm)
        entity_type = _infer_entity_type(row, label_norm)
        policy = get_type_usage_policy(entity_type)
        if reject:
            rejected.append(
                {
                    "external_skill_id": row["external_skill_id"],
                    "source_table": row["source_table"],
                    "skill_name": raw_label,
                    "skill_name_norm": label_norm,
                    "reason": reason,
                    "evidence_json": json.dumps({**evidence, "entity_type": entity_type}, ensure_ascii=False, sort_keys=True),
                    "status": STATUS_REJECTED_NOISE,
                    "source_hash": _hash_payload({"row": row, "reason": reason}),
                    "updated_at": now,
                }
            )
            continue

        proposed_id = _make_skill_id(raw_label)
        aliases = []
        if label_norm != normalize_canonical_key(proposed_id.removeprefix("skill:").replace("_", " ")):
            aliases.append(raw_label)
        proposals.append(
            {
                "external_skill_id": row["external_skill_id"],
                "proposed_canonical_id": proposed_id,
                "proposed_label": raw_label.strip(),
                "proposed_entity_type": entity_type,
                "source_table": row["source_table"],
                "status": STATUS_PROPOSED_FROM_ONET,
                "review_status": "pending",
                "reason": "discriminant_external_skill",
                "match_weight_policy": str(policy["match_weight_policy"]),
                "display_policy": str(policy["display_policy"]),
                "evidence_json": json.dumps(
                    {
                        **evidence,
                        "entity_type": entity_type,
                        "aliases": aliases,
                        "parents": [],
                        "usage": policy["usage"],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "source_hash": _hash_payload({"row": row, "proposal": proposed_id, "entity_type": entity_type}),
                "updated_at": now,
            }
        )

    return mappings, proposals, rejected
