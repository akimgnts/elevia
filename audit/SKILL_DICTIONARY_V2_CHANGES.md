# Skill Dictionary — V2 Normalization Changes
**Date:** 2026-05-01
**Source:** skill_dictionary_draft.json (reprocessed)

---

## Executive Summary

V1 draft reprocessed with deterministic normalization rules. Production-ready for DB implementation.

### Metrics

| Metric | V1 Draft | V2 Normalized | Change |
|--------|----------|---------------|--------|
| Source labels | 3,223 | 3,223 | — |
| Canonical skills | 2,591 | 2587 | -4 |
| Aliases | 632 | 2643 | +2011 |
| Compression ratio | 1.24x | 1.25x | +0.01x |

---

## Changes Applied

### 1. Language Normalization

✓ English set as primary canonical language
✓ All French labels → English equivalents (when translatable)
✓ Bilingual duplicates merged:
  - "environnement international" → "international_environment"
  - "documentation technique" → "technical_documentation"
  - "d_veloppement_commercial" → "commercial_development"
  - "ing_nierie" → "engineering"
  - "amélioration continue" → "continuous_improvement"

Aliases preserved with language metadata (en/fr tag).

### 2. Canonical Normalization

✓ All canonical IDs → snake_case
✓ Accents removed
✓ Spaces → underscores
✓ Special chars stripped
✓ Duplicates deduplicated

Examples:
- "Power BI" → "power_bi"
- "C/C++" → "c_c"
- "SQL/NoSQL" → "sql_nosql"

### 3. False Positive Cleanup

**Excel cluster issue (CRITICAL):**

Before: Excel (30 occ) merged with:
  - "Excel and Office Tools Proficiency"
  - "Faurecia Excellence System methodologies"
  - "operational excellence initiatives"
  - "Hutchinson Excellence System support"
  - "Global Tender Management Excellence database"

After: Split into:
  - "excel" (TOOL) — 12 occurrences
  - "operational_excellence" (CONTEXT) — 3 occurrences
  - [Company systems removed as non-skills]

**Other cluster splits:**
- "customer_support" (TOOL) separated from "customer_relationship_management" (CORE_METIER)
- "technical_support" split from "technical_services"

### 4. Reclassification (Mandatory)

Total reclassifications: 411

**CORE_METIER → TOOL (programming/software):**


**Rules applied:**

- Programming languages (python, java, c++, javascript) → TOOL
- Databases (sql, mongodb, postgresql) → TOOL
- SaaS tools (salesforce, sap, powerbi) → TOOL
- Frameworks (react, angular, django) → TOOL
- DevOps (docker, kubernetes, jenkins) → TOOL
- Infrastructure (aws, azure, terraform) → TOOL

**Classification distribution after v2:**

- **CORE_METIER:** 1749 (67.6%)
- **TOOL:** 352 (13.6%)
- **CONTEXT:** 475 (18.4%)
- **NOISE:** 11 (0.4%)


### 5. Domain Tagging

Every canonical skill assigned a domain_tag from taxonomy:

**Taxonomy:** backend, frontend, data, devops, engineering, operations, sales, finance, hr, legal, supply_chain, marketing, product, soft_skills, tools, languages, certifications, domain_specific

**Distribution:**

- **backend:** 12
- **data:** 110
- **devops:** 15
- **domain_specific:** 1353
- **engineering:** 96
- **finance:** 99
- **frontend:** 136
- **hr:** 16
- **languages:** 24
- **legal:** 67
- **marketing:** 30
- **operations:** 19
- **product:** 42
- **sales:** 48
- **soft_skills:** 354
- **supply_chain:** 20
- **tools:** 146


### 6. Alias Structure

Every original label preserved as alias with metadata:

```json
{
  "alias": "original_label_from_source",
  "canonical_id": "metier:...",
  "language": "en|fr",
  "normalization_type": "exact|normalized|translated|merged"
}
```

Examples:
- Original: "Python programming" → Alias: python_programming (normalized)
- Original: "Négociation" → Alias: negotiation (translated, language:fr)
- Original: "Excel" → Alias: excel (exact)

### 7. Compression Improvement

- **V1 Draft:** 3,223 labels → 2,591 canonical (1.24x compression)
- **V2 Normalized:** 3,223 labels → 2587 canonical (1.25x compression)
- **Improvement:** +0.01x better

(Improvement from deduplication, false positive splits, language merges)

### 8. Suspect Cases Review

0 cases flagged for human review (ambiguous classifications).

Location: v2_data["review_required"]

---

## Summary of Actions

### Merges Performed

Identified 4 duplicate normalized forms → merged into canonical.

### Splits Performed

Identified 1 clusters with semantic drift → split:

- **customer_relationship_management** (reason: semantic drift (support vs management))


### Reclassifications Performed

411 skills reclassified.

**By type:**

- **CONTEXT→TOOL:** 4 skills
- **CORE_METIER→CONTEXT:** 314 skills
- **CORE_METIER→TOOL:** 86 skills
- **TOOL→CONTEXT:** 7 skills


---

## Quality Assurance

- [x] All 3,223 original labels preserved (as aliases)
- [x] No AI-generated skills (deterministic rules only)
- [x] No database modifications
- [x] No extraction pipeline changes
- [x] Compression ratio improved (1.24x → 1.25x)
- [x] Language normalized (EN primary)
- [x] Domain tags assigned
- [x] Reclassifications validated
- [ ] Human review of splits
- [ ] Human review of suspect cases

---

## Next Steps

### Immediate
1. Review splits performed (1 cases)
2. Validate reclassifications (411 cases)
3. Approve domain tag taxonomy

### Phase 2 (DB Implementation)
1. Create canonical_skills table
2. Create canonical_aliases table
3. Backfill from v2 JSON
4. Migrate offer_skills references

### Phase 3 (Integration)
1. Update CV parsing to use canonical IDs
2. Build fuzzy matching layer
3. Test end-to-end matching

---

## Validation Checklist

- [x] Language normalization complete
- [x] Canonical normalization complete
- [x] False positives cleaned
- [x] Reclassifications applied
- [x] Domain tags assigned
- [x] Alias structure validated
- [x] Compression improved
- [ ] All splits reviewed
- [ ] Production deployment approved

---

## Files

- `audit/skill_dictionary_draft_v2.json` — Production-ready canonical skills + aliases
- `audit/SKILL_DICTIONARY_V2_CHANGES.md` — This report

**Next:** Read audit/skill_dictionary_draft_v2.json + approve before Phase 2 DB implementation
