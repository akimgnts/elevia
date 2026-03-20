#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

REPO_ROOT = Path(__file__).resolve().parents[3]
API_SRC = REPO_ROOT / "apps" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from compass.canonical.master_store import get_master_canonical_store, reset_master_canonical_store  # noqa: E402
from compass.roles.occupation_resolver import OccupationResolver  # noqa: E402
from compass.roles.occupation_signature_calibration import OccupationSignatureCalibrator  # noqa: E402
from compass.roles.occupation_signature_role_context import (  # noqa: E402
    DOMAIN_REFINEMENT_RULES,
    OccupationSignatureRoleContextRefiner,
    PHASE2_ROLE_CONTEXT_RULES,
    RoleContextRefinementConfig,
)
from compass.roles.role_resolver import RoleResolver  # noqa: E402
from integrations.onet.repository import OnetRepository  # noqa: E402

EVAL_CASES = REPO_ROOT / "apps" / "api" / "data" / "eval" / "role_resolver_eval_cases.jsonl"


def _signature_stats(rows: list[dict]) -> dict[str, float | int]:
    master_store = get_master_canonical_store()
    by_occupation: dict[str, dict[str, str]] = defaultdict(dict)
    for row in rows:
        onetsoc_code = str(row.get("onetsoc_code") or "")
        canonical_skill_id = str(row.get("canonical_skill_id") or "")
        if not onetsoc_code or not canonical_skill_id:
            continue
        entity = master_store.get(canonical_skill_id)
        cluster_name = "UNKNOWN"
        if entity is not None:
            cluster_name = str(entity.metadata.get("cluster_name") or cluster_name)
        by_occupation[onetsoc_code][canonical_skill_id] = cluster_name

    counts = [len(skill_map) for skill_map in by_occupation.values()]
    if not counts:
        return {
            "occupations_with_skills": 0,
            "mean_skills_per_occupation": 0.0,
            "median_skills_per_occupation": 0.0,
            "occupations_ge_3_skills": 0,
            "occupations_ge_5_skills": 0,
            "mean_cluster_entropy": 0.0,
        }

    entropies: list[float] = []
    for skill_map in by_occupation.values():
        cluster_counts: dict[str, int] = defaultdict(int)
        for cluster_name in skill_map.values():
            if cluster_name and cluster_name != "UNKNOWN":
                cluster_counts[cluster_name] += 1
        if not cluster_counts:
            entropies.append(0.0)
            continue
        total = sum(cluster_counts.values())
        entropy = 0.0
        for count in cluster_counts.values():
            p = count / total
            entropy -= p * math.log2(p)
        entropies.append(entropy)

    return {
        "occupations_with_skills": len(by_occupation),
        "mean_skills_per_occupation": round(mean(counts), 3),
        "median_skills_per_occupation": float(median(counts)),
        "occupations_ge_3_skills": sum(1 for count in counts if count >= 3),
        "occupations_ge_5_skills": sum(1 for count in counts if count >= 5),
        "mean_cluster_entropy": round(mean(entropies), 4),
    }


def _rows_by_occupation(rows: list[dict]) -> dict[str, set[str]]:
    by_occupation: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        onetsoc_code = str(row.get("onetsoc_code") or "")
        canonical_skill_id = str(row.get("canonical_skill_id") or "")
        if onetsoc_code and canonical_skill_id:
            by_occupation[onetsoc_code].add(canonical_skill_id)
    return by_occupation


def _medium_signal_skill_analysis(rows: list[dict], total_occupations: int) -> list[dict[str, object]]:
    calibrator = OccupationSignatureCalibrator()
    stats = calibrator.build_medium_signal_stats(rows, total_occupations=total_occupations)
    return [
        {
            "canonical_skill_id": stat.canonical_skill_id,
            "canonical_label": stat.canonical_label,
            "canonical_type": stat.canonical_type,
            "canonical_cluster": stat.canonical_cluster,
            "occupation_count": stat.occupation_count,
            "occupation_share": round(stat.occupation_share, 4),
            "cluster_distribution": stat.cluster_distribution,
            "cluster_entropy": stat.cluster_entropy,
        }
        for stat in sorted(stats.values(), key=lambda item: (-item.occupation_count, item.canonical_label))
    ]


def _skill_redundancy_score(rows: list[dict], broad_skill_ids: set[str]) -> float:
    by_occupation = _rows_by_occupation(rows)
    if not by_occupation:
        return 0.0
    ratios: list[float] = []
    for skill_ids in by_occupation.values():
        if not skill_ids:
            continue
        ratios.append(len(skill_ids & broad_skill_ids) / float(len(skill_ids)))
    return round(mean(ratios), 4) if ratios else 0.0


def _load_eval_cases() -> list[dict]:
    if not EVAL_CASES.exists():
        return []
    with EVAL_CASES.open() as handle:
        return [json.loads(line) for line in handle if line.strip()]


class _SignatureRepoView:
    def __init__(self, base_repo: OnetRepository, signature_rows: list[dict]):
        self._base_repo = base_repo
        self._signature_rows = [dict(row) for row in signature_rows]

    def list_occupation_title_candidates(self):
        return self._base_repo.list_occupation_title_candidates()

    def list_occupations(self):
        return self._base_repo.list_occupations()

    def list_occupation_mapped_skills(self):
        return [dict(row) for row in self._signature_rows]


def _resolver_metrics(
    repo: OnetRepository,
    signature_rows: list[dict],
    *,
    tracked_skill_ids: set[str] | None = None,
) -> dict[str, object]:
    cases = _load_eval_cases()
    if not cases:
        return {}
    resolver = RoleResolver(occupation_resolver=OccupationResolver(repo=_SignatureRepoView(repo, signature_rows)))
    confidences: list[float] = []
    overlaps: list[int] = []
    displayable_cases = 0
    false_overlap_cases = 0
    overlap_contribution: defaultdict[str, dict[str, int]] = defaultdict(lambda: {"candidate_hits": 0, "displayable_hits": 0, "false_overlap_hits": 0})

    for case in cases:
        result = resolver.resolve(
            raw_title=str(case.get("raw_title") or ""),
            canonical_skills=list(case.get("canonical_skills") or []),
        )
        confidence = float(result.get("occupation_confidence") or 0.0)
        confidences.append(confidence)
        if bool((result.get("evidence") or {}).get("displayable")):
            displayable_cases += 1
        primary = next(iter(result.get("candidate_occupations") or []), None)
        overlap = int((((primary or {}).get("evidence") or {}).get("skill_overlap") or {}).get("count") or 0)
        overlaps.append(overlap)
        predicted_family = result.get("primary_role_family")
        expected_family = case.get("expected_role_family")
        if predicted_family and expected_family and predicted_family != expected_family and overlap > 0 and confidence >= 0.65:
            false_overlap_cases += 1
        if tracked_skill_ids:
            for candidate in result.get("candidate_occupations") or []:
                overlap_ids = set(((((candidate or {}).get("evidence") or {}).get("skill_overlap") or {}).get("canonical_ids") or []))
                for canonical_skill_id in sorted(overlap_ids & tracked_skill_ids):
                    overlap_contribution[canonical_skill_id]["candidate_hits"] += 1
                    if bool((result.get("evidence") or {}).get("displayable")):
                        overlap_contribution[canonical_skill_id]["displayable_hits"] += 1
                    if predicted_family and expected_family and predicted_family != expected_family and confidence >= 0.65:
                        overlap_contribution[canonical_skill_id]["false_overlap_hits"] += 1

    sorted_confidences = sorted(confidences)
    median_confidence = sorted_confidences[len(sorted_confidences) // 2] if sorted_confidences else 0.0
    metrics = {
        "cases": len(cases),
        "average_overlap_size": round(mean(overlaps), 3) if overlaps else 0.0,
        "average_confidence": round(mean(confidences), 4) if confidences else 0.0,
        "median_confidence": round(float(median_confidence), 4),
        "displayable_cases": displayable_cases,
        "false_overlap_cases": false_overlap_cases,
    }
    if tracked_skill_ids:
        metrics["overlap_contribution_by_skill"] = {
            canonical_skill_id: overlap_contribution.get(
                canonical_skill_id,
                {"candidate_hits": 0, "displayable_hits": 0, "false_overlap_hits": 0},
            )
            for canonical_skill_id in sorted(tracked_skill_ids)
        }
    return metrics


def _refinement_metrics(
    before_rows: list[dict],
    after_rows: list[dict],
    *,
    decisions: list[object],
    broad_skill_ids: set[str],
) -> dict[str, object]:
    retained_counts: dict[str, int] = defaultdict(int)
    removed_counts: dict[str, int] = defaultdict(int)
    anchor_sets_by_occupation: dict[str, set[str]] = defaultdict(set)
    for decision in decisions:
        if decision.retained:
            retained_counts[decision.canonical_skill_id] += 1
            anchor_sets_by_occupation[decision.onetsoc_code].update(decision.matched_anchor_ids)
        else:
            removed_counts[decision.canonical_skill_id] += 1

    retention_by_skill: dict[str, dict[str, float | int]] = {}
    for canonical_skill_id in sorted(broad_skill_ids):
        retained = retained_counts.get(canonical_skill_id, 0)
        removed = removed_counts.get(canonical_skill_id, 0)
        total = retained + removed
        retention_by_skill[canonical_skill_id] = {
            "retained": retained,
            "removed": removed,
            "retention_rate": round(retained / float(total), 4) if total else 0.0,
        }

    avg_anchor_count = 0.0
    if anchor_sets_by_occupation:
        avg_anchor_count = round(mean(len(anchor_ids) for anchor_ids in anchor_sets_by_occupation.values()), 3)

    total_retained = sum(item["retained"] for item in retention_by_skill.values())
    total_considered = sum((item["retained"] + item["removed"]) for item in retention_by_skill.values())
    return {
        "retention_by_skill": retention_by_skill,
        "overall_retention_rate": round(total_retained / float(total_considered or 1), 4),
        "average_contextual_anchors_per_occupation": avg_anchor_count,
        "skill_redundancy_score_before": _skill_redundancy_score(before_rows, broad_skill_ids),
        "skill_redundancy_score_after": _skill_redundancy_score(after_rows, broad_skill_ids),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate occupation signature precision before filtering, after calibration, and after role-context refinement"
    )
    parser.add_argument("--db", default=str(REPO_ROOT / "apps" / "api" / "data" / "db" / "onet.db"))
    args = parser.parse_args()

    reset_master_canonical_store()
    repo = OnetRepository(Path(args.db))
    repo.ensure_schema()

    raw_rows = repo.list_occupation_mapped_skills(apply_signature_filter=False)
    low_filtered_rows = repo.list_occupation_mapped_skills(
        apply_signature_filter=True,
        apply_signature_calibration=False,
    )
    calibrated_rows = repo.list_occupation_mapped_skills(
        apply_signature_filter=True,
        apply_signature_calibration=True,
        apply_signature_role_context=False,
    )
    role_context_refiner = OccupationSignatureRoleContextRefiner(
        config=RoleContextRefinementConfig(enable_phase2=False, enable_domain_refinement=False)
    )
    phase1_rows = role_context_refiner.filter_rows(calibrated_rows)
    phase2_refiner = OccupationSignatureRoleContextRefiner(
        config=RoleContextRefinementConfig(enable_domain_refinement=False)
    )
    phase2_rows, phase2_decisions = phase2_refiner.filter_rows(
        calibrated_rows,
        return_diagnostics=True,
    )
    domain_refiner = OccupationSignatureRoleContextRefiner()
    domain_rows, domain_decisions = domain_refiner.filter_rows(
        calibrated_rows,
        return_diagnostics=True,
    )

    total_occupations = repo.count_occupations()
    before = _signature_stats(raw_rows)
    after_low_filter = _signature_stats(low_filtered_rows)
    after_calibration = _signature_stats(calibrated_rows)
    after_role_context = _signature_stats(phase1_rows)
    after_phase2 = _signature_stats(phase2_rows)
    after_domain = _signature_stats(domain_rows)
    occupation_titles = {row["onetsoc_code"]: row["title"] for row in repo.list_occupations()}
    broad_skill_analysis = [
        {
            "canonical_skill_id": stat.canonical_skill_id,
            "canonical_label": stat.canonical_label,
            "canonical_type": stat.canonical_type,
            "canonical_cluster": stat.canonical_cluster,
            "occupation_count": stat.occupation_count,
            "occupation_share": round(stat.occupation_share, 4),
            "cluster_distribution": stat.cluster_distribution,
            "cluster_entropy": stat.cluster_entropy,
            "role_family_distribution": stat.role_family_distribution,
            "top_cooccurring_skills": stat.top_cooccurring_skills,
        }
        for stat in sorted(
            phase2_refiner.build_broad_skill_stats(
                phase1_rows,
                total_occupations=total_occupations,
                occupation_titles=occupation_titles,
                skill_ids=set(PHASE2_ROLE_CONTEXT_RULES),
            ).values(),
            key=lambda item: (-item.occupation_count, item.canonical_label),
        )
    ]
    broad_skill_ids = set(PHASE2_ROLE_CONTEXT_RULES)
    domain_skill_analysis = [
        {
            "canonical_skill_id": stat.canonical_skill_id,
            "canonical_label": stat.canonical_label,
            "canonical_type": stat.canonical_type,
            "canonical_cluster": stat.canonical_cluster,
            "occupation_count": stat.occupation_count,
            "occupation_share": round(stat.occupation_share, 4),
            "cluster_distribution": stat.cluster_distribution,
            "cluster_entropy": stat.cluster_entropy,
            "role_family_distribution": stat.role_family_distribution,
            "top_cooccurring_skills": stat.top_cooccurring_skills,
        }
        for stat in sorted(
            domain_refiner.build_broad_skill_stats(
                phase2_rows,
                total_occupations=total_occupations,
                occupation_titles=occupation_titles,
                skill_ids=set(DOMAIN_REFINEMENT_RULES),
            ).values(),
            key=lambda item: (-item.occupation_count, item.canonical_label),
        )
    ]
    domain_skill_ids = set(DOMAIN_REFINEMENT_RULES)

    report = {
        "before_filtering": before,
        "after_low_signal_filter": after_low_filter,
        "after_calibration": after_calibration,
        "after_role_context_refinement": after_role_context,
        "after_context_refinement_phase2": after_phase2,
        "after_domain_refinement": after_domain,
        "delta_vs_before": {
            key: round(float(after_domain[key]) - float(before[key]), 4)
            for key in before.keys()
        },
        "delta_vs_low_filter": {
            key: round(float(after_domain[key]) - float(after_low_filter[key]), 4)
            for key in after_low_filter.keys()
        },
        "delta_vs_calibration": {
            key: round(float(after_domain[key]) - float(after_calibration[key]), 4)
            for key in after_calibration.keys()
        },
        "delta_vs_role_context_refinement": {
            key: round(float(after_phase2[key]) - float(after_role_context[key]), 4)
            for key in after_role_context.keys()
        },
        "delta_vs_context_refinement_phase2": {
            key: round(float(after_domain[key]) - float(after_phase2[key]), 4)
            for key in after_phase2.keys()
        },
        "medium_signal_skill_analysis": _medium_signal_skill_analysis(low_filtered_rows, total_occupations),
        "phase2_broad_skill_analysis": broad_skill_analysis,
        "phase2_cooccurrence_matrix": {
            item["canonical_skill_id"]: {skill_id: count for skill_id, count in item["top_cooccurring_skills"]}
            for item in broad_skill_analysis
        },
        "phase2_context_metrics": _refinement_metrics(
            phase1_rows,
            phase2_rows,
            decisions=phase2_decisions,
            broad_skill_ids=broad_skill_ids,
        ),
        "domain_skill_analysis": domain_skill_analysis,
        "domain_cooccurrence_matrix": {
            item["canonical_skill_id"]: {skill_id: count for skill_id, count in item["top_cooccurring_skills"]}
            for item in domain_skill_analysis
        },
        "domain_context_metrics": _refinement_metrics(
            phase2_rows,
            domain_rows,
            decisions=domain_decisions,
            broad_skill_ids=domain_skill_ids,
        ),
        "resolver_overlap_comparison": {
            "before_phase2_refinement": _resolver_metrics(repo, phase1_rows),
            "after_phase2_refinement": _resolver_metrics(repo, phase2_rows),
            "before_domain_refinement": _resolver_metrics(repo, phase2_rows, tracked_skill_ids=domain_skill_ids),
            "after_domain_refinement": _resolver_metrics(repo, domain_rows, tracked_skill_ids=domain_skill_ids),
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
