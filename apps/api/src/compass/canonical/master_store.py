from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from .canonical_store import CanonicalStore, get_canonical_store, normalize_canonical_key
from .entity_types import (
    DISPLAY_ANALYTICS_ONLY,
    DISPLAY_STANDARD,
    DISPLAY_RESOLVER_ONLY,
    ENTITY_TYPE_OCCUPATION,
    ENTITY_TYPE_ROLE_FAMILY,
    ENTITY_TYPE_SECTOR,
    ENTITY_TYPE_SKILL_DOMAIN,
    ENTITY_TYPE_SKILL_HUMAN,
    ENTITY_TYPE_SKILL_TECHNICAL,
    ENTITY_TYPE_SKILL_TOOL,
    POLICY_CONTEXT_ONLY,
    STATUS_NATIVE,
    STATUS_PROPOSED_FROM_ONET,
    get_type_usage_policy,
)
from .master_seed import ROLE_FAMILY_DEFINITIONS, SECTOR_DEFINITIONS

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[5]
_DEFAULT_ONET_DB = _REPO_ROOT / "apps" / "api" / "data" / "db" / "onet.db"

_GENERIC_HUMAN_SKILLS = {
    "active listening",
    "communication",
    "written communication",
    "verbal communication",
    "time management",
    "teamwork",
    "leadership",
    "adaptability",
    "coordination",
    "negotiation",
    "stakeholder management",
}

_DOMAIN_HINTS = {
    "analysis",
    "analytics",
    "financial",
    "finance",
    "budget",
    "budgeting",
    "reporting",
    "accounting",
    "marketing",
    "sales",
    "business",
    "project",
    "supply",
    "logistics",
    "procurement",
    "hr",
    "legal",
}

_TECHNICAL_HINTS = {
    "programming",
    "software",
    "data",
    "sql",
    "python",
    "java",
    "cloud",
    "devops",
    "automation",
    "engineering",
    "api",
    "machine learning",
    "debugging",
}

_APPROVED_PROPOSAL_CLUSTER_OVERRIDES = {
    "skill:billing_operations": "FINANCE_BUSINESS_OPERATIONS",
    "skill:computer_aided_manufacturing": "ENGINEERING_INDUSTRY",
    "skill:digital_accessibility": "SOFTWARE_IT",
    "skill:dispatch_operations": "FINANCE_BUSINESS_OPERATIONS",
    "skill:electronic_data_interchange": "FINANCE_BUSINESS_OPERATIONS",
    "skill:health_information_management": "FINANCE_BUSINESS_OPERATIONS",
    "skill:medical_coding": "FINANCE_BUSINESS_OPERATIONS",
    "skill:payroll_administration": "FINANCE_BUSINESS_OPERATIONS",
    "skill:point_of_sale_operations": "MARKETING_SALES_GROWTH",
    "skill:tax_compliance": "FINANCE_BUSINESS_OPERATIONS",
    "skill:workforce_scheduling": "FINANCE_BUSINESS_OPERATIONS",
    "skill:hris": "FINANCE_BUSINESS_OPERATIONS",
}


@dataclass(frozen=True)
class CanonicalSourceRef:
    source_system: str
    source_id: str
    relation: str
    source_label: str = ""


@dataclass
class CanonicalEntity:
    id: str
    label: str
    type: str
    aliases: list[str] = field(default_factory=list)
    parents: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    source_refs: list[CanonicalSourceRef] = field(default_factory=list)
    status: str = STATUS_NATIVE
    match_weight_policy: str = POLICY_CONTEXT_ONLY
    display_policy: str = DISPLAY_STANDARD
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["source_refs"] = [asdict(ref) for ref in self.source_refs]
        return data


class MasterCanonicalStore:
    def __init__(self) -> None:
        self.loaded: bool = False
        self.entities: dict[str, CanonicalEntity] = {}
        self.alias_to_entity_ids: dict[str, list[str]] = {}

    def add_entity(self, entity: CanonicalEntity) -> None:
        self.entities[entity.id] = entity
        for alias in [entity.label, *entity.aliases]:
            key = normalize_canonical_key(alias)
            if not key:
                continue
            bucket = self.alias_to_entity_ids.setdefault(key, [])
            if entity.id not in bucket:
                bucket.append(entity.id)

    def get(self, entity_id: str) -> Optional[CanonicalEntity]:
        return self.entities.get(entity_id)

    def find_by_alias(self, alias: str, *, entity_type: str | None = None) -> list[CanonicalEntity]:
        ids = self.alias_to_entity_ids.get(normalize_canonical_key(alias), [])
        entities = [self.entities[eid] for eid in ids if eid in self.entities]
        if entity_type:
            entities = [entity for entity in entities if entity.type == entity_type]
        return entities

    def list_by_type(self, entity_type: str) -> list[CanonicalEntity]:
        return [entity for entity in self.entities.values() if entity.type == entity_type]


_master_store: Optional[MasterCanonicalStore] = None


def _infer_skill_entity_type(entry: dict[str, object]) -> str:
    label = normalize_canonical_key(str(entry.get("label") or ""))
    concept_type = str(entry.get("concept_type") or "").strip().lower()
    cluster_name = str(entry.get("cluster_name") or "").strip().upper()
    skill_type = str(entry.get("skill_type") or "").strip().lower()

    if concept_type == "tool":
        return ENTITY_TYPE_SKILL_TOOL
    if label in _GENERIC_HUMAN_SKILLS or skill_type == "generic":
        return ENTITY_TYPE_SKILL_HUMAN
    if any(hint in label for hint in _DOMAIN_HINTS) or cluster_name in {"FINANCE_BUSINESS_OPERATIONS", "MARKETING_SALES_GROWTH"}:
        return ENTITY_TYPE_SKILL_DOMAIN
    if any(hint in label for hint in _TECHNICAL_HINTS) or cluster_name in {"DATA_ANALYTICS_AI", "SOFTWARE_IT", "ENGINEERING_INDUSTRY"}:
        return ENTITY_TYPE_SKILL_TECHNICAL
    return ENTITY_TYPE_SKILL_DOMAIN


def _make_seed_entity(*, entity_id: str, label: str, entity_type: str, aliases: list[str], parents: list[str]) -> CanonicalEntity:
    policy = get_type_usage_policy(entity_type)
    return CanonicalEntity(
        id=entity_id,
        label=label,
        type=entity_type,
        aliases=aliases,
        parents=parents,
        source_refs=[CanonicalSourceRef(source_system="elevia_internal", source_id=entity_id, relation="native", source_label=label)],
        status=STATUS_NATIVE,
        match_weight_policy=str(policy["match_weight_policy"]),
        display_policy=str(policy["display_policy"]),
        metadata={"usage": policy["usage"], "seeded": True},
    )


def _load_approved_onet_proposals(onet_db_path: Path) -> list[dict[str, object]]:
    if not onet_db_path.exists():
        return []
    conn = sqlite3.connect(str(onet_db_path))
    conn.row_factory = sqlite3.Row
    try:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='onet_canonical_promotion_candidate'"
        ).fetchone()
        if not exists:
            return []
        rows = conn.execute(
            """
            SELECT proposed_canonical_id, proposed_label, proposed_entity_type,
                   match_weight_policy, display_policy, evidence_json,
                   external_skill_id, source_table, source_hash
            FROM onet_canonical_promotion_candidate
            WHERE review_status = 'approved'
            ORDER BY proposed_canonical_id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _infer_proposal_cluster_name(proposal: dict[str, object], evidence_payload: dict[str, object]) -> str:
    proposed_canonical_id = str(proposal.get("proposed_canonical_id") or "")
    if proposed_canonical_id in _APPROVED_PROPOSAL_CLUSTER_OVERRIDES:
        return _APPROVED_PROPOSAL_CLUSTER_OVERRIDES[proposed_canonical_id]

    label = normalize_canonical_key(str(proposal.get("proposed_label") or ""))
    if any(hint in label for hint in {"marketing", "sales", "lead generation", "crm", "point of sale"}):
        return "MARKETING_SALES_GROWTH"
    if any(hint in label for hint in {"manufacturing", "automation", "cad", "warehouse", "supply", "procurement", "erp"}):
        return "ENGINEERING_INDUSTRY"
    if any(hint in label for hint in {"data", "analytics", "statistical", "business intelligence"}):
        return "DATA_ANALYTICS_AI"
    if any(hint in label for hint in {"cloud", "linux", "cyber", "software", "api", "web", "digital", "accessibility"}):
        return "SOFTWARE_IT"
    if any(hint in label for hint in {"billing", "tax", "payroll", "coding", "documentation", "operations", "dispatch", "scheduling", "finance", "accounting", "medical"}):
        return "FINANCE_BUSINESS_OPERATIONS"

    evidence_cluster = str(evidence_payload.get("cluster_name") or "").strip().upper()
    if evidence_cluster:
        return evidence_cluster
    return "FINANCE_BUSINESS_OPERATIONS"


def _build_master_store(base_store: CanonicalStore, onet_db_path: Path) -> MasterCanonicalStore:
    store = MasterCanonicalStore()

    for sector in SECTOR_DEFINITIONS:
        store.add_entity(
            _make_seed_entity(
                entity_id=f"sector:{sector['key']}",
                label=str(sector["label"]),
                entity_type=ENTITY_TYPE_SECTOR,
                aliases=list(sector.get("aliases") or []),
                parents=[],
            )
        )

    from compass.roles.role_family_map import ROLE_FAMILY_TO_SECTOR  # local import to avoid circular import

    for family in ROLE_FAMILY_DEFINITIONS:
        sector_key = ROLE_FAMILY_TO_SECTOR.get(str(family["key"]), "OTHER")
        store.add_entity(
            _make_seed_entity(
                entity_id=f"role_family:{family['key']}",
                label=str(family["label"]),
                entity_type=ENTITY_TYPE_ROLE_FAMILY,
                aliases=list(family.get("aliases") or []),
                parents=[f"sector:{sector_key}"],
            )
        )

    for canonical_id, entry in base_store.id_to_skill.items():
        entity_type = _infer_skill_entity_type(entry)
        policy = get_type_usage_policy(entity_type)
        aliases = list(dict.fromkeys(str(alias) for alias in entry.get("aliases") or [] if alias))
        parent_id = base_store.hierarchy.get(canonical_id)
        metadata = {
            "skill_type": entry.get("skill_type"),
            "concept_type": entry.get("concept_type"),
            "cluster_name": entry.get("cluster_name"),
            "genericity_score": entry.get("genericity_score"),
            "mapping_confidence": entry.get("mapping_confidence"),
            "status_raw": entry.get("status"),
            "usage": policy["usage"],
        }
        store.add_entity(
            CanonicalEntity(
                id=canonical_id,
                label=str(entry.get("label") or canonical_id),
                type=entity_type,
                aliases=aliases,
                parents=[parent_id] if parent_id else [],
                source_refs=[CanonicalSourceRef(source_system="canonical_core", source_id=canonical_id, relation="native", source_label=str(entry.get("label") or canonical_id))],
                status=STATUS_NATIVE,
                match_weight_policy=str(policy["match_weight_policy"]),
                display_policy=str(policy["display_policy"]),
                metadata=metadata,
            )
        )

    for proposal in _load_approved_onet_proposals(onet_db_path):
        policy = get_type_usage_policy(str(proposal.get("proposed_entity_type") or ENTITY_TYPE_SKILL_DOMAIN))
        evidence = proposal.get("evidence_json")
        try:
            evidence_payload = json.loads(evidence) if isinstance(evidence, str) else {}
        except Exception:
            evidence_payload = {}
        cluster_name = _infer_proposal_cluster_name(proposal, evidence_payload)
        store.add_entity(
            CanonicalEntity(
                id=str(proposal["proposed_canonical_id"]),
                label=str(proposal["proposed_label"]),
                type=str(proposal["proposed_entity_type"]),
                aliases=list(evidence_payload.get("aliases") or []),
                parents=list(evidence_payload.get("parents") or []),
                source_refs=[
                    CanonicalSourceRef(
                        source_system="onet",
                        source_id=str(proposal.get("external_skill_id") or ""),
                        relation="proposal_accepted",
                        source_label=str(proposal.get("source_table") or "onet"),
                    )
                ],
                status=STATUS_PROPOSED_FROM_ONET,
                match_weight_policy=str(proposal.get("match_weight_policy") or policy["match_weight_policy"]),
                display_policy=str(proposal.get("display_policy") or policy["display_policy"]),
                metadata={
                    "usage": policy["usage"],
                    "review_status": "approved",
                    "source_hash": proposal.get("source_hash"),
                    "cluster_name": cluster_name,
                    "evidence": evidence_payload,
                },
            )
        )

    for entity in list(store.entities.values()):
        for parent in entity.parents:
            parent_entity = store.entities.get(parent)
            if parent_entity and entity.id not in parent_entity.children:
                parent_entity.children.append(entity.id)

    store.loaded = True
    return store


def get_master_canonical_store(*, onet_db_path: str | Path | None = None) -> MasterCanonicalStore:
    global _master_store
    if _master_store is None:
        base_store = get_canonical_store()
        db_path = Path(onet_db_path) if onet_db_path is not None else _DEFAULT_ONET_DB
        _master_store = _build_master_store(base_store, db_path)
    return _master_store


def reset_master_canonical_store() -> None:
    global _master_store
    _master_store = None
