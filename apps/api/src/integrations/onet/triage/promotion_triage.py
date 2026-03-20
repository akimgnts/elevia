from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

from compass.canonical.canonical_store import get_canonical_store, normalize_canonical_key
from compass.roles.role_family_map import map_onet_occupation_to_role_family

from ..mappers.map_onet_typed_canonical import classify_onet_skills_for_typed_canonical
from ..repository import OnetRepository, utc_now

HIGH_PRIORITY_LIMIT = 60
REVIEWABLE_LIMIT = 200
REPORT_PATH = Path("apps/api/data/onet_promotion_triage_report.json")

_GENERIC_PENALTY_TERMS = {
    "management",
    "communication",
    "coordination",
    "monitoring",
    "analysis",
    "operations",
    "service",
    "reading",
    "writing",
    "speaking",
    "mathematics",
    "science",
    "learning",
}

_HIGH_VALUE_TECH_TERMS = {
    "software",
    "oracle",
    "sap",
    "tableau",
    "python",
    "power bi",
    "microsoft",
    "wms",
    "erp",
    "crm",
    "cloud",
    "server",
    "database",
    "network",
    "api",
    "scada",
    "cam",
    "cad",
    "citrix",
    "cisco",
    "linux",
    "windows",
    "salesforce",
    "git",
    "docker",
    "kubernetes",
}

_PHYSICAL_EQUIPMENT_TERMS = {
    "belt",
    "conveyor",
    "dolly",
    "sprayer",
    "scanner",
    "stand",
    "sampler",
    "saw",
    "pump",
    "compressor",
    "generator",
    "multimeter",
    "meter",
    "valve",
    "furnace",
    "boiler",
    "lamp",
    "ladder",
    "cart",
    "wrench",
    "drill",
    "hammer",
    "pliers",
    "irrigation",
    "purification",
    "oxygen",
    "filtration",
    "mri",
    "ekg",
    "x ray",
    "x-ray",
    "electrocardiography",
}

_SOFTWARE_CONTEXT_TERMS = {
    "software",
    "cloud",
    "server",
    "database",
    "network",
    "computing",
    "application",
    "applications",
    "operating system",
    "operating systems",
}


@dataclass
class CandidateFeatures:
    external_skill_id: str
    proposed_label: str
    proposed_entity_type: str
    source_table: str
    occupation_coverage: int
    role_family_coverage: int
    duplicate_count: int
    canonical_similarity: float
    generic_penalty: float
    physical_penalty: float
    tool_bonus: float
    hot_bonus: float
    coverage_score: float
    cluster_idf_score: float
    score: float
    tier: str
    triage_reason: str


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _compute_similarity(label_norm: str, aliases: list[str]) -> float:
    if not label_norm:
        return 0.0
    best = 0.0
    label_tokens = set(label_norm.split())
    for alias in aliases:
        alias_norm = normalize_canonical_key(alias)
        if not alias_norm:
            continue
        alias_tokens = set(alias_norm.split())
        if label_tokens and alias_tokens and not (label_tokens & alias_tokens):
            continue
        score = SequenceMatcher(None, label_norm, alias_norm).ratio()
        if score > best:
            best = score
    return round(best, 4)


def _generic_penalty(label_norm: str) -> float:
    if not label_norm:
        return 0.6
    penalty = 0.0
    tokens = set(label_norm.split())
    generic_hits = tokens & _GENERIC_PENALTY_TERMS
    penalty += 0.18 * len(generic_hits)
    if label_norm in {"management", "analysis", "operations"}:
        penalty += 0.35
    if len(label_norm.split()) == 1 and label_norm in _GENERIC_PENALTY_TERMS:
        penalty += 0.15
    return min(0.75, penalty)


def _physical_equipment_penalty(source_table: str, label_norm: str, occupation_coverage: int, role_family_coverage: int) -> float:
    if not label_norm:
        return 0.0
    penalty = 0.0
    if source_table == "tools_used":
        penalty += 0.06
    if any(term in label_norm for term in _PHYSICAL_EQUIPMENT_TERMS):
        penalty += 0.2
    if "systems" in label_norm and not any(term in label_norm for term in _SOFTWARE_CONTEXT_TERMS):
        penalty += 0.12
    if source_table == "tools_used" and occupation_coverage <= 3 and role_family_coverage <= 1:
        penalty += 0.1
    return min(0.55, penalty)


def _tool_bonus(source_table: str, label_norm: str, evidence: dict) -> tuple[float, float]:
    bonus = 0.0
    hot_bonus = 0.0
    if source_table == "technology_skills":
        bonus += 0.24
        hot_bonus += 0.04
    elif source_table == "tools_used":
        bonus += 0.06
    if any(term in label_norm for term in _HIGH_VALUE_TECH_TERMS):
        bonus += 0.12
    if any(term in label_norm for term in _SOFTWARE_CONTEXT_TERMS):
        bonus += 0.06
    return min(0.35, bonus), min(0.1, hot_bonus)


def _coverage_score(coverage: int, max_coverage: int) -> float:
    if coverage <= 0 or max_coverage <= 0:
        return 0.0
    return round(math.log1p(coverage) / math.log1p(max_coverage), 4)


def _cluster_idf(role_family_coverage: int, total_role_families: int) -> float:
    if role_family_coverage <= 0 or total_role_families <= 0:
        return 0.0
    return round(math.log((1 + total_role_families) / (1 + role_family_coverage)) / math.log(1 + total_role_families), 4)


def _build_support(repo: OnetRepository) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, int]]:
    conn = repo.connect()
    try:
        occ_titles = {
            row["onetsoc_code"]: row["title"]
            for row in conn.execute("SELECT onetsoc_code, title FROM onet_occupation").fetchall()
        }
        occ_by_skill: dict[str, set[str]] = defaultdict(set)
        for table in ("onet_occupation_skill", "onet_occupation_technology_skill", "onet_occupation_tool"):
            rows = conn.execute(f"SELECT onetsoc_code, external_skill_id FROM {table}").fetchall()
            for row in rows:
                occ_by_skill[row["external_skill_id"]].add(row["onetsoc_code"])

        family_by_skill: dict[str, set[str]] = defaultdict(set)
        for external_skill_id, occ_codes in occ_by_skill.items():
            for code in occ_codes:
                family = map_onet_occupation_to_role_family(code, occ_titles.get(code))
                if family and family != "other":
                    family_by_skill[external_skill_id].add(family)

        dup_counts: dict[str, int] = defaultdict(int)
        rows = conn.execute("SELECT skill_name_norm FROM onet_skill").fetchall()
        for row in rows:
            dup_counts[row["skill_name_norm"]] += 1
        return occ_by_skill, family_by_skill, dup_counts
    finally:
        conn.close()


def _rank_candidates(repo: OnetRepository, proposal_rows: list[dict]) -> list[CandidateFeatures]:
    store = get_canonical_store()
    alias_keys = list(store.alias_to_id.keys())
    occ_by_skill, family_by_skill, dup_counts = _build_support(repo)
    max_coverage = max((len(v) for v in occ_by_skill.values()), default=1)
    all_role_families = {fam for fams in family_by_skill.values() for fam in fams}
    total_role_families = max(len(all_role_families), 1)

    features: list[CandidateFeatures] = []
    for row in proposal_rows:
        evidence = {}
        try:
            evidence = json.loads(row.get("evidence_json") or "{}")
        except Exception:
            evidence = {}
        label = str(row.get("proposed_label") or "")
        label_norm = normalize_canonical_key(label)
        occ_cov = len(occ_by_skill.get(row["external_skill_id"], set()))
        fam_cov = len(family_by_skill.get(row["external_skill_id"], set()))
        similarity = _compute_similarity(label_norm, alias_keys)
        coverage_score = _coverage_score(occ_cov, max_coverage)
        cluster_idf_score = _cluster_idf(fam_cov, total_role_families)
        generic_penalty = _generic_penalty(label_norm)
        physical_penalty = _physical_equipment_penalty(str(row.get("source_table") or ""), label_norm, occ_cov, fam_cov)
        tool_bonus, hot_bonus = _tool_bonus(str(row.get("source_table") or ""), label_norm, evidence)
        duplicate_count = dup_counts.get(label_norm, 0)

        score = (
            0.36 * coverage_score
            + 0.24 * cluster_idf_score
            + 0.18 * similarity
            + tool_bonus
            + hot_bonus
            - generic_penalty
            - physical_penalty
            - (0.12 if duplicate_count > 1 and not any(term in label_norm for term in _HIGH_VALUE_TECH_TERMS) else 0.05 if duplicate_count > 1 else 0.0)
        )
        score = round(_clamp(score), 4)

        reasons: list[str] = []
        if occ_cov >= 20:
            reasons.append("high_occupation_coverage")
        elif occ_cov >= 5:
            reasons.append("moderate_occupation_coverage")
        if cluster_idf_score >= 0.45:
            reasons.append("good_cluster_idf")
        if similarity >= 0.82:
            reasons.append("near_existing_canonical_alias")
        if tool_bonus > 0.0:
            reasons.append("tool_or_technology_signal")
        if generic_penalty >= 0.3:
            reasons.append("generic_penalty")
        if physical_penalty >= 0.18:
            reasons.append("physical_equipment_penalty")
        if duplicate_count > 1:
            reasons.append("duplicate_label_variant")
        if not reasons:
            reasons.append("long_tail_candidate")

        features.append(
            CandidateFeatures(
                external_skill_id=row["external_skill_id"],
                proposed_label=label,
                proposed_entity_type=str(row.get("proposed_entity_type") or ""),
                source_table=str(row.get("source_table") or ""),
                occupation_coverage=occ_cov,
                role_family_coverage=fam_cov,
                duplicate_count=duplicate_count,
                canonical_similarity=similarity,
                generic_penalty=generic_penalty,
                physical_penalty=physical_penalty,
                tool_bonus=tool_bonus,
                hot_bonus=hot_bonus,
                coverage_score=coverage_score,
                cluster_idf_score=cluster_idf_score,
                score=score,
                tier="deferred_long_tail",
                triage_reason="|".join(reasons),
            )
        )

    features.sort(
        key=lambda item: (
            -item.score,
            -item.occupation_coverage,
            -item.cluster_idf_score,
            -item.canonical_similarity,
            item.proposed_label.lower(),
            item.external_skill_id,
        )
    )

    seen_labels: set[str] = set()
    for idx, item in enumerate(features):
        label_norm = normalize_canonical_key(item.proposed_label)
        duplicate_variant = bool(label_norm and label_norm in seen_labels)
        if label_norm:
            seen_labels.add(label_norm)
        if duplicate_variant:
            if "duplicate_label_variant" not in item.triage_reason:
                item.triage_reason = f"{item.triage_reason}|duplicate_label_variant"
            item.tier = "deferred_long_tail" if item.score >= 0.22 else "rejected_noise"
            continue
        if item.generic_penalty >= 0.45 or item.physical_penalty >= 0.3 or item.score < 0.12:
            item.tier = "rejected_noise"
            continue
        if idx < HIGH_PRIORITY_LIMIT and item.score >= 0.28:
            item.tier = "high_priority"
        elif idx < HIGH_PRIORITY_LIMIT + REVIEWABLE_LIMIT and item.score >= 0.18:
            item.tier = "reviewable"
        else:
            item.tier = "deferred_long_tail"
    return features


def _build_report(rows: list[CandidateFeatures], *, output_path: Path) -> dict[str, object]:
    tier_counts = Counter(row.tier for row in rows)
    source_breakdown = Counter(row.source_table for row in rows)
    type_breakdown = Counter(row.proposed_entity_type for row in rows)
    rejected_categories = Counter()
    duplicate_labels = Counter(normalize_canonical_key(row.proposed_label) for row in rows if normalize_canonical_key(row.proposed_label))
    for row in rows:
        if row.tier == "rejected_noise":
            for reason in row.triage_reason.split("|"):
                rejected_categories[reason] += 1

    report = {
        "generated_at": utc_now(),
        "total_candidates": len(rows),
        "tier_distribution": dict(tier_counts),
        "source_table_distribution": dict(source_breakdown),
        "entity_type_distribution": dict(type_breakdown),
        "top_candidates": [row.__dict__ for row in rows[:50]],
        "high_priority_examples": [row.__dict__ for row in rows if row.tier == "high_priority"][:20],
        "reviewable_examples": [row.__dict__ for row in rows if row.tier == "reviewable"][:20],
        "rejected_examples": [row.__dict__ for row in rows if row.tier == "rejected_noise"][:20],
        "rejected_categories": dict(rejected_categories),
        "duplicate_label_count": sum(1 for count in duplicate_labels.values() if count > 1),
        "top_duplicate_labels": [
            {"label_norm": label, "count": count}
            for label, count in duplicate_labels.most_common(20)
            if count > 1
        ],
        "tool_vs_skill_breakdown": {
            "tool_like": sum(1 for row in rows if row.source_table in {"technology_skills", "tools_used"}),
            "skill_like": sum(1 for row in rows if row.source_table == "skills"),
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def run_promotion_triage(
    repo: OnetRepository,
    *,
    source_tables: list[str] | None = None,
    report_path: Path | None = None,
) -> dict[str, object]:
    source_tables = source_tables or ["skills", "technology_skills", "tools_used"]
    skills = [dict(row) for row in repo.list_skills_for_mapping(source_tables=source_tables)]
    mappings, proposals, rejected = classify_onet_skills_for_typed_canonical(skills)
    repo.replace_typed_skill_mapping_outcomes(mappings, proposals, rejected)

    proposal_rows = [dict(row) for row in repo.list_canonical_promotion_candidates(review_status="pending")]
    ranked = _rank_candidates(repo, proposal_rows)
    repo.update_canonical_promotion_triage(ranked)
    report = _build_report(ranked, output_path=report_path or REPORT_PATH)
    report["mapped_existing"] = len(mappings)
    report["proposed_pending"] = len(proposal_rows)
    report["rejected_noise_count"] = len(rejected)
    return report
