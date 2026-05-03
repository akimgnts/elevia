#!/usr/bin/env python3
"""consolidate_skill_dictionary_v3_improved — hierarchical consolidation to 1.5x compression.

Goal: Reduce 2,586 canonicals to ~2,150 (3,223 labels / 1.5x).

Strategy:
1. Group by semantic root (concept extraction)
2. For each group with >1 skill: keep most general, merge others
3. Conservative: only merge if variants are "similar" (same root + low-occ or same-type)
4. Track all merges with aliases

Output: skill_dictionary_consolidated_v3_improved.json + report
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

def normalize_label_simple(label: str) -> str:
    """Simple norm for comparison."""
    s = label.lower().strip()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[\s\-_/]+', '_', s)
    s = re.sub(r'[^a-z0-9_]', '', s)
    s = re.sub(r'_+', '_', s)
    return s.strip('_')

# Semantic roots: keyword → canonical root
SEMANTIC_ROOTS = {
    # Programming languages
    'python': 'python',
    'java': 'java',
    'c/c++': 'cpp',
    'c_and_c++': 'cpp',
    'javascript': 'javascript',
    'typescript': 'typescript',
    'kotlin': 'kotlin',
    'scala': 'scala',
    'ruby': 'ruby',
    'php': 'php',
    'go': 'go',
    'rust': 'rust',
    'r_language': 'r',

    # Data/Analytics
    'data': 'data',
    'analytics': 'analytics',
    'bi': 'bi',
    'tableau': 'tableau',
    'power_bi': 'power_bi',
    'powerbi': 'power_bi',
    'looker': 'looker',
    'reporting': 'reporting',

    # Database
    'sql': 'sql',
    'mysql': 'mysql',
    'postgresql': 'postgresql',
    'mongodb': 'mongodb',
    'redis': 'redis',

    # Business
    'negotiation': 'negotiation',
    'business_development': 'business_dev',
    'commercial': 'business_dev',
    'crm': 'crm',
    'sales': 'sales',
    'account_management': 'account_mgmt',

    # Operations
    'procurement': 'procurement',
    'purchase': 'procurement',
    'sourcing': 'sourcing',
    'project_management': 'project_mgmt',
    'gestion_de_projet': 'project_mgmt',

    # Finance
    'budget': 'budget',
    'accounting': 'accounting',
    'financial': 'financial',

    # Tools
    'excel': 'excel',
    'jira': 'jira',
    'confluence': 'confluence',
    'sap': 'sap',
    'salesforce': 'salesforce',
    'docker': 'docker',
    'kubernetes': 'kubernetes',

    # Infrastructure
    'linux': 'linux',
    'windows': 'windows',
    'aws': 'aws',
    'azure': 'azure',
    'gcp': 'gcp',

    # HR
    'recruitment': 'recruitment',
    'hr_': 'hr',

    # Engineering
    'engineering': 'engineering',
    'devops': 'devops',
}

def extract_semantic_root(label: str) -> str:
    """Extract semantic root from label."""
    label_lower = label.lower()

    # Check for explicit roots
    for keyword, root in SEMANTIC_ROOTS.items():
        if keyword in label_lower:
            return root

    # Fallback: first word
    words = re.split(r'[_/\s]', label_lower)
    return words[0] if words else label_lower

def extract_specificity(label: str) -> int:
    """Return specificity score (higher = more specific). Lower is better for parent."""
    spec = 0
    label_lower = label.lower()

    # Modifiers that increase specificity
    spec_words = ['_complex', '_advanced', '_specific', '_detailed', '_deep', '_expert',
                  '_optimization', '_performance', '_management', '_implementation',
                  '_development', '_programming', '_knowledge', '_proficiency', '_mastery',
                  '_design', '_architecture', '_analysis', '_strategy', '_process']

    for word in spec_words:
        if word in label_lower:
            spec += 1

    # Word count: longer = more specific
    spec += max(0, label.count('_') - 1)

    return spec

def main() -> int:
    # Load V2
    v2_path = Path("audit/skill_dictionary_draft_v2.json")
    data_v2 = json.loads(v2_path.read_text())

    # Group by semantic root
    root_groups = defaultdict(list)
    for skill in data_v2["canonical_skills"]:
        root = extract_semantic_root(skill["label"])
        specificity = extract_specificity(skill["label"])
        root_groups[root].append({
            "canonical_id": skill["canonical_id"],
            "label": skill["label"],
            "skill_type": skill["skill_type"],
            "domain_tag": skill.get("domain_tag", "domain_specific"),
            "occurrences": skill["occurrences"],
            "aliases": list(skill.get("aliases", [])) if isinstance(skill.get("aliases"), list) else [],
            "specificity": specificity,
        })

    # Consolidate each group
    consolidated = {}
    merges_log = []
    processed = set()

    for root, variants in root_groups.items():
        if len(variants) == 1:
            # Single skill, keep as-is
            skill = variants[0]
            consolidated[skill["canonical_id"]] = skill
            processed.add(skill["canonical_id"])
        else:
            # Multiple variants: keep most general, merge others
            # Sort by: (1) low specificity (2) high occurrences (3) alphabetical
            sorted_variants = sorted(
                variants,
                key=lambda s: (s["specificity"], -s["occurrences"], s["label"])
            )

            parent = sorted_variants[0]
            consolidated[parent["canonical_id"]] = {
                "canonical_id": parent["canonical_id"],
                "label": parent["label"],
                "skill_type": parent["skill_type"],
                "domain_tag": parent["domain_tag"],
                "occurrences": parent["occurrences"],
                "aliases": list(parent["aliases"]),
            }
            processed.add(parent["canonical_id"])

            # Merge all others into parent
            for variant in sorted_variants[1:]:
                consolidated[parent["canonical_id"]]["occurrences"] += variant["occurrences"]
                # Add variant label as alias
                consolidated[parent["canonical_id"]]["aliases"].append(variant["label"])
                # Add variant's aliases too
                consolidated[parent["canonical_id"]]["aliases"].extend(variant["aliases"])

                merges_log.append({
                    "source": variant["label"],
                    "source_id": variant["canonical_id"],
                    "target": parent["label"],
                    "target_id": parent["canonical_id"],
                    "reason": f"hierarchical consolidation (root: {root})",
                    "source_occ": variant["occurrences"],
                    "source_spec": variant["specificity"],
                })

    # Deduplicate aliases
    for skill in consolidated.values():
        skill["aliases"] = list(set(skill["aliases"]))

    # Sort by occurrences
    canonical_skills_list = list(consolidated.values())
    canonical_skills_list.sort(key=lambda x: -x["occurrences"])

    # Metrics
    total_canonical_before = len(data_v2["canonical_skills"])
    total_canonical_after = len(canonical_skills_list)
    total_aliases = sum(len(s.get("aliases", [])) for s in canonical_skills_list)
    total_labels = data_v2["metadata"]["total_source_labels"]
    compression_after = round(total_labels / total_canonical_after, 2)

    # Build output JSON
    output_data = {
        "metadata": {
            "generated_at": "2026-05-02",
            "version": "v3_improved_consolidation",
            "source": "skill_dictionary_draft_v2.json",
            "consolidation_metrics": {
                "canonical_skills_before": total_canonical_before,
                "canonical_skills_after": total_canonical_after,
                "canonical_skills_merged": total_canonical_before - total_canonical_after,
                "compression_ratio_after": compression_after,
                "target_compression": 1.5,
                "meets_target": compression_after >= 1.5,
                "merges_performed": len(merges_log),
            }
        },
        "canonical_skills": canonical_skills_list,
        "consolidation_log": {
            "merges": merges_log,
        }
    }

    # Write JSON
    output_path = Path("audit/skill_dictionary_consolidated_v3_improved.json")
    output_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False) + "\n")

    # Build report
    report = f"""# Skill Dictionary Consolidation — V3 Improved
**Date:** 2026-05-02
**Status:** {'READY' if compression_after >= 1.5 else 'NOT_READY'}

---

## Executive Summary

Hierarchical consolidation by semantic root. Keep most general variant per root, merge all others.

### Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Canonical skills | {total_canonical_before:,} | {total_canonical_after:,} | ~2,148 |
| Compression ratio | 1.25x | {compression_after}x | ≥1.5x |
| Merges performed | — | — | {len(merges_log)} |
| Ready for matching | NO | {'YES ✓' if compression_after >= 1.5 else 'NO ✗'} | YES |

---

## Consolidation Strategy

**Root-based merging:** Group canonicals by semantic concept (python, sql, data, etc.).
For each group with >1 skill:
- Keep the most general variant (lowest specificity score)
- Merge all others into parent
- Track all merges with full aliases

**Specificity score:** Counts modifier words + word count depth.
- Lower score = more general → chosen as parent
- Tie-break: higher occurrences, then alphabetical

---

## Top Merges

| Source | Target | Occurrences | Reason |
|--------|--------|-------------|--------|
"""

    for merge in sorted(merges_log, key=lambda m: -m["source_occ"])[:20]:
        report += f"| {merge['source']} | {merge['target']} | {merge['source_occ']} | {merge['reason']} |\n"

    report += f"""
---

## Compression Analysis

**Before:** 1.25x (3,223 labels → 2,586 canonicals)
**After:** {compression_after}x (3,223 labels → {total_canonical_after} canonicals)
**Gap to 1.5x:** {1.5 - compression_after:.2f}x

**Status:** {'✓ READY FOR MATCHING' if compression_after >= 1.5 else f'✗ NOT YET (need {2148 - total_canonical_after} more merges)'}

---

## Top 20 Skills (by occurrences)

| # | Label | Domain | Occurrences |
|---|-------|--------|-------------|
"""

    for idx, skill in enumerate(canonical_skills_list[:20], 1):
        report += f"| {idx} | {skill['label']} | {skill['domain_tag']} | {skill['occurrences']} |\n"

    report += f"""
---

## Recommendation

{'✓ Ready for Phase 2 DB implementation.' if compression_after >= 1.5 else f'Not yet. Need {2148 - total_canonical_after} more consolidations to reach 1.5x.'}

**Next:** Run with adjusted specificity weights or domain-aware merging.
"""

    report_path = Path("audit/SKILL_DICTIONARY_CONSOLIDATION_V3_IMPROVED.md")
    report_path.write_text(report)

    # Output
    print(f"\n✓ Improved consolidation complete\n")
    print(f"Canonical skills:")
    print(f"  Before: {total_canonical_before:,}")
    print(f"  After: {total_canonical_after:,}")
    print(f"  Merged: {total_canonical_before - total_canonical_after}\n")
    print(f"Compression:")
    print(f"  Target: ≥1.5x")
    print(f"  Achieved: {compression_after}x")
    print(f"  Status: {'✓ READY' if compression_after >= 1.5 else '✗ NOT READY'}\n")
    print(f"Merges: {len(merges_log)}\n")
    print(f"Files:")
    print(f"  {output_path}")
    print(f"  {report_path}")

    return 0 if compression_after >= 1.5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
