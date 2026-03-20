"""
weighted_store.py — Loader for canonical_skills_core_weighted.json (contextual weights).

Read-only, deterministic, safe:
  - Does NOT affect canonical mapping.
  - Used only for contextual skill weighting in scoring.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from compass.canonical.canonical_store import normalize_canonical_key

logger = logging.getLogger(__name__)

# ── Path resolution ────────────────────────────────────────────────────────────
_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[5]  # …/elevia-compass
_DEFAULT_WEIGHTED_PATH = _REPO_ROOT / "audit" / "canonical_skills_core_weighted.json"


def _resolve_weighted_path() -> Path:
    env_path = os.getenv("ELEVIA_CANONICAL_WEIGHTED_PATH", "").strip()
    if env_path:
        return Path(env_path)
    return _DEFAULT_WEIGHTED_PATH


_DEFAULT_CONTEXTUAL = {
    "CORE": 1.2,
    "SECONDARY": 1.0,
    "CONTEXT": 0.8,
}


@dataclass
class WeightedSkillResult:
    canonical_id: Optional[str]
    importance_level: Optional[str]
    weight: float
    affinity_match: bool
    penalties: List[str]


class WeightedCanonicalStore:
    def __init__(self) -> None:
        self.loaded: bool = False
        self.alias_to_id: Dict[str, str] = {}
        self.id_to_skill: Dict[str, dict] = {}
        self.contextual_defaults: Dict[str, float] = dict(_DEFAULT_CONTEXTUAL)
        self.generic_penalties: Dict[str, float] = {}
        self.weighting_source: Optional[str] = None

    def is_loaded(self) -> bool:
        return self.loaded


def map_offer_cluster_to_weighted(cluster: Optional[str]) -> Optional[str]:
    if not cluster:
        return None
    cluster = cluster.strip().upper()
    mapping = {
        "DATA_IT": "DATA_ANALYTICS_AI",
        "MARKETING_SALES": "MARKETING_SALES_GROWTH",
        "FINANCE_LEGAL": "FINANCE_BUSINESS_OPERATIONS",
        "SUPPLY_OPS": "FINANCE_BUSINESS_OPERATIONS",
        "ENGINEERING_INDUSTRY": "ENGINEERING_INDUSTRY",
        "ADMIN_HR": "GENERIC_TRANSVERSAL",
        "OTHER": "GENERIC_TRANSVERSAL",
    }
    return mapping.get(cluster, cluster)


def _build_store(data: dict) -> WeightedCanonicalStore:
    store = WeightedCanonicalStore()

    rules = data.get("matching_engine_rules") or {}
    defaults = rules.get("contextual_weight_defaults") or {}
    if isinstance(defaults, dict):
        for key, value in defaults.items():
            if isinstance(value, (int, float)):
                store.contextual_defaults[str(key).upper()] = float(value)
    store.weighting_source = rules.get("contextual_weighting_source")

    for entry in rules.get("generic_skills_to_downweight") or []:
        if not isinstance(entry, dict):
            continue
        cid = entry.get("canonical_skill_id")
        penalty = entry.get("penalty_weight")
        if cid and isinstance(penalty, (int, float)):
            store.generic_penalties[str(cid)] = float(penalty)

    ontology = data.get("ontology") or []
    for cluster_entry in ontology:
        if not isinstance(cluster_entry, dict):
            continue
        cluster_name = cluster_entry.get("cluster_name")
        for skill in cluster_entry.get("skills") or []:
            if not isinstance(skill, dict):
                continue
            cid = skill.get("canonical_skill_id")
            if not cid:
                continue
            store.id_to_skill[cid] = {**skill, "cluster_name": cluster_name}

            label_key = normalize_canonical_key(str(skill.get("label", "")))
            if label_key and label_key not in store.alias_to_id:
                store.alias_to_id[label_key] = cid

            for alias in skill.get("aliases") or []:
                key = normalize_canonical_key(str(alias))
                if key and key not in store.alias_to_id:
                    store.alias_to_id[key] = cid

    store.loaded = True
    return store


def _load_store() -> WeightedCanonicalStore:
    path = _resolve_weighted_path()
    if not path.exists():
        logger.warning("WEIGHTED_CANONICAL_STORE path_not_found path=%s", path)
        return WeightedCanonicalStore()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.warning("WEIGHTED_CANONICAL_STORE load_failed path=%s error=%s", path, type(exc).__name__)
        return WeightedCanonicalStore()

    store = _build_store(data)
    meta = data.get("ontology_metadata") or {}
    logger.info(
        json.dumps(
            {
                "event": "WEIGHTED_CANONICAL_STORE_VERSION",
                "version": meta.get("version"),
                "path": str(path),
                "aliases_count": len(store.alias_to_id),
                "skills_count": len(store.id_to_skill),
            }
        )
    )
    return store


_store: Optional[WeightedCanonicalStore] = None


def get_weighted_store() -> WeightedCanonicalStore:
    global _store
    if _store is None:
        _store = _load_store()
    return _store


def resolve_weighted_skill(
    label: str,
    offer_cluster: Optional[str],
    *,
    store: WeightedCanonicalStore,
    clamp_min: float,
    clamp_max: float,
) -> WeightedSkillResult:
    if not label or not store.is_loaded():
        return WeightedSkillResult(None, None, 1.0, False, [])

    key = normalize_canonical_key(label)
    canonical_id = store.alias_to_id.get(key)
    if not canonical_id:
        return WeightedSkillResult(None, None, 1.0, False, [])

    skill = store.id_to_skill.get(canonical_id, {})
    importance = str(skill.get("importance_level") or "SECONDARY").upper()
    weight = skill.get("contextual_weight")
    if not isinstance(weight, (int, float)):
        weight = store.contextual_defaults.get(importance, 1.0)

    affinity = skill.get("offer_cluster_affinity") or []
    affinity_match = True
    if offer_cluster and affinity:
        affinity_match = str(offer_cluster) in [str(a) for a in affinity]
        if not affinity_match:
            weight = min(weight, store.contextual_defaults.get("CONTEXT", 0.8))

    penalties: List[str] = []
    penalty = store.generic_penalties.get(canonical_id)
    if isinstance(penalty, (int, float)):
        weight = weight * float(penalty)
        penalties.append("generic_skill_penalty")

    weight = max(clamp_min, min(clamp_max, float(weight)))
    return WeightedSkillResult(canonical_id, importance, weight, affinity_match, penalties)
