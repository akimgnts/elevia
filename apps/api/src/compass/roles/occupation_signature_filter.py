from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Sequence

from compass.canonical.canonical_store import get_canonical_store
from compass.canonical.master_store import get_master_canonical_store

LOW_SIGNAL_SEED_IDS: frozenset[str] = frozenset(
    {
        "skill:problem_solving",
        "skill:observability",
        "skill:negotiation",
        "skill:time_management",
        "skill:spreadsheet_analysis",
        "skill:process_documentation",
        "skill:documentation",
        "skill:data_storytelling",
        "skill:presentation_skills",
        "skill:stakeholder_communication",
        "skill:stakeholder_management",
    }
)


@dataclass(frozen=True)
class OccupationSignatureFilterConfig:
    max_occupation_share: float = 0.50
    max_human_skill_share: float = 0.15
    max_transversal_share: float = 0.15
    explicit_low_signal_ids: frozenset[str] = LOW_SIGNAL_SEED_IDS


@dataclass(frozen=True)
class SignatureSkillStat:
    canonical_skill_id: str
    canonical_label: str
    canonical_type: str
    canonical_cluster: str
    occupation_count: int
    occupation_share: float


class OccupationSignatureFilter:
    def __init__(self, config: OccupationSignatureFilterConfig | None = None) -> None:
        self.config = config or OccupationSignatureFilterConfig()
        self._base_store = get_canonical_store()
        self._master_store = get_master_canonical_store()

    def build_skill_stats(
        self,
        rows: Sequence[dict],
        *,
        total_occupations: int,
    ) -> dict[str, SignatureSkillStat]:
        if total_occupations <= 0:
            return {}

        occupation_sets: dict[str, set[str]] = defaultdict(set)
        labels: dict[str, str] = {}
        for row in rows:
            canonical_skill_id = str(row.get("canonical_skill_id") or "")
            onetsoc_code = str(row.get("onetsoc_code") or "")
            if not canonical_skill_id or not onetsoc_code:
                continue
            occupation_sets[canonical_skill_id].add(onetsoc_code)
            labels.setdefault(canonical_skill_id, str(row.get("canonical_label") or canonical_skill_id))

        stats: dict[str, SignatureSkillStat] = {}
        for canonical_skill_id, onetsoc_codes in occupation_sets.items():
            entity = self._master_store.get(canonical_skill_id)
            base_entry = self._base_store.id_to_skill.get(canonical_skill_id, {})
            cluster_name = str(base_entry.get("cluster_name") or "")
            if not cluster_name and entity is not None:
                cluster_name = str(entity.metadata.get("cluster_name") or "")
            occupation_count = len(onetsoc_codes)
            stats[canonical_skill_id] = SignatureSkillStat(
                canonical_skill_id=canonical_skill_id,
                canonical_label=str((entity.label if entity else "") or labels.get(canonical_skill_id) or canonical_skill_id),
                canonical_type=str((entity.type if entity else "") or "unknown"),
                canonical_cluster=cluster_name or "UNKNOWN",
                occupation_count=occupation_count,
                occupation_share=occupation_count / float(total_occupations),
            )
        return stats

    def identify_low_discriminant_skill_ids(
        self,
        rows: Sequence[dict],
        *,
        total_occupations: int,
    ) -> set[str]:
        stats = self.build_skill_stats(rows, total_occupations=total_occupations)
        low_signal_ids: set[str] = set(self.config.explicit_low_signal_ids)
        for canonical_skill_id, stat in stats.items():
            if stat.occupation_share > self.config.max_occupation_share:
                low_signal_ids.add(canonical_skill_id)
                continue
            if stat.canonical_type == "skill_human" and stat.occupation_share > self.config.max_human_skill_share:
                low_signal_ids.add(canonical_skill_id)
                continue
            if stat.canonical_cluster == "GENERIC_TRANSVERSAL" and stat.occupation_share > self.config.max_transversal_share:
                low_signal_ids.add(canonical_skill_id)
        return low_signal_ids

    def filter_rows(
        self,
        rows: Sequence[dict],
        *,
        total_occupations: int,
    ) -> list[dict]:
        if not rows:
            return []
        low_signal_ids = self.identify_low_discriminant_skill_ids(rows, total_occupations=total_occupations)
        return [dict(row) for row in rows if str(row.get("canonical_skill_id") or "") not in low_signal_ids]


def filter_occupation_signature_rows(
    rows: Sequence[dict],
    *,
    total_occupations: int,
    config: OccupationSignatureFilterConfig | None = None,
) -> list[dict]:
    return OccupationSignatureFilter(config=config).filter_rows(rows, total_occupations=total_occupations)
