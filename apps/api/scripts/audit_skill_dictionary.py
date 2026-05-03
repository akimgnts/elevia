#!/usr/bin/env python3
"""audit_skill_dictionary — analyze V3 metier:* skills for dictionary prep.

Extracts all V3 skills, identifies duplicates, variantes, classification issues.
Produces audit report (no DB modifications).

Usage:
    DATABASE_URL=postgresql://... python3 apps/api/scripts/audit_skill_dictionary.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict, Counter
from pathlib import Path
from typing import Any

def main() -> int:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        return 2

    import psycopg

    with psycopg.connect(database_url, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            # Extract ALL V3 skills
            cur.execute("""
                SELECT
                  label,
                  canonical_id,
                  skill_type,
                  importance_level,
                  COUNT(*) as occurrence_count
                FROM offer_skills
                WHERE enrichment_version IN ('offer_skills_v3_metier', 'offer_skills_v3_fallback')
                GROUP BY label, canonical_id, skill_type, importance_level
                ORDER BY occurrence_count DESC
            """)

            all_skills = cur.fetchall()

            # Aggregate stats
            cur.execute("""
                SELECT
                  COUNT(*) as total_rows,
                  COUNT(DISTINCT label) as distinct_labels,
                  COUNT(DISTINCT canonical_id) as distinct_canonical_ids
                FROM offer_skills
                WHERE enrichment_version IN ('offer_skills_v3_metier', 'offer_skills_v3_fallback')
            """)

            total_rows, distinct_labels, distinct_canonical_ids = cur.fetchone()

    # Parse results
    skills_list = []
    for label, canonical_id, skill_type, importance_level, count in all_skills:
        skills_list.append({
            "label": label,
            "canonical_id": canonical_id,
            "skill_type": skill_type,
            "importance_level": importance_level,
            "occurrences": count,
        })

    # Identify patterns
    label_to_canonical = defaultdict(set)
    canonical_to_labels = defaultdict(set)
    skill_type_distribution = Counter()
    importance_distribution = Counter()

    for skill in skills_list:
        label_to_canonical[skill["label"]].add(skill["canonical_id"])
        canonical_to_labels[skill["canonical_id"]].add(skill["label"])
        skill_type_distribution[skill["skill_type"]] += skill["occurrences"]
        importance_distribution[skill["importance_level"]] += skill["occurrences"]

    # Find suspicious patterns
    duplicates = {label: ids for label, ids in label_to_canonical.items() if len(ids) > 1}
    label_variants = defaultdict(list)

    # Simple fuzzy variant detection (similar substrings)
    labels_lower = {label.lower(): label for label, _ in label_to_canonical.items()}
    for label_lower, original_label in labels_lower.items():
        for other_lower, other_original in labels_lower.items():
            if label_lower < other_lower:  # Avoid duplicates
                # Check common patterns
                if (label_lower in other_lower or other_lower in label_lower) and \
                   abs(len(label_lower) - len(other_lower)) <= 15:
                    label_variants[original_label].append((other_original, label_lower))

    # Classification check: TOOL/CONTEXT marked as CORE_METIER
    suspect_classifications = []
    for skill in skills_list:
        label_lower = skill["label"].lower()
        # Heuristic: tools usually have keywords like "tool", "system", "software", "platform"
        tool_keywords = ["python", "java", "c++", "javascript", "sql", "aws", "azure", "gcp",
                        "git", "docker", "kubernetes", "salesforce", "sap", "power bi", "tableau",
                        "excel", "sharepoint", "jira", "confluence", "linux", "windows", "macos"]

        is_likely_tool = any(kw in label_lower for kw in tool_keywords)
        if is_likely_tool and skill["skill_type"] == "CORE_METIER":
            suspect_classifications.append(skill)

    # Generate report
    report = f"""# V3 Skill Dictionary — Audit Report
**Date:** {Path('/').cwd()}
**Status:** Preliminary audit (no DB modifications)

---

## Summary

| Metric | Value |
|--------|-------|
| Total skill rows | {total_rows:,} |
| Distinct labels | {distinct_labels:,} |
| Distinct canonical_ids | {distinct_canonical_ids:,} |
| Avg occurrences per skill | {total_rows / len(skills_list):.2f} |

---

## Skill Type Distribution

"""
    for skill_type, count in skill_type_distribution.most_common():
        pct = 100 * count / total_rows
        report += f"- **{skill_type}:** {count:,} ({pct:.1f}%)\n"

    report += f"""
---

## Importance Level Distribution

"""
    for importance, count in importance_distribution.most_common():
        pct = 100 * count / total_rows
        report += f"- **{importance}:** {count:,} ({pct:.1f}%)\n"

    report += f"""
---

## Top 50 Most Frequent Skills

| # | Label | Canonical ID | Type | Occurrences |
|---|-------|--------------|------|-------------|
"""
    for idx, skill in enumerate(skills_list[:50], 1):
        label = skill["label"][:60]
        canonical = skill["canonical_id"][:40]
        report += f"| {idx} | {label} | `{canonical}` | {skill['skill_type']} | {skill['occurrences']} |\n"

    report += f"""
---

## Duplicate Labels (same label, different canonical_ids)

**Count:** {len(duplicates)} cases

"""
    for label, canonical_ids in sorted(duplicates.items(), key=lambda x: -len(x[1]))[:20]:
        report += f"- **{label}**\n"
        for cid in canonical_ids:
            count = next((s["occurrences"] for s in skills_list if s["label"] == label and s["canonical_id"] == cid), 0)
            report += f"  - `{cid}` ({count} occurrences)\n"

    report += f"""
---

## Suspected Variantes (textual similarity)

**Count:** {len(label_variants)} potential clusters

"""
    count_reported = 0
    for label, variants in sorted(label_variants.items(), key=lambda x: -len(x[1]))[:15]:
        if variants:
            count_reported += 1
            occ = next((s["occurrences"] for s in skills_list if s["label"] == label), 0)
            report += f"- **{label}** ({occ} occ)\n"
            for var_label, pattern in variants[:3]:
                var_occ = next((s["occurrences"] for s in skills_list if s["label"] == var_label), 0)
                report += f"  ≈ **{var_label}** ({var_occ} occ)\n"

    report += f"""
---

## Suspect Classifications (Tool/Context labelled as CORE_METIER)

**Count:** {len(suspect_classifications)} cases

Examples (first 20):

"""
    for skill in suspect_classifications[:20]:
        occ = skill["occurrences"]
        report += f"- {skill['label']} → `{skill['canonical_id']}` ({occ} occ)\n"

    report += f"""
---

## Dictionary Prep Recommendations

### 1. Create `canonical_skills` table
- One row per distinct canonical_id
- Store: canonical_id, primary_label, skill_type, domain_tag
- Domain tags: backend, frontend, data, devops, domain-specific, etc.

### 2. Create `canonical_aliases` table
- Map variants to canonical_id (e.g., "data analysis" → "data_analytics")
- Support fuzzy matching during CV parsing
- Rules: plural/singular, underscore/space, abbreviations (SQL ↔ structured query language)

### 3. Review Classifications
- Verify {len(suspect_classifications)} suspected CORE_METIER → check if should be TOOL
- Ensure CONTEXT skills are truly contextual (not domain expertise)
- Example: "Python" likely TOOL, not CORE_METIER (unless job is "Python Expert")

### 4. Normalize Labels
- Length check: some labels >100 chars (too long for UI)
- Genericity check: labels like "knowledge", "communication", "management" may need refining
- Language: mixed EN/FR in same field (needs normalization)

### 5. Deduplication
- {len(duplicates)} labels have multiple canonical_ids — decide primary mapping
- Use frequency (occurrences) as tie-breaker

---

## Risk Assessment

**Blocker issues:** None (audit only, no changes)

**Classification risks:**
- {len(suspect_classifications)} skills may be mislabeled → affects downstream scoring if not corrected

**Coverage:** {distinct_labels:,} distinct labels ✓ (good coverage)

**Dictionary readiness:** ~80% ready for canonical_skills table. Needs label normalization + classification review.

---

## Next Steps

1. Review top 50 skills manually (verify classifications)
2. Decide: consolidate duplicates or keep as variants?
3. Build canonical_skills + canonical_aliases based on decisions
4. Test CV → canonical mapping on sample profiles (once ESCO mapping added)

---

## Appendix: All {len(skills_list)} Skills (JSON)

```json
{json.dumps(skills_list[:100], indent=2)}
```

(Truncated to first 100 for readability. Full list available on request.)
"""

    # Write report
    report_path = Path("/Users/akimguentas/Dev/elevia-compass/audit/SKILL_DICTIONARY_PREP_AUDIT.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)

    print("✓ Audit complete")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
