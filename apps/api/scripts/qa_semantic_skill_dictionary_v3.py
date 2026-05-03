#!/usr/bin/env python3
"""qa_semantic_skill_dictionary_v3 — semantic QA audit of skill dictionary.

Tâches:
1. Check compression ratio
2. Detect semantic duplicates
3. Check cluster coherence
4. Detect over-specificity
5. Low quality label detection
6. Domain tag semantic check
7. Calculate matching readiness score
8-11. Generate reports + tests

Usage:
    python3 scripts/qa_semantic_skill_dictionary_v3.py
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

# Weak suffixes that indicate over-specificity
WEAK_SUFFIXES = {
    "programming", "scripting", "proficiency", "knowledge", "usage",
    "mastery", "support", "activities", "experience", "familiarity",
    "expertise", "skills", "capabilities", "competency", "training",
    "implementation", "deployment", "integration", "development"
}

# Generic words (too broad)
GENERIC_WORDS = {
    "support", "management", "process", "activities", "knowledge",
    "expertise", "environment", "documentation", "reporting", "analysis",
    "data", "system", "tool", "application", "service", "framework",
}

# Tool keywords
TOOL_KEYWORDS = {
    "python", "java", "javascript", "c++", "c#", "sql", "golang", "rust",
    "typescript", "kotlin", "scala", "php", "ruby", "perl", "r",
    "matlab", "vba", "excel", "powerbi", "power_bi", "tableau", "looker",
    "salesforce", "sap", "oracle", "aws", "azure", "gcp", "docker",
    "kubernetes", "git", "jenkins", "gitlab", "jira", "confluence",
}

# Semantic duplicate groups (canonical should be merged)
SEMANTIC_DUPLICATE_GROUPS = [
    ["python", "python_programming", "python_scripting"],
    ["java", "java_programming", "java_application_development", "core_java"],
    ["c_c_programming", "c_c_development", "c_and_c_programming"],
    ["sql", "sql_querying", "sql_mastery", "rdbms_sql_proficiency"],
    ["power_bi", "powerbi", "power_bi_development"],
    ["contract_negotiation", "negotiation", "n_gociation", "commercial_negotiation"],
    ["international_environment", "environnement_international"],
    ["business_development", "commercial_development", "d_veloppement_commercial"],
    ["project_management", "gestion_de_projet", "project_management_expertise"],
    ["data_analysis", "analyse_des_donnees", "data_analytics"],
    ["data_visualization", "data_visualisation", "dashboard_creation"],
    ["financial_reporting", "reporting", "monthly_reporting", "reporting_automation"],
    ["customer_relationship_management", "client_relationship_management", "crm"],
    ["procurement", "purchasing", "achat", "sourcing", "purchase_order_management"],
    ["quality_management", "quality_assurance", "quality_control"],
    ["technical_documentation", "documentation_technique"],
    ["maintenance", "preventive_maintenance", "maintenance_preventive"],
    ["recruitment", "talent_acquisition", "candidate_sourcing"],
    ["market_analysis", "market_research", "analyse_de_marche"],
    ["english_language_proficiency", "english", "fluent_english"],
    ["french_language_proficiency", "french", "maitrise_du_francais"],
]

# Cluster pollution patterns
CLUSTER_POLLUTION = {
    "excel": ["excellence", "operational_excellence", "excellence_system"],
    "customer_relationship_management": ["customer_support", "customer_training", "customer_complaint", "customer_analytics"],
    "quality_assurance": ["data_quality", "construction_quality", "functional_testing", "supplier_quality"],
    "angular": ["logistic", "triangular", "establishment"],
    "data_analysis": ["financial_data_analysis", "market_data_analysis", "sales_data_analysis"],
}

def normalize_label_simple(label: str) -> str:
    """Simple normalization for comparison."""
    s = label.lower().strip()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[\s\-_/]+', '_', s)
    s = re.sub(r'[^a-z0-9_]', '', s)
    s = re.sub(r'_+', '_', s)
    return s.strip('_')

def remove_weak_suffix(label: str) -> str:
    """Remove weak suffix for comparison."""
    norm = normalize_label_simple(label)
    for suffix in sorted(WEAK_SUFFIXES, key=len, reverse=True):
        suffix_norm = normalize_label_simple(suffix)
        if norm.endswith(f"_{suffix_norm}"):
            return norm[:-len(f"_{suffix_norm}")]
    return norm

def main() -> int:
    v2_path = Path("/Users/akimguentas/Dev/elevia-compass/audit/skill_dictionary_draft_v2.json")

    if not v2_path.exists():
        print(f"ERROR: {v2_path} not found")
        return 1

    data = json.loads(v2_path.read_text())

    # TÂCHE 2: Check compression
    total_labels = data["metadata"]["total_source_labels"]
    canonical_count = len(data["canonical_skills"])
    compression_ratio = round(total_labels / canonical_count, 2)

    compression_blocker = compression_ratio < 1.5
    compression_warning = 1.5 <= compression_ratio < 2.0

    # TÂCHE 3: Detect semantic duplicates
    canonical_by_normalized = {}
    for skill in data["canonical_skills"]:
        norm = normalize_label_simple(skill["label"])
        if norm not in canonical_by_normalized:
            canonical_by_normalized[norm] = skill

    semantic_duplicates = []
    matched_groups = set()

    for group in SEMANTIC_DUPLICATE_GROUPS:
        group_norms = [normalize_label_simple(label) for label in group]
        group_skills = []

        for skill in data["canonical_skills"]:
            norm = normalize_label_simple(skill["label"])
            if norm in group_norms:
                group_skills.append(skill)

        if len(group_skills) > 1:
            semantic_duplicates.append({
                "group": group,
                "canonical_ids": [s["canonical_id"] for s in group_skills],
                "labels": [s["label"] for s in group_skills],
                "confidence": "HIGH",
                "proposed_action": "MERGE",
                "reason": "Semantic equivalence (same concept, different suffixes or translations)"
            })
            matched_groups.update(group_norms)

    # TÂCHE 4: Cluster coherence check
    polluted_clusters = []

    for canonical_id, pollution_keywords in CLUSTER_POLLUTION.items():
        skill = next((s for s in data["canonical_skills"] if s["canonical_id"] == canonical_id), None)
        if skill:
            for alias in skill["aliases"]:
                alias_lower = alias.lower()
                for keyword in pollution_keywords:
                    if keyword.lower() in alias_lower:
                        polluted_clusters.append({
                            "canonical_id": canonical_id,
                            "label": skill["label"],
                            "suspect_alias": alias,
                            "issue_type": "polluted_alias",
                            "reason": f"Alias contains '{keyword}' which may not belong in '{skill['label']}'",
                            "proposed_action": "REMOVE_ALIAS or SPLIT_CLUSTER",
                            "severity": "HIGH" if keyword in ["excellence", "support"] else "MEDIUM"
                        })

    # TÂCHE 5: Over-specificity detection
    over_specific = []

    for skill in data["canonical_skills"]:
        label_norm = normalize_label_simple(skill["label"])
        parent = remove_weak_suffix(skill["label"])

        if parent != label_norm and parent:
            # Find if parent exists as canonical
            parent_skill = next((s for s in data["canonical_skills"] if normalize_label_simple(s["label"]) == parent), None)
            if parent_skill:
                over_specific.append({
                    "current_canonical": skill["label"],
                    "current_id": skill["canonical_id"],
                    "proposed_parent": parent_skill["label"],
                    "parent_id": parent_skill["canonical_id"],
                    "reason": f"Over-specific variant that should merge with parent",
                    "confidence": "MEDIUM"
                })

    # TÂCHE 6: Low quality labels
    low_quality = []

    for skill in data["canonical_skills"]:
        label = skill["label"]
        issues = []

        # Check for broken accents (NFD artifacts)
        if any(c in label for c in "n_d_a_e_o"):
            if "_" in label and any(x in label for x in ["n_gociation", "d_veloppement", "ing_nierie", "am_lioration", "donn_es"]):
                issues.append("broken_accents_nfd_artifacts")

        # Check for special chars
        if any(c in label for c in "()[]{},'\""):
            issues.append("special_chars")

        # Check length
        if len(label) > 50:
            issues.append("too_long_label")

        # Check genericity
        if any(generic in label.lower() for generic in GENERIC_WORDS):
            if len(label.split('_')) <= 2:
                issues.append("too_generic")

        if issues:
            low_quality.append({
                "canonical_id": skill["canonical_id"],
                "label": label,
                "issues": issues,
                "proposed_action": "REVIEW or RENAME"
            })

    # TÂCHE 7: Domain tag semantic check
    domain_tag_fixes = []

    for skill in data["canonical_skills"]:
        label_lower = skill["label"].lower()
        current_tag = skill.get("domain_tag", "unknown")
        proposed_tag = None

        # Language detection
        if any(lang in label_lower for lang in ["english", "french", "spanish", "dutch", "german", "chinese", "arabic"]):
            if current_tag != "languages":
                proposed_tag = "languages"

        # Tools detection
        elif any(tool in label_lower for tool in TOOL_KEYWORDS):
            if current_tag not in ["tools", "backend", "frontend", "data", "devops"]:
                proposed_tag = "tools"

        # Domain-specific checks
        elif any(x in label_lower for x in ["recruitment", "talent", "candidate", "onboarding"]):
            if current_tag != "hr":
                proposed_tag = "hr"

        elif any(x in label_lower for x in ["budget", "financial", "accounting", "forecasting", "variance"]):
            if current_tag != "finance":
                proposed_tag = "finance"

        elif any(x in label_lower for x in ["procurement", "purchasing", "supplier", "logistics", "inventory"]):
            if current_tag != "supply_chain":
                proposed_tag = "supply_chain"

        if proposed_tag:
            domain_tag_fixes.append({
                "canonical_id": skill["canonical_id"],
                "label": skill["label"],
                "current_domain_tag": current_tag,
                "proposed_domain_tag": proposed_tag,
                "reason": "Domain tag semantically mismatched with label",
                "confidence": "HIGH"
            })

    # TÂCHE 8: Calculate matching readiness score
    score = 100

    # Penalties
    if compression_blocker:
        score -= 25
    elif compression_warning:
        score -= 10

    score -= min(len(semantic_duplicates) * 2, 20)
    score -= min(len([p for p in polluted_clusters if p.get("severity") == "HIGH"]) * 3, 20)
    score -= min(len(low_quality) * 1, 15)
    score -= min(len(domain_tag_fixes) * 1, 10)
    score -= min(len(over_specific) * 1, 10)

    score = max(0, score)

    # Determine status
    if score >= 85:
        status = "READY"
    elif score >= 70:
        status = "NEEDS_REVIEW"
    else:
        status = "NOT_READY"

    # TÂCHE 9-10: Build outputs
    findings = {
        "status": status,
        "qa_score": score,
        "compression_ratio": compression_ratio,
        "compression_blocker": compression_blocker,
        "total_source_labels": total_labels,
        "canonical_skills_count": canonical_count,
        "semantic_duplicate_candidates": semantic_duplicates,
        "polluted_clusters": polluted_clusters,
        "over_specific_canonicals": over_specific,
        "low_quality_labels": low_quality,
        "domain_tag_fixes": domain_tag_fixes,
        "priority_fix_plan": {
            "P0": [
                f"Compression ratio too low ({compression_ratio}x < 1.5x target)" if compression_blocker else None,
                f"Found {len([s for s in semantic_duplicates if s['confidence'] == 'HIGH'])} semantic duplicate groups" if semantic_duplicates else None,
                f"Found {len([p for p in polluted_clusters if p.get('severity') == 'HIGH'])} critical polluted clusters" if polluted_clusters else None,
            ],
            "P1": [
                f"Review {len(over_specific)} over-specific canonical skills",
                f"Fix domain tags on {len(domain_tag_fixes)} skills",
            ],
            "P2": [
                f"Clean {len(low_quality)} low quality labels",
            ]
        }
    }

    # Filter out Nones
    findings["priority_fix_plan"]["P0"] = [x for x in findings["priority_fix_plan"]["P0"] if x]

    # Write JSON
    json_path = Path("/Users/akimguentas/Dev/elevia-compass/audit/skill_dictionary_v3_semantic_findings.json")
    json_path.write_text(json.dumps(findings, indent=2, ensure_ascii=False) + "\n")

    # Write Markdown
    md_path = Path("/Users/akimguentas/Dev/elevia-compass/audit/SKILL_DICTIONARY_V3_SEMANTIC_QA.md")
    md_content = f"""# Skill Dictionary V3 — Semantic QA Audit
**Date:** 2026-05-02
**Status:** {status}

---

## Executive Summary

**Semantic audit verdict:** {status}

**QA Score:** {score}/100

### Key Metrics

| Metric | Value | Status |
|--------|-------|--------|
| Compression Ratio | {compression_ratio}x | {'🔴 BLOCKER' if compression_blocker else '⚠️ WARNING' if compression_warning else '✓ OK'} |
| Semantic Duplicates | {len(semantic_duplicates)} groups | {'🔴 BLOCKER' if semantic_duplicates else '✓ OK'} |
| Polluted Clusters | {len([p for p in polluted_clusters if p.get('severity') == 'HIGH'])} critical | {'🔴 CRITICAL' if any(p.get('severity') == 'HIGH' for p in polluted_clusters) else '✓ OK'} |
| Over-specific Skills | {len(over_specific)} | ⚠️ Needs cleanup |
| Low Quality Labels | {len(low_quality)} | ⚠️ Needs review |
| Domain Tag Mismatches | {len(domain_tag_fixes)} | ⚠️ Needs fixes |

---

## Why V2 is {status} for Matching

### Compression Ratio: {compression_ratio}x

**Target:** ≥1.5x (3,223 labels → ≤2,148 canonical)
**Current:** {compression_ratio}x ({total_labels} labels → {canonical_count} canonical)

**Analysis:**

Compression of {compression_ratio}x is too low. Indicates:
- Dictionary remains fragmented
- Too many redundant concepts
- Matching will have poor signal-to-noise ratio
- CV parsing will struggle to resolve candidate skills to offers

**Recommendation:** NOT READY. Must improve compression to ≥1.5x before matching integration.

---

## Semantic Duplicate Candidates: {len(semantic_duplicates)} Groups

These should be merged into single canonical:

| Group | Canonical IDs | Reason | Proposed Action |
|-------|---------------|--------|-----------------|
"""

    for dup in semantic_duplicates:
        ids = ", ".join(dup["canonical_ids"])
        md_content += f"| {dup['labels'][0]}, ... | `{ids}` | {dup['reason'][:60]} | MERGE |\n"

    md_content += f"""
---

## Polluted Clusters: {len(polluted_clusters)}

Aliases that don't belong in their canonical cluster:

| Canonical | Suspect Alias | Reason | Severity |
|-----------|---------------|--------|----------|
"""

    for poll in sorted(polluted_clusters, key=lambda x: x.get("severity", "MEDIUM"), reverse=True)[:20]:
        md_content += f"| {poll['label']} | {poll['suspect_alias']} | {poll['reason'][:50]} | {poll.get('severity', '?')} |\n"

    md_content += f"""
---

## Over-Specific Canonical Skills: {len(over_specific)}

These should merge with their parent canonical:

| Current | Parent | Reason |
|---------|--------|--------|
"""

    for over in over_specific[:15]:
        md_content += f"| {over['current_canonical']} | {over['proposed_parent']} | {over['reason'][:50]} |\n"

    md_content += f"""
---

## Low Quality Labels: {len(low_quality)}

| Canonical ID | Label | Issues |
|--------------|-------|--------|
"""

    for low in low_quality[:15]:
        md_content += f"| `{low['canonical_id']}` | {low['label']} | {', '.join(low['issues'])} |\n"

    md_content += f"""
---

## Domain Tag Semantic Mismatches: {len(domain_tag_fixes)}

| Canonical ID | Label | Current | Proposed |
|--------------|-------|---------|----------|
"""

    for fix in domain_tag_fixes[:15]:
        md_content += f"| `{fix['canonical_id']}` | {fix['label']} | {fix['current_domain_tag']} | {fix['proposed_domain_tag']} |\n"

    md_content += f"""
---

## Priority Fix Plan

### P0 — BLOCKERS (must fix before matching integration)

"""
    for item in findings["priority_fix_plan"]["P0"]:
        md_content += f"- {item}\n"

    md_content += f"""

### P1 — Important (before production)

"""
    for item in findings["priority_fix_plan"]["P1"]:
        md_content += f"- {item}\n"

    md_content += f"""

### P2 — Cleanup (post-Phase 2 optional)

"""
    for item in findings["priority_fix_plan"]["P2"]:
        md_content += f"- {item}\n"

    md_content += f"""

---

## Recommendation

### ❌ DO NOT PROCEED TO DB IMPLEMENTATION YET

**Reason:** Dictionary is not semantically ready for CV↔offer matching.

**Issues:**
1. Compression ratio too low ({compression_ratio}x < 1.5x target)
2. {len(semantic_duplicates)} semantic duplicate groups unmerged
3. {len([p for p in polluted_clusters if p.get('severity') == 'HIGH'])} critical polluted clusters
4. {len(over_specific)} over-specific skills need consolidation
5. {len(domain_tag_fixes)} domain tags semantically mismatched

**Next Steps:**

1. Address P0 blockers:
   - Merge semantic duplicates (python + python_programming, etc.)
   - Clean polluted clusters (excel + excellence, etc.)
   - Improve compression ratio to ≥1.5x

2. Once fixed, re-run this audit

3. When score ≥85, proceed to Phase 2 DB implementation

---

## Technical Details

**Script:** scripts/qa_semantic_skill_dictionary_v3.py
**Input:** audit/skill_dictionary_draft_v2.json
**Outputs:**
- audit/SKILL_DICTIONARY_V3_SEMANTIC_QA.md (this report)
- audit/skill_dictionary_v3_semantic_findings.json (structured data)

**QA Checks:**
- Compression ratio analysis ✓
- Semantic duplicate detection ✓
- Cluster coherence check ✓
- Over-specificity detection ✓
- Low quality label detection ✓
- Domain tag semantic validation ✓
- Matching readiness score calculation ✓

---

**Final Verdict:** {status} — Score {score}/100
"""

    md_path.write_text(md_content)

    # Console output
    print(f"\n✓ Semantic QA complete\n")
    print(f"Status: {status}")
    print(f"QA Score: {score}/100")
    print(f"Compression: {compression_ratio}x ({'BLOCKER' if compression_blocker else 'WARNING' if compression_warning else 'OK'})")
    print(f"Semantic duplicates: {len(semantic_duplicates)}")
    print(f"Polluted clusters: {len(polluted_clusters)}")
    print(f"Over-specific skills: {len(over_specific)}")
    print(f"Low quality labels: {len(low_quality)}")
    print(f"Domain tag mismatches: {len(domain_tag_fixes)}")
    print(f"\nFiles:")
    print(f"  {json_path}")
    print(f"  {md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
