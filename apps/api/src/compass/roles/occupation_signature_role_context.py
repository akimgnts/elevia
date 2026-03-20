from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Sequence

from compass.canonical.canonical_store import get_canonical_store
from compass.canonical.master_store import get_master_canonical_store

from .role_family_map import map_onet_occupation_to_role_family


@dataclass(frozen=True)
class RoleContextAnchorGroup:
    label: str
    anchor_skill_ids: frozenset[str]
    min_anchor_matches: int
    required_anchor_ids: frozenset[str] = frozenset()


PHASE1_ROLE_CONTEXT_RULES: dict[str, tuple[RoleContextAnchorGroup, ...]] = {
    "skill:project_management": (
        RoleContextAnchorGroup(
            label="software_delivery",
            anchor_skill_ids=frozenset(
                {
                    "skill:backend_development",
                    "skill:web_service_api",
                    "skill:version_control",
                    "skill:linux_administration",
                }
            ),
            min_anchor_matches=3,
        ),
        RoleContextAnchorGroup(
            label="engineering_delivery",
            anchor_skill_ids=frozenset(
                {
                    "skill:cad_modeling",
                    "skill:industrial_automation",
                    "skill:mechanical_design",
                    "skill:technical_drawing",
                    "skill:root_cause_analysis",
                }
            ),
            min_anchor_matches=3,
        ),
        RoleContextAnchorGroup(
            label="operations_delivery",
            anchor_skill_ids=frozenset(
                {
                    "skill:process_mapping",
                    "skill:operations_management",
                    "skill:supply_chain_management",
                    "skill:vendor_management",
                }
            ),
            min_anchor_matches=3,
        ),
    ),
    "skill:erp_usage": (
        RoleContextAnchorGroup(
            label="enterprise_ops",
            anchor_skill_ids=frozenset(
                {
                    "skill:supply_chain_management",
                    "skill:procurement_basics",
                    "skill:vendor_management",
                    "skill:electronic_data_interchange",
                    "skill:process_mapping",
                }
            ),
            min_anchor_matches=3,
        ),
        RoleContextAnchorGroup(
            label="finance_ops",
            anchor_skill_ids=frozenset(
                {
                    "skill:accounting_basics",
                    "skill:billing_operations",
                    "skill:payroll_administration",
                    "skill:tax_compliance",
                }
            ),
            min_anchor_matches=2,
        ),
    ),
    "skill:operations_management": (
        RoleContextAnchorGroup(
            label="operations_core",
            anchor_skill_ids=frozenset(
                {
                    "skill:process_mapping",
                    "skill:supply_chain_management",
                    "skill:warehouse_operations",
                    "skill:vendor_management",
                    "skill:workforce_scheduling",
                }
            ),
            min_anchor_matches=3,
        ),
        RoleContextAnchorGroup(
            label="administrative_ops",
            anchor_skill_ids=frozenset(
                {
                    "skill:accounting_basics",
                    "skill:billing_operations",
                    "skill:payroll_administration",
                    "skill:workforce_scheduling",
                }
            ),
            min_anchor_matches=2,
        ),
    ),
    "skill:supply_chain_management": (
        RoleContextAnchorGroup(
            label="supply_ops",
            anchor_skill_ids=frozenset(
                {
                    "skill:procurement_basics",
                    "skill:erp_usage",
                    "skill:vendor_management",
                    "skill:warehouse_operations",
                    "skill:electronic_data_interchange",
                    "skill:process_mapping",
                }
            ),
            min_anchor_matches=4,
        ),
    ),
    "skill:procurement_basics": (
        RoleContextAnchorGroup(
            label="procurement_ops",
            anchor_skill_ids=frozenset(
                {
                    "skill:supply_chain_management",
                    "skill:erp_usage",
                    "skill:vendor_management",
                    "skill:electronic_data_interchange",
                    "skill:process_mapping",
                }
            ),
            min_anchor_matches=3,
        ),
        RoleContextAnchorGroup(
            label="procurement_finance",
            anchor_skill_ids=frozenset(
                {
                    "skill:accounting_basics",
                    "skill:billing_operations",
                    "skill:tax_compliance",
                }
            ),
            min_anchor_matches=2,
        ),
    ),
}

PHASE2_ROLE_CONTEXT_RULES: dict[str, tuple[RoleContextAnchorGroup, ...]] = {
    "skill:scripting_automation": (
        RoleContextAnchorGroup(
            label="software_platform",
            anchor_skill_ids=frozenset(
                {
                    "skill:backend_development",
                    "skill:web_service_api",
                    "skill:linux_administration",
                    "skill:cloud_architecture",
                    "skill:containerization",
                }
            ),
            min_anchor_matches=2,
        ),
        RoleContextAnchorGroup(
            label="data_platform",
            anchor_skill_ids=frozenset(
                {
                    "skill:data_engineering",
                    "skill:statistical_programming",
                    "skill:data_modeling",
                    "skill:machine_learning",
                    "skill:business_intelligence",
                }
            ),
            min_anchor_matches=2,
        ),
        RoleContextAnchorGroup(
            label="industrial_controls",
            anchor_skill_ids=frozenset(
                {
                    "skill:cad_modeling",
                    "skill:technical_drawing",
                    "skill:industrial_automation",
                    "skill:mechanical_design",
                    "skill:root_cause_analysis",
                }
            ),
            min_anchor_matches=3,
        ),
    ),
    "skill:linux_administration": (
        RoleContextAnchorGroup(
            label="backend_platform",
            anchor_skill_ids=frozenset(
                {
                    "skill:backend_development",
                    "skill:web_service_api",
                    "skill:cloud_architecture",
                    "skill:containerization",
                }
            ),
            min_anchor_matches=2,
        ),
        RoleContextAnchorGroup(
            label="infra_security",
            anchor_skill_ids=frozenset(
                {
                    "skill:networking_basics",
                    "skill:cybersecurity_basics",
                    "skill:cloud_architecture",
                    "skill:containerization",
                }
            ),
            min_anchor_matches=2,
        ),
        RoleContextAnchorGroup(
            label="data_platform",
            anchor_skill_ids=frozenset(
                {
                    "skill:scripting_automation",
                    "skill:data_engineering",
                    "skill:statistical_programming",
                    "skill:business_intelligence",
                }
            ),
            min_anchor_matches=2,
        ),
    ),
    "skill:workforce_scheduling": (
        RoleContextAnchorGroup(
            label="staffing_operations",
            anchor_skill_ids=frozenset(
                {
                    "skill:operations_management",
                    "skill:dispatch_operations",
                    "skill:warehouse_operations",
                    "skill:supply_chain_management",
                }
            ),
            min_anchor_matches=2,
        ),
        RoleContextAnchorGroup(
            label="staffing_admin",
            anchor_skill_ids=frozenset(
                {
                    "skill:operations_management",
                    "skill:payroll_administration",
                    "skill:accounting_basics",
                    "skill:billing_operations",
                }
            ),
            min_anchor_matches=2,
        ),
    ),
    "skill:statistical_programming": (
        RoleContextAnchorGroup(
            label="advanced_analytics",
            anchor_skill_ids=frozenset(
                {
                    "skill:data_modeling",
                    "skill:machine_learning",
                    "skill:business_intelligence",
                    "skill:data_visualization",
                    "skill:data_engineering",
                }
            ),
            min_anchor_matches=2,
        ),
    ),
    "skill:cad_modeling": (
        RoleContextAnchorGroup(
            label="mechanical_design",
            anchor_skill_ids=frozenset(
                {
                    "skill:mechanical_design",
                    "skill:technical_drawing",
                    "skill:industrial_automation",
                    "skill:computer_aided_manufacturing",
                    "skill:electrical_engineering_basics",
                    "skill:root_cause_analysis",
                }
            ),
            min_anchor_matches=3,
        ),
    ),
}

DOMAIN_REFINEMENT_RULES: dict[str, tuple[RoleContextAnchorGroup, ...]] = {
    "skill:project_management": (
        RoleContextAnchorGroup(
            label="software_delivery_core",
            anchor_skill_ids=frozenset(
                {
                    "skill:backend_development",
                    "skill:web_service_api",
                    "skill:version_control",
                    "skill:cloud_architecture",
                    "skill:linux_administration",
                }
            ),
            min_anchor_matches=3,
            required_anchor_ids=frozenset({"skill:version_control"}),
        ),
        RoleContextAnchorGroup(
            label="engineering_delivery_core",
            anchor_skill_ids=frozenset(
                {
                    "skill:cad_modeling",
                    "skill:mechanical_design",
                    "skill:technical_drawing",
                    "skill:industrial_automation",
                    "skill:root_cause_analysis",
                }
            ),
            min_anchor_matches=3,
            required_anchor_ids=frozenset({"skill:mechanical_design", "skill:technical_drawing"}),
        ),
        RoleContextAnchorGroup(
            label="operations_delivery_core",
            anchor_skill_ids=frozenset(
                {
                    "skill:operations_management",
                    "skill:process_mapping",
                    "skill:vendor_management",
                    "skill:warehouse_operations",
                    "skill:workforce_scheduling",
                }
            ),
            min_anchor_matches=3,
            required_anchor_ids=frozenset({"skill:operations_management"}),
        ),
        RoleContextAnchorGroup(
            label="finance_delivery_core",
            anchor_skill_ids=frozenset(
                {
                    "skill:erp_usage",
                    "skill:accounting_basics",
                    "skill:payroll_administration",
                    "skill:billing_operations",
                    "skill:process_mapping",
                }
            ),
            min_anchor_matches=3,
            required_anchor_ids=frozenset({"skill:erp_usage"}),
        ),
    ),
    "skill:erp_usage": (
        RoleContextAnchorGroup(
            label="enterprise_ops_core",
            anchor_skill_ids=frozenset(
                {
                    "skill:supply_chain_management",
                    "skill:procurement_basics",
                    "skill:vendor_management",
                    "skill:electronic_data_interchange",
                    "skill:warehouse_operations",
                }
            ),
            min_anchor_matches=3,
            required_anchor_ids=frozenset({"skill:vendor_management"}),
        ),
        RoleContextAnchorGroup(
            label="enterprise_ops_management",
            anchor_skill_ids=frozenset(
                {
                    "skill:operations_management",
                    "skill:process_mapping",
                    "skill:vendor_management",
                    "skill:warehouse_operations",
                    "skill:supply_chain_management",
                }
            ),
            min_anchor_matches=3,
            required_anchor_ids=frozenset({"skill:operations_management"}),
        ),
        RoleContextAnchorGroup(
            label="finance_core",
            anchor_skill_ids=frozenset(
                {
                    "skill:accounting_basics",
                    "skill:billing_operations",
                    "skill:payroll_administration",
                    "skill:tax_compliance",
                }
            ),
            min_anchor_matches=2,
            required_anchor_ids=frozenset({"skill:accounting_basics"}),
        ),
    ),
    "skill:operations_management": (
        RoleContextAnchorGroup(
            label="operations_core",
            anchor_skill_ids=frozenset(
                {
                    "skill:workforce_scheduling",
                    "skill:warehouse_operations",
                    "skill:dispatch_operations",
                    "skill:process_mapping",
                    "skill:vendor_management",
                }
            ),
            min_anchor_matches=3,
            required_anchor_ids=frozenset({"skill:workforce_scheduling"}),
        ),
        RoleContextAnchorGroup(
            label="administrative_core",
            anchor_skill_ids=frozenset(
                {
                    "skill:workforce_scheduling",
                    "skill:payroll_administration",
                    "skill:billing_operations",
                    "skill:accounting_basics",
                }
            ),
            min_anchor_matches=3,
            required_anchor_ids=frozenset({"skill:workforce_scheduling"}),
        ),
    ),
    "skill:supply_chain_management": (
        RoleContextAnchorGroup(
            label="supply_execution",
            anchor_skill_ids=frozenset(
                {
                    "skill:warehouse_operations",
                    "skill:vendor_management",
                    "skill:procurement_basics",
                    "skill:electronic_data_interchange",
                    "skill:process_mapping",
                }
            ),
            min_anchor_matches=3,
            required_anchor_ids=frozenset({"skill:warehouse_operations", "skill:vendor_management"}),
        ),
        RoleContextAnchorGroup(
            label="supply_management",
            anchor_skill_ids=frozenset(
                {
                    "skill:operations_management",
                    "skill:vendor_management",
                    "skill:procurement_basics",
                    "skill:electronic_data_interchange",
                    "skill:process_mapping",
                }
            ),
            min_anchor_matches=3,
            required_anchor_ids=frozenset({"skill:operations_management"}),
        ),
    ),
    "skill:procurement_basics": (
        RoleContextAnchorGroup(
            label="procurement_execution",
            anchor_skill_ids=frozenset(
                {
                    "skill:supply_chain_management",
                    "skill:vendor_management",
                    "skill:warehouse_operations",
                    "skill:electronic_data_interchange",
                    "skill:process_mapping",
                }
            ),
            min_anchor_matches=3,
            required_anchor_ids=frozenset({"skill:vendor_management"}),
        ),
        RoleContextAnchorGroup(
            label="procurement_finance",
            anchor_skill_ids=frozenset(
                {
                    "skill:accounting_basics",
                    "skill:billing_operations",
                    "skill:payroll_administration",
                    "skill:tax_compliance",
                    "skill:erp_usage",
                }
            ),
            min_anchor_matches=2,
            required_anchor_ids=frozenset({"skill:accounting_basics"}),
        ),
    ),
}


@dataclass(frozen=True)
class RoleContextRefinementConfig:
    phase1_rules_by_skill: dict[str, tuple[RoleContextAnchorGroup, ...]] | None = None
    phase2_rules_by_skill: dict[str, tuple[RoleContextAnchorGroup, ...]] | None = None
    domain_rules_by_skill: dict[str, tuple[RoleContextAnchorGroup, ...]] | None = None
    enable_phase2: bool = True
    enable_domain_refinement: bool = True

    def phase1_rules(self) -> dict[str, tuple[RoleContextAnchorGroup, ...]]:
        return dict(self.phase1_rules_by_skill or PHASE1_ROLE_CONTEXT_RULES)

    def phase2_rules(self) -> dict[str, tuple[RoleContextAnchorGroup, ...]]:
        return dict(self.phase2_rules_by_skill or PHASE2_ROLE_CONTEXT_RULES)

    def domain_rules(self) -> dict[str, tuple[RoleContextAnchorGroup, ...]]:
        return dict(self.domain_rules_by_skill or DOMAIN_REFINEMENT_RULES)

    def all_rule_skill_ids(self) -> set[str]:
        skill_ids = set(self.phase1_rules()) 
        if self.enable_phase2:
            skill_ids.update(self.phase2_rules())
        if self.enable_domain_refinement:
            skill_ids.update(self.domain_rules())
        return skill_ids


@dataclass(frozen=True)
class BroadSkillStat:
    canonical_skill_id: str
    canonical_label: str
    canonical_type: str
    canonical_cluster: str
    occupation_count: int
    occupation_share: float
    cluster_distribution: dict[str, int]
    cluster_entropy: float
    role_family_distribution: dict[str, int]
    top_cooccurring_skills: list[tuple[str, int]]


@dataclass(frozen=True)
class RoleContextDecision:
    onetsoc_code: str
    canonical_skill_id: str
    phase: str
    retained: bool
    matched_anchor_ids: tuple[str, ...]
    matched_group_labels: tuple[str, ...]


class OccupationSignatureRoleContextRefiner:
    def __init__(self, config: RoleContextRefinementConfig | None = None) -> None:
        self.config = config or RoleContextRefinementConfig()
        self._base_store = get_canonical_store()
        self._master_store = get_master_canonical_store()

    def _canonical_metadata(self, canonical_skill_id: str, fallback_label: str = "") -> tuple[str, str, str]:
        entity = self._master_store.get(canonical_skill_id)
        base_entry = self._base_store.id_to_skill.get(canonical_skill_id, {})
        cluster_name = str(base_entry.get("cluster_name") or "")
        if not cluster_name and entity is not None:
            cluster_name = str(entity.metadata.get("cluster_name") or "")
        label = str((entity.label if entity else "") or fallback_label or canonical_skill_id)
        entity_type = str((entity.type if entity else "") or "unknown")
        return label, entity_type, cluster_name or "UNKNOWN"

    def build_broad_skill_stats(
        self,
        rows: Sequence[dict],
        *,
        total_occupations: int,
        occupation_titles: dict[str, str] | None = None,
        skill_ids: set[str] | None = None,
    ) -> dict[str, BroadSkillStat]:
        if total_occupations <= 0:
            return {}
        target_skill_ids = skill_ids or self.config.all_rule_skill_ids()
        by_occupation: dict[str, set[str]] = defaultdict(set)
        labels: dict[str, str] = {}
        for row in rows:
            onetsoc_code = str(row.get("onetsoc_code") or "")
            canonical_skill_id = str(row.get("canonical_skill_id") or "")
            if not onetsoc_code or not canonical_skill_id:
                continue
            by_occupation[onetsoc_code].add(canonical_skill_id)
            labels.setdefault(canonical_skill_id, str(row.get("canonical_label") or canonical_skill_id))

        stats: dict[str, BroadSkillStat] = {}
        for canonical_skill_id in target_skill_ids:
            occupation_codes = [code for code, skill_ids in by_occupation.items() if canonical_skill_id in skill_ids]
            if not occupation_codes:
                continue
            label, entity_type, cluster_name = self._canonical_metadata(
                canonical_skill_id,
                labels.get(canonical_skill_id, canonical_skill_id),
            )
            role_families: Counter[str] = Counter()
            cooccurring: Counter[str] = Counter()
            cluster_distribution: Counter[str] = Counter()
            for onetsoc_code in occupation_codes:
                title = (occupation_titles or {}).get(onetsoc_code, "")
                role_families[map_onet_occupation_to_role_family(onetsoc_code, title)] += 1
                for other_skill_id in by_occupation[onetsoc_code]:
                    if other_skill_id != canonical_skill_id:
                        cooccurring[other_skill_id] += 1
                        _other_label, _other_type, other_cluster = self._canonical_metadata(other_skill_id, labels.get(other_skill_id, other_skill_id))
                        if other_cluster and other_cluster != "UNKNOWN":
                            cluster_distribution[other_cluster] += 1
            total_cluster_count = sum(cluster_distribution.values())
            cluster_entropy = 0.0
            if total_cluster_count:
                for count in cluster_distribution.values():
                    p = count / total_cluster_count
                    cluster_entropy -= p * math.log2(p)
            stats[canonical_skill_id] = BroadSkillStat(
                canonical_skill_id=canonical_skill_id,
                canonical_label=label,
                canonical_type=entity_type,
                canonical_cluster=cluster_name,
                occupation_count=len(occupation_codes),
                occupation_share=len(occupation_codes) / float(total_occupations),
                cluster_distribution=dict(cluster_distribution),
                cluster_entropy=round(cluster_entropy, 4),
                role_family_distribution=dict(role_families),
                top_cooccurring_skills=cooccurring.most_common(12),
            )
        return stats

    def _apply_rule_set(
        self,
        rows: Sequence[dict],
        *,
        rules: dict[str, tuple[RoleContextAnchorGroup, ...]],
        phase: str,
    ) -> tuple[list[dict], list[RoleContextDecision]]:
        rows_by_occupation: dict[str, list[dict]] = defaultdict(list)
        skill_sets_by_occupation: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            onetsoc_code = str(row.get("onetsoc_code") or "")
            canonical_skill_id = str(row.get("canonical_skill_id") or "")
            if not onetsoc_code:
                continue
            row_copy = dict(row)
            rows_by_occupation[onetsoc_code].append(row_copy)
            if canonical_skill_id:
                skill_sets_by_occupation[onetsoc_code].add(canonical_skill_id)

        refined: list[dict] = []
        decisions: list[RoleContextDecision] = []
        for onetsoc_code in sorted(rows_by_occupation):
            occupation_rows = rows_by_occupation[onetsoc_code]
            occupation_skill_ids = skill_sets_by_occupation[onetsoc_code]
            for row in occupation_rows:
                canonical_skill_id = str(row.get("canonical_skill_id") or "")
                groups = rules.get(canonical_skill_id)
                if not groups:
                    refined.append(row)
                    continue
                matched_anchor_ids: set[str] = set()
                matched_group_labels: list[str] = []
                retained = False
                for group in groups:
                    anchors = sorted((occupation_skill_ids & set(group.anchor_skill_ids)) - {canonical_skill_id})
                    if not set(group.required_anchor_ids).issubset(set(anchors)):
                        continue
                    if len(anchors) >= group.min_anchor_matches:
                        retained = True
                        matched_anchor_ids.update(anchors)
                        matched_group_labels.append(group.label)
                if retained:
                    refined.append(row)
                decisions.append(
                    RoleContextDecision(
                        onetsoc_code=onetsoc_code,
                        canonical_skill_id=canonical_skill_id,
                        phase=phase,
                        retained=retained,
                        matched_anchor_ids=tuple(sorted(matched_anchor_ids)),
                        matched_group_labels=tuple(sorted(matched_group_labels)),
                    )
                )
        return refined, decisions

    def filter_rows(
        self,
        rows: Sequence[dict],
        *,
        return_diagnostics: bool = False,
    ) -> list[dict] | tuple[list[dict], list[RoleContextDecision]]:
        if not rows:
            return ([], []) if return_diagnostics else []
        phase1_rows, phase1_decisions = self._apply_rule_set(
            rows,
            rules=self.config.phase1_rules(),
            phase="phase1",
        )
        refined = phase1_rows
        decisions = list(phase1_decisions)
        if self.config.enable_phase2:
            refined, phase2_decisions = self._apply_rule_set(
                phase1_rows,
                rules=self.config.phase2_rules(),
                phase="phase2",
            )
            decisions.extend(phase2_decisions)
        if self.config.enable_domain_refinement:
            refined, domain_decisions = self._apply_rule_set(
                refined,
                rules=self.config.domain_rules(),
                phase="domain",
            )
            decisions.extend(domain_decisions)
        if return_diagnostics:
            return refined, decisions
        return refined


def refine_occupation_signature_rows(
    rows: Sequence[dict],
    *,
    config: RoleContextRefinementConfig | None = None,
) -> list[dict]:
    return OccupationSignatureRoleContextRefiner(config=config).filter_rows(rows)  # type: ignore[return-value]
