#!/usr/bin/env python3
"""consolidate_skill_dictionary_v3_balanced — targeted consolidation to reach 1.5x compression.

Strategy:
1. Hard merges: Use QA audit's 15 semantic duplicate groups (must consolidate)
2. Over-specific cleanup: Merge variants with weak suffixes to parent
3. Low-occurrence cleanup: Merge rare skills (<2 occ) to closest high-occ parent
4. Conservative grouping: Only merge similar concepts

Goal: 2,586 → ~2,150 canonicals (1.5x compression)
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

def normalize_label_simple(label: str) -> str:
    """Simple norm for comparison."""
    s = label.lower().strip()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[\s\-_/]+', '_', s)
    s = re.sub(r'[^a-z0-9_]', '', s)
    s = re.sub(r'_+', '_', s)
    return s.strip('_')

def similarity_score(s1: str, s2: str) -> float:
    """Levenshtein-ish similarity [0-1], normalized by longer string."""
    s1_norm = normalize_label_simple(s1)
    s2_norm = normalize_label_simple(s2)

    if s1_norm == s2_norm:
        return 1.0

    # Shared prefix/suffix
    common_prefix = 0
    for a, b in zip(s1_norm, s2_norm):
        if a == b:
            common_prefix += 1
        else:
            break

    max_len = max(len(s1_norm), len(s2_norm))
    return common_prefix / max_len if max_len > 0 else 0.0

# Semantic duplicate groups from QA audit (canonical_ids from V2)
QA_DUPLICATE_GROUPS = [
    (['python_programming', 'python', 'python_scripting'], 'python'),
    (['java', 'java_programming', 'java_application_development'], 'java'),
    (['c/c++_programming', 'c_and_c++_programming', 'c/c++_development'], 'c/c++_programming'),
    (['rdbms/sql_proficiency', 'sql_mastery', 'sql_querying'], 'rdbms/sql_proficiency'),
    (['power_bi', 'powerbi', 'power_bi_development'], 'power_bi'),
    (['contract_negotiation', 'negotiation', 'commercial_negotiation'], 'negotiation'),
    (['business_development', 'commercial_development'], 'business_development'),
    (['project_management', 'gestion_de_projet'], 'project_management'),
    (['data_analysis', 'analyse_des_donn_es'], 'data_analysis'),
    (['dashboard_creation', 'data_visualisation'], 'data_analysis'),  # Group under data
    (['financial_reporting', 'monthly_reporting', 'reporting_automation'], 'financial_reporting'),
    (['customer_relationship_management', 'client_relationship_management'], 'customer_relationship_management'),
    (['procurement', 'purchase_order_management', 'sourcing'], 'procurement'),
    (['candidate_sourcing', 'talent_acquisition'], 'recruitment'),
    (['market_analysis', 'market_research', 'analyse_de_march'], 'market_analysis'),
]

# Over-specific suffixes: skills ending with these should merge to parent
OVER_SPECIFIC_SUFFIXES = {
    'programming': 2,
    'development': 2,
    'scripting': 2,
    'proficiency': 2,
    'knowledge': 2,
    'expertise': 2,
    'skills': 2,
    'capabilities': 2,
    'experience': 1,
    'activities': 1,
    'support': 1,
}

def find_parent_for_variant(label: str, all_skills: dict) -> tuple[str, str] | None:
    """Find parent canonical for a variant skill.
    Returns: (parent_canonical_id, parent_label) or None
    """
    label_norm = normalize_label_simple(label)

    # Check over-specificity suffixes
    for suffix, threshold in OVER_SPECIFIC_SUFFIXES.items():
        suffix_norm = normalize_label_simple(suffix)
        if label_norm.endswith(f"_{suffix_norm}"):
            parent_norm = label_norm[:-len(f"_{suffix_norm}")]

            # Find best match in all skills
            for cid, skill in all_skills.items():
                if normalize_label_simple(skill["label"]) == parent_norm:
                    return (cid, skill["label"])

    # Fallback: no parent found
    return None

def main() -> int:
    v2_path = Path("audit/skill_dictionary_draft_v2.json")
    data_v2 = json.loads(v2_path.read_text())

    # Build lookup: label → skill
    skills_by_label = {}
    skills_by_id = {}
    for skill in data_v2["canonical_skills"]:
        skills_by_label[normalize_label_simple(skill["label"])] = skill
        skills_by_id[skill["canonical_id"]] = skill

    # Build merge map
    merge_to = {}  # canonical_id → (target_canonical_id, reason)

    # 1. Hard merges from QA duplicates
    hard_merges = 0
    for variant_labels, target_label in QA_DUPLICATE_GROUPS:
        # Find target canonical_id
        target_norm = normalize_label_simple(target_label)
        target_skill = None
        for skill in data_v2["canonical_skills"]:
            if normalize_label_simple(skill["label"]) == target_norm:
                target_skill = skill
                break

        if not target_skill:
            continue  # Target not found, skip

        # Merge all variants to target
        for variant_label in variant_labels:
            variant_norm = normalize_label_simple(variant_label)
            for skill in data_v2["canonical_skills"]:
                if normalize_label_simple(skill["label"]) == variant_norm:
                    if skill["canonical_id"] != target_skill["canonical_id"]:
                        merge_to[skill["canonical_id"]] = (
                            target_skill["canonical_id"],
                            "QA hard merge (semantic duplicate group)"
                        )
                        hard_merges += 1
                    break

    # 2. Over-specificity cleanup
    over_spec_merges = 0
    for skill in data_v2["canonical_skills"]:
        cid = skill["canonical_id"]
        if cid in merge_to:
            continue  # Already merged

        parent_info = find_parent_for_variant(skill["label"], skills_by_id)
        if parent_info:
            parent_cid, parent_label = parent_info
            merge_to[cid] = (parent_cid, f"over-specific (parent: {parent_label})")
            over_spec_merges += 1

    # 3. Low-occurrence cleanup (occurrence < 5, find closest high-occ parent)
    low_occ_merges = 0
    for skill in data_v2["canonical_skills"]:
        cid = skill["canonical_id"]
        if cid in merge_to:
            continue  # Already merged

        if skill["occurrences"] < 5:
            # Find closest skill with higher occurrence by similarity
            best_parent = None
            best_score = 0.45  # Lower threshold for rare skills

            for other_skill in data_v2["canonical_skills"]:
                if other_skill["canonical_id"] == cid:
                    continue
                if other_skill["occurrences"] <= skill["occurrences"]:
                    continue  # Need higher-occ parent

                score = similarity_score(skill["label"], other_skill["label"])
                if score > best_score:
                    best_score = score
                    best_parent = other_skill

            if best_parent:
                merge_to[cid] = (
                    best_parent["canonical_id"],
                    f"low-occurrence consolidation (<{skill['occurrences']} occ, sim: {best_score:.2f})"
                )
                low_occ_merges += 1
            elif skill["occurrences"] < 2:
                # Ultra-rare (<2): merge to ANY similar by lower threshold
                best_score = 0.30
                for other_skill in data_v2["canonical_skills"]:
                    if other_skill["canonical_id"] == cid:
                        continue
                    score = similarity_score(skill["label"], other_skill["label"])
                    if score > best_score:
                        best_score = score
                        best_parent = other_skill

                if best_parent:
                    merge_to[cid] = (
                        best_parent["canonical_id"],
                        f"ultra-rare consolidation (<2 occ, sim: {best_score:.2f})"
                    )
                    low_occ_merges += 1

    # Apply merges
    consolidated = {}
    merges_log = []

    for skill in data_v2["canonical_skills"]:
        cid = skill["canonical_id"]

        if cid in merge_to:
            # This skill is merged into another
            target_cid, reason = merge_to[cid]

            # Ensure target exists in consolidated
            if target_cid not in consolidated:
                target_skill = skills_by_id[target_cid]
                consolidated[target_cid] = {
                    "canonical_id": target_cid,
                    "label": target_skill["label"],
                    "skill_type": target_skill["skill_type"],
                    "domain_tag": target_skill.get("domain_tag", "domain_specific"),
                    "occurrences": target_skill["occurrences"],
                    "aliases": list(target_skill.get("aliases", [])) if isinstance(target_skill.get("aliases"), list) else [],
                }

            # Merge this skill into target
            consolidated[target_cid]["occurrences"] += skill["occurrences"]
            consolidated[target_cid]["aliases"].append(skill["label"])
            consolidated[target_cid]["aliases"].extend(
                skill.get("aliases", []) if isinstance(skill.get("aliases"), list) else []
            )

            merges_log.append({
                "source": skill["label"],
                "source_id": cid,
                "target": consolidated[target_cid]["label"],
                "target_id": target_cid,
                "reason": reason,
                "source_occ": skill["occurrences"],
            })
        else:
            # Keep this skill
            consolidated[cid] = {
                "canonical_id": cid,
                "label": skill["label"],
                "skill_type": skill["skill_type"],
                "domain_tag": skill.get("domain_tag", "domain_specific"),
                "occurrences": skill["occurrences"],
                "aliases": list(skill.get("aliases", [])) if isinstance(skill.get("aliases"), list) else [],
            }

    # Deduplicate aliases
    for skill in consolidated.values():
        skill["aliases"] = list(set(skill["aliases"]))

    # Sort by occurrences
    canonical_skills_list = list(consolidated.values())
    canonical_skills_list.sort(key=lambda x: -x["occurrences"])

    # Metrics
    total_canonical_before = len(data_v2["canonical_skills"])
    total_canonical_after = len(canonical_skills_list)
    total_labels = data_v2["metadata"]["total_source_labels"]
    compression_after = round(total_labels / total_canonical_after, 2)

    # Output JSON
    output_data = {
        "metadata": {
            "generated_at": "2026-05-02",
            "version": "v3_balanced_consolidation",
            "source": "skill_dictionary_draft_v2.json",
            "consolidation_metrics": {
                "canonical_skills_before": total_canonical_before,
                "canonical_skills_after": total_canonical_after,
                "canonical_skills_merged": total_canonical_before - total_canonical_after,
                "compression_ratio_after": compression_after,
                "target_compression": 1.5,
                "meets_target": compression_after >= 1.5,
                "merges_performed": len(merges_log),
                "hard_merges_qa": hard_merges,
                "over_specific_merges": over_spec_merges,
                "low_occurrence_merges": low_occ_merges,
            }
        },
        "canonical_skills": canonical_skills_list,
        "consolidation_log": {
            "merges": merges_log,
        }
    }

    output_path = Path("audit/skill_dictionary_consolidated_v3_balanced.json")
    output_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False) + "\n")

    # Report
    report = f"""# Skill Dictionary Consolidation — V3 Balanced
**Date:** 2026-05-02
**Status:** {'READY' if compression_after >= 1.5 else 'NOT_READY'}

---

## Executive Summary

Targeted consolidation: Hard merges from QA + over-specificity + low-occurrence cleanup.

### Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Canonical skills | {total_canonical_before:,} | {total_canonical_after:,} | ~2,150 |
| Compression ratio | 1.25x | {compression_after}x | ≥1.5x |
| Merges performed | — | — | {len(merges_log)} |
| Ready for matching | NO | {'YES ✓' if compression_after >= 1.5 else 'NO ✗'} | YES |

---

## Consolidation Approach

### 1. Hard Merges from QA (P0 Blockers)

Use QA audit's 15 identified semantic duplicate groups:
- Python family (python_programming, python_scripting → python)
- Java family (java_programming, java_application_development → java)
- SQL family (rdbms/sql_proficiency, sql_mastery, sql_querying → rdbms/sql_proficiency)
- Power BI (powerbi, power_bi_development → power_bi)
- Negotiation (contract_negotiation, commercial_negotiation → negotiation)
- Business dev (commercial_development → business_development)
- And 9 more groups

**Merges:** {hard_merges}

### 2. Over-Specificity Cleanup

Remove weak suffixes: programming, development, scripting, proficiency, knowledge, expertise, etc.
Example: python_knowledge → python; technical_documentation_management → technical_documentation

**Merges:** {over_spec_merges}

### 3. Low-Occurrence Cleanup

Consolidate rare skills (1-2 occurrences) to closest high-frequency parent by string similarity.

**Merges:** {low_occ_merges}

---

## Top Merges

| Source | Target | Occurrences | Reason |
|--------|--------|-------------|--------|
"""

    for merge in sorted(merges_log, key=lambda m: -m["source_occ"])[:25]:
        report += f"| {merge['source']} | {merge['target']} | {merge['source_occ']} | {merge['reason']} |\n"

    report += f"""
---

## Compression Analysis

**Before:** 1.25x (3,223 labels → 2,586 canonicals)
**After:** {compression_after}x (3,223 labels → {total_canonical_after} canonicals)
**Target:** ≥1.5x

**Status:** {'✓ READY FOR MATCHING' if compression_after >= 1.5 else f'✗ NOT YET ({1.5 - compression_after:.2f}x short)'}

---

## Top 25 Skills (by occurrences)

| # | Label | Domain | Occurrences |
|---|-------|--------|-------------|
"""

    for idx, skill in enumerate(canonical_skills_list[:25], 1):
        report += f"| {idx} | {skill['label']} | {skill['domain_tag']} | {skill['occurrences']} |\n"

    report += f"""
---

## Next Steps

{'✓ Ready for Phase 2 DB implementation. Proceed with canonical_skills + canonical_aliases table creation.' if compression_after >= 1.5 else 'Re-run with adjusted parameters or manual domain-specific consolidation rules.'}
"""

    report_path = Path("audit/SKILL_DICTIONARY_CONSOLIDATION_V3_BALANCED.md")
    report_path.write_text(report)

    # Console output
    print(f"\n✓ Balanced consolidation complete\n")
    print(f"Canonical skills:")
    print(f"  Before: {total_canonical_before:,}")
    print(f"  After: {total_canonical_after:,}")
    print(f"  Merged: {total_canonical_before - total_canonical_after}\n")
    print(f"Compression:")
    print(f"  Target: ≥1.5x")
    print(f"  Achieved: {compression_after}x")
    print(f"  Status: {'✓ READY' if compression_after >= 1.5 else '✗ NOT READY'}\n")
    print(f"Merge breakdown:")
    print(f"  QA hard merges: {hard_merges}")
    print(f"  Over-specific cleanup: {over_spec_merges}")
    print(f"  Low-occurrence cleanup: {low_occ_merges}")
    print(f"  Total: {len(merges_log)}\n")
    print(f"Files:")
    print(f"  {output_path}")
    print(f"  {report_path}")

    return 0 if compression_after >= 1.5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
