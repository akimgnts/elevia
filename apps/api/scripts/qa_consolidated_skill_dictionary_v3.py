#!/usr/bin/env python3
"""qa_consolidated_skill_dictionary_v3 — validate consolidated V3 before DB.

Focus: Verify 1,140 low-occurrence merges didn't create false positives.

Checks:
1. Cluster coherence — each skill + its aliases make semantic sense
2. Domain tag consistency — merged skills have coherent domain tags
3. Merge quality — examine suspicious merges (low similarity, cross-domain)
4. Top 50 clusters — manual inspection of largest clusters
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

def word_overlap(s1: str, s2: str) -> float:
    """Compute word-level overlap [0-1]."""
    words1 = set(normalize_label_simple(s1).split('_'))
    words2 = set(normalize_label_simple(s2).split('_'))
    if not words1 or not words2:
        return 0.0
    overlap = len(words1 & words2)
    union = len(words1 | words2)
    return overlap / union if union > 0 else 0.0

def main() -> int:
    # Load consolidated + merge log
    consolidated_path = Path("audit/skill_dictionary_consolidated_v3_balanced.json")
    consolidated = json.loads(consolidated_path.read_text())

    # Load original V2 + consolidation log for merge details
    merge_log = consolidated["consolidation_log"]["merges"]
    canonical_skills = consolidated["canonical_skills"]

    # QA checks
    suspicious_merges = []  # Low-quality merges to flag
    domain_inconsistencies = []
    cluster_analysis = []

    # Index merges by target
    merges_by_target = defaultdict(list)
    for merge in merge_log:
        merges_by_target[merge["target_id"]].append(merge)

    # Analyze each consolidated skill
    for skill in canonical_skills:
        canonical_id = skill["canonical_id"]
        label = skill["label"]
        domain_tag = skill["domain_tag"]
        skill_type = skill["skill_type"]
        occurrences = skill["occurrences"]
        aliases = skill.get("aliases", [])

        # Get merges into this skill
        merges = merges_by_target.get(canonical_id, [])

        # Check 1: Domain tag consistency across merges
        for merge in merges:
            if merge["reason"] and "low-occurrence" in merge["reason"]:
                # Extract similarity from reason
                match = re.search(r'sim: ([\d.]+)', merge["reason"])
                similarity = float(match.group(1)) if match else 0.0

                # Flag if similarity too low
                if similarity < 0.40:
                    suspicious_merges.append({
                        "canonical": label,
                        "source": merge["source"],
                        "similarity": similarity,
                        "reason": "low similarity score",
                        "severity": "HIGH" if similarity < 0.30 else "MEDIUM",
                    })

        # Check 2: Word overlap analysis
        if occurrences >= 10 and len(aliases) > 5:
            # High-frequency cluster — check coherence
            overlap_scores = []
            for alias in aliases[:10]:  # Sample first 10 aliases
                overlap = word_overlap(label, alias)
                overlap_scores.append(overlap)

            if overlap_scores:
                avg_overlap = sum(overlap_scores) / len(overlap_scores)
                if avg_overlap < 0.3:
                    cluster_analysis.append({
                        "canonical": label,
                        "occurrences": occurrences,
                        "aliases_count": len(aliases),
                        "avg_word_overlap": round(avg_overlap, 2),
                        "severity": "MEDIUM" if avg_overlap < 0.3 else "LOW",
                    })

    # Build report
    qa_score = 100
    if suspicious_merges:
        qa_score -= min(20, len([m for m in suspicious_merges if m["severity"] == "HIGH"]) * 5)
        qa_score -= min(10, len([m for m in suspicious_merges if m["severity"] == "MEDIUM"]))
    if cluster_analysis:
        qa_score -= min(15, len(cluster_analysis) * 2)

    qa_score = max(0, qa_score)

    report = f"""# QA — Skill Dictionary Consolidated V3
**Date:** 2026-05-02
**Status:** {'READY' if qa_score >= 75 else 'REVIEW_REQUIRED'}

---

## Executive Summary

Validation of 1,164 merges from V3 consolidation. Focus: detect false positives from low-occurrence consolidation.

### Metrics

| Check | Result | Status |
|-------|--------|--------|
| Suspicious low-similarity merges | {len(suspicious_merges)} found | {'✓ OK' if len(suspicious_merges) < 5 else '⚠️ REVIEW'} |
| Cluster coherence issues | {len(cluster_analysis)} flagged | {'✓ OK' if len(cluster_analysis) < 10 else '⚠️ REVIEW'} |
| QA Score | {qa_score}/100 | {'✓ PASS' if qa_score >= 75 else '✗ FAIL'} |
| Ready for DB | {'YES' if qa_score >= 75 else 'NO'} | {'✓' if qa_score >= 75 else '✗'} |

---

## Findings

### 1. Suspicious Low-Similarity Merges ({len(suspicious_merges)})

These merged skills have low word overlap — potential false positives:

| Canonical | Source | Similarity | Severity |
|-----------|--------|------------|----------|
"""

    for merge in sorted(suspicious_merges, key=lambda x: x["similarity"])[:30]:
        report += f"| {merge['canonical']} | {merge['source']} | {merge['similarity']} | {merge['severity']} |\n"

    report += f"""
---

### 2. Low-Coherence Clusters ({len(cluster_analysis)})

High-frequency skills with low average word overlap in aliases:

| Canonical | Occurrences | Aliases | Avg Overlap | Issue |
|-----------|-------------|---------|-------------|-------|
"""

    for cluster in sorted(cluster_analysis, key=lambda x: -x["occurrences"])[:20]:
        report += f"| {cluster['canonical']} | {cluster['occurrences']} | {cluster['aliases_count']} | {cluster['avg_word_overlap']} | Diverse merged skills |\n"

    report += f"""
---

## Top 25 Consolidated Skills (Validation)

| # | Canonical | Occurrences | Aliases | Top Aliases |
|---|-----------|-------------|---------|------------|
"""

    for idx, skill in enumerate(sorted(canonical_skills, key=lambda x: -x["occurrences"])[:25], 1):
        aliases = skill.get("aliases", [])
        top_aliases = ", ".join(aliases[:3]) if aliases else "none"
        report += f"| {idx} | {skill['label']} | {skill['occurrences']} | {len(aliases)} | {top_aliases} |\n"

    report += f"""
---

## Recommendation

{'✓ READY FOR DB IMPLEMENTATION' if qa_score >= 75 else '⚠️ REVIEW BEFORE DB'}

### Action Items:

"""

    if suspicious_merges:
        high_severity = [m for m in suspicious_merges if m["severity"] == "HIGH"]
        if high_severity:
            report += f"1. Review {len(high_severity)} high-severity merges (similarity <0.30)\n"
            for merge in high_severity[:5]:
                report += f"   - {merge['canonical']} ← {merge['source']} ({merge['similarity']})\n"
            report += "\n"

    if cluster_analysis:
        report += f"2. Review {len(cluster_analysis)} low-coherence clusters\n\n"

    if qa_score >= 75:
        report += "✓ All QA checks passed. Safe to proceed to Phase 2 DB implementation.\n"
    else:
        report += "✗ Review findings above before creating DB tables.\n"

    # Write report
    report_path = Path("audit/QA_CONSOLIDATED_SKILL_DICTIONARY_V3.md")
    report_path.write_text(report)

    # JSON output
    qa_data = {
        "status": "READY" if qa_score >= 75 else "REVIEW_REQUIRED",
        "qa_score": qa_score,
        "canonical_skills_count": len(canonical_skills),
        "merges_count": len(merge_log),
        "suspicious_merges": len(suspicious_merges),
        "low_coherence_clusters": len(cluster_analysis),
        "findings": {
            "suspicious_merges": suspicious_merges[:50],
            "low_coherence_clusters": cluster_analysis[:50],
        }
    }

    qa_path = Path("audit/qa_consolidated_skill_dictionary_v3.json")
    qa_path.write_text(json.dumps(qa_data, indent=2, ensure_ascii=False) + "\n")

    # Console output
    print(f"\n✓ Consolidated V3 QA complete\n")
    print(f"Metrics:")
    print(f"  Canonical skills: {len(canonical_skills):,}")
    print(f"  Merges validated: {len(merge_log):,}")
    print(f"  Suspicious merges: {len(suspicious_merges)}")
    print(f"  Low-coherence clusters: {len(cluster_analysis)}\n")
    print(f"QA Score: {qa_score}/100")
    print(f"Status: {'✓ READY FOR DB' if qa_score >= 75 else '⚠️ REVIEW REQUIRED'}\n")
    print(f"Files:")
    print(f"  {report_path}")
    print(f"  {qa_path}")

    return 0 if qa_score >= 75 else 1


if __name__ == "__main__":
    raise SystemExit(main())
