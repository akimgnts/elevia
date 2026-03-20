from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Sequence

from compass.canonical.canonical_store import get_canonical_store
from compass.canonical.master_store import get_master_canonical_store


MEDIUM_SIGNAL_ALLOWED_CLUSTERS: dict[str, frozenset[str]] = {
    "skill:project_management": frozenset({"SOFTWARE_IT", "ENGINEERING_INDUSTRY", "FINANCE_BUSINESS_OPERATIONS"}),
    "skill:erp_usage": frozenset({"FINANCE_BUSINESS_OPERATIONS", "ENGINEERING_INDUSTRY"}),
    "skill:linux_administration": frozenset({"SOFTWARE_IT", "DATA_ANALYTICS_AI"}),
    "skill:supply_chain_management": frozenset({"FINANCE_BUSINESS_OPERATIONS", "ENGINEERING_INDUSTRY"}),
    "skill:procurement_basics": frozenset({"FINANCE_BUSINESS_OPERATIONS", "ENGINEERING_INDUSTRY"}),
    "skill:operations_management": frozenset({"FINANCE_BUSINESS_OPERATIONS", "ENGINEERING_INDUSTRY"}),
    "skill:crm_management": frozenset({"MARKETING_SALES_GROWTH", "FINANCE_BUSINESS_OPERATIONS"}),
    "skill:lead_generation": frozenset({"MARKETING_SALES_GROWTH"}),
    "skill:account_management": frozenset({"MARKETING_SALES_GROWTH", "FINANCE_BUSINESS_OPERATIONS"}),
    "skill:b2b_sales": frozenset({"MARKETING_SALES_GROWTH"}),
}


@dataclass(frozen=True)
class OccupationSignatureCalibrationConfig:
    medium_signal_min_share: float = 0.15
    medium_signal_max_share: float = 0.50
    allowed_clusters_by_skill: dict[str, frozenset[str]] | None = None
    min_anchor_cluster_count: int = 2
    min_anchor_cluster_share: float = 0.35

    def cluster_rules(self) -> dict[str, frozenset[str]]:
        return dict(self.allowed_clusters_by_skill or MEDIUM_SIGNAL_ALLOWED_CLUSTERS)


@dataclass(frozen=True)
class MediumSignalSkillStat:
    canonical_skill_id: str
    canonical_label: str
    canonical_type: str
    canonical_cluster: str
    occupation_count: int
    occupation_share: float
    cluster_distribution: dict[str, int]
    cluster_entropy: float


class OccupationSignatureCalibrator:
    def __init__(self, config: OccupationSignatureCalibrationConfig | None = None) -> None:
        self.config = config or OccupationSignatureCalibrationConfig()
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

    def build_medium_signal_stats(
        self,
        rows: Sequence[dict],
        *,
        total_occupations: int,
    ) -> dict[str, MediumSignalSkillStat]:
        if total_occupations <= 0:
            return {}
        occupation_sets: dict[str, set[str]] = defaultdict(set)
        cluster_distribution: dict[str, Counter[str]] = defaultdict(Counter)
        labels: dict[str, str] = {}
        rules = self.config.cluster_rules()

        for row in rows:
            canonical_skill_id = str(row.get("canonical_skill_id") or "")
            if canonical_skill_id not in rules:
                continue
            onetsoc_code = str(row.get("onetsoc_code") or "")
            if not onetsoc_code:
                continue
            occupation_sets[canonical_skill_id].add(onetsoc_code)
            labels.setdefault(canonical_skill_id, str(row.get("canonical_label") or canonical_skill_id))
            occupation_cluster = self._infer_row_cluster(row)
            if occupation_cluster:
                cluster_distribution[canonical_skill_id][occupation_cluster] += 1

        stats: dict[str, MediumSignalSkillStat] = {}
        for canonical_skill_id, allowed_clusters in rules.items():
            occs = occupation_sets.get(canonical_skill_id, set())
            if not occs:
                continue
            label, entity_type, canonical_cluster = self._canonical_metadata(canonical_skill_id, labels.get(canonical_skill_id, ""))
            distribution = dict(cluster_distribution.get(canonical_skill_id, Counter()))
            total = sum(distribution.values())
            entropy = 0.0
            if total:
                for count in distribution.values():
                    p = count / total
                    entropy -= p * math.log2(p)
            stats[canonical_skill_id] = MediumSignalSkillStat(
                canonical_skill_id=canonical_skill_id,
                canonical_label=label,
                canonical_type=entity_type,
                canonical_cluster=canonical_cluster,
                occupation_count=len(occs),
                occupation_share=len(occs) / float(total_occupations),
                cluster_distribution=distribution,
                cluster_entropy=round(entropy, 4),
            )
        return stats

    def filter_rows(
        self,
        rows: Sequence[dict],
        *,
        total_occupations: int,
    ) -> list[dict]:
        if not rows:
            return []
        rules = self.config.cluster_rules()
        stats = self.build_medium_signal_stats(rows, total_occupations=total_occupations)
        medium_signal_ids = {
            canonical_skill_id
            for canonical_skill_id, stat in stats.items()
            if self.config.medium_signal_min_share <= stat.occupation_share <= self.config.medium_signal_max_share
        }
        if not medium_signal_ids:
            return [dict(row) for row in rows]

        rows_by_occupation: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            onetsoc_code = str(row.get("onetsoc_code") or "")
            if onetsoc_code:
                rows_by_occupation[onetsoc_code].append(dict(row))

        calibrated: list[dict] = []
        for onetsoc_code, occupation_rows in rows_by_occupation.items():
            for row in occupation_rows:
                canonical_skill_id = str(row.get("canonical_skill_id") or "")
                if canonical_skill_id not in medium_signal_ids:
                    calibrated.append(row)
                    continue
                support_counts: Counter[str] = Counter()
                for other_row in occupation_rows:
                    if other_row is row:
                        continue
                    if str(other_row.get("canonical_skill_id") or "") == canonical_skill_id:
                        continue
                    cluster_name = self._infer_row_cluster(other_row)
                    if cluster_name and cluster_name not in {"GENERIC_TRANSVERSAL", "UNKNOWN"}:
                        support_counts[cluster_name] += 1
                total_support = sum(support_counts.values())
                supported_clusters: set[str] = set()
                if total_support > 0:
                    for cluster_name, count in support_counts.items():
                        if count >= self.config.min_anchor_cluster_count or (count / total_support) >= self.config.min_anchor_cluster_share:
                            supported_clusters.add(cluster_name)
                allowed_clusters = rules.get(canonical_skill_id, frozenset())
                if supported_clusters & set(allowed_clusters):
                    calibrated.append(row)
        return calibrated

    def _infer_row_cluster(self, row: dict) -> str:
        canonical_skill_id = str(row.get("canonical_skill_id") or "")
        label, _entity_type, cluster_name = self._canonical_metadata(canonical_skill_id, str(row.get("canonical_label") or ""))
        return cluster_name


def calibrate_occupation_signature_rows(
    rows: Sequence[dict],
    *,
    total_occupations: int,
    config: OccupationSignatureCalibrationConfig | None = None,
) -> list[dict]:
    return OccupationSignatureCalibrator(config=config).filter_rows(rows, total_occupations=total_occupations)
