# Skill Dictionary V3 — Semantic QA Audit
**Date:** 2026-05-02
**Status:** NOT_READY

---

## Executive Summary

**Semantic audit verdict:** NOT_READY

**QA Score:** 22/100

### Key Metrics

| Metric | Value | Status |
|--------|-------|--------|
| Compression Ratio | 1.25x | 🔴 BLOCKER |
| Semantic Duplicates | 15 groups | 🔴 BLOCKER |
| Polluted Clusters | 0 critical | ✓ OK |
| Over-specific Skills | 8 | ⚠️ Needs cleanup |
| Low Quality Labels | 222 | ⚠️ Needs review |
| Domain Tag Mismatches | 1786 | ⚠️ Needs fixes |

---

## Why V2 is NOT_READY for Matching

### Compression Ratio: 1.25x

**Target:** ≥1.5x (3,223 labels → ≤2,148 canonical)
**Current:** 1.25x (3223 labels → 2586 canonical)

**Analysis:**

Compression of 1.25x is too low. Indicates:
- Dictionary remains fragmented
- Too many redundant concepts
- Matching will have poor signal-to-noise ratio
- CV parsing will struggle to resolve candidate skills to offers

**Recommendation:** NOT READY. Must improve compression to ≥1.5x before matching integration.

---

## Semantic Duplicate Candidates: 15 Groups

These should be merged into single canonical:

| Group | Canonical IDs | Reason | Proposed Action |
|-------|---------------|--------|-----------------|
| python_programming, ... | `metier:python_programming, metier:python, metier:python_scripting` | Semantic equivalence (same concept, different suffixes or tr | MERGE |
| java, ... | `metier:java, metier:java_programming, metier:java_application_development` | Semantic equivalence (same concept, different suffixes or tr | MERGE |
| c/c++_programming, ... | `metier:c_c_programming, metier:c_and_c_programming, metier:c_c_development` | Semantic equivalence (same concept, different suffixes or tr | MERGE |
| rdbms/sql_proficiency, ... | `metier:rdbms_sql_proficiency, metier:sql_mastery, metier:sql_querying` | Semantic equivalence (same concept, different suffixes or tr | MERGE |
| power_bi, ... | `metier:power_bi, metier:powerbi, metier:power_bi_development` | Semantic equivalence (same concept, different suffixes or tr | MERGE |
| contract_negotiation, ... | `metier:contract_negotiation, metier:n_gociation, metier:commercial_negotiation` | Semantic equivalence (same concept, different suffixes or tr | MERGE |
| business_development, ... | `metier:business_development, metier:commercial_development` | Semantic equivalence (same concept, different suffixes or tr | MERGE |
| project_management, ... | `metier:project_management, metier:gestion_de_projet` | Semantic equivalence (same concept, different suffixes or tr | MERGE |
| data_analysis, ... | `metier:data_analysis, metier:analyse_des_donn_es` | Semantic equivalence (same concept, different suffixes or tr | MERGE |
| dashboard_creation, ... | `metier:dashboard_creation, metier:data_visualisation` | Semantic equivalence (same concept, different suffixes or tr | MERGE |
| financial_reporting, ... | `metier:financial_reporting, metier:monthly_reporting, metier:reporting_automation` | Semantic equivalence (same concept, different suffixes or tr | MERGE |
| customer_relationship_management, ... | `metier:customer_relationship_management, metier:client_relationship_management` | Semantic equivalence (same concept, different suffixes or tr | MERGE |
| procurement, ... | `metier:procurement, metier:purchase_order_management` | Semantic equivalence (same concept, different suffixes or tr | MERGE |
| candidate_sourcing, ... | `metier:candidate_sourcing, metier:talent_acquisition` | Semantic equivalence (same concept, different suffixes or tr | MERGE |
| market_analysis, ... | `metier:market_analysis, metier:market_research, metier:analyse_de_march` | Semantic equivalence (same concept, different suffixes or tr | MERGE |

---

## Polluted Clusters: 0

Aliases that don't belong in their canonical cluster:

| Canonical | Suspect Alias | Reason | Severity |
|-----------|---------------|--------|----------|

---

## Over-Specific Canonical Skills: 8

These should merge with their parent canonical:

| Current | Parent | Reason |
|---------|--------|--------|
| python_programming | python | Over-specific variant that should merge with paren |
| java_programming | java | Over-specific variant that should merge with paren |
| python_scripting | python | Over-specific variant that should merge with paren |
| erp_deployment | erp | Over-specific variant that should merge with paren |
| jira_knowledge | jira | Over-specific variant that should merge with paren |
| power_bi_capabilities | power_bi | Over-specific variant that should merge with paren |
| power_bi_development | power_bi | Over-specific variant that should merge with paren |
| industrial_environment_experience | industrial_environment | Over-specific variant that should merge with paren |

---

## Low Quality Labels: 222

| Canonical ID | Label | Issues |
|--------------|-------|--------|
| `metier:international_environment` | international_environment | too_generic |
| `metier:data_analysis` | data_analysis | too_generic |
| `metier:technical_documentation` | technical_documentation | too_generic |
| `metier:project_management` | project_management | too_generic |
| `metier:market_analysis` | market_analysis | too_generic |
| `metier:financial_reporting` | financial_reporting | too_generic |
| `metier:budget_management` | budget_management | too_generic |
| `metier:contract_management` | contract_management | too_generic |
| `metier:account_management` | account_management | too_generic |
| `metier:technical_support` | technical_support | too_generic |
| `metier:kpi_analysis` | kpi_analysis | too_generic |
| `metier:support_technique` | support_technique | too_generic |
| `metier:agile_environment` | agile_environment | too_generic |
| `metier:change_management` | change_management | too_generic |
| `metier:database_management` | database_management | too_generic |

---

## Domain Tag Semantic Mismatches: 1786

| Canonical ID | Label | Current | Proposed |
|--------------|-------|---------|----------|
| `metier:international_environment` | international_environment | domain_specific | tools |
| `metier:customer_relationship_management` | customer_relationship_management | soft_skills | tools |
| `metier:client_relationship_management` | client_relationship_management | soft_skills | tools |
| `metier:project_management` | project_management | soft_skills | tools |
| `metier:b2b_prospecting` | b2b_prospecting | sales | tools |
| `metier:market_analysis` | market_analysis | domain_specific | tools |
| `metier:procurement` | procurement | supply_chain | tools |
| `metier:financial_reporting` | financial_reporting | finance | tools |
| `metier:budget_management` | budget_management | soft_skills | finance |
| `metier:cross_functional_collaboration` | cross_functional_collaboration | soft_skills | tools |
| `metier:veille_technologique` | technology_monitoring | domain_specific | tools |
| `metier:contract_negotiation` | contract_negotiation | soft_skills | tools |
| `metier:supplier_relationship_management` | supplier_relationship_management | soft_skills | tools |
| `metier:supplier_performance_improvement` | supplier_performance_improvement | operations | tools |
| `metier:candidate_sourcing` | candidate_sourcing | domain_specific | tools |

---

## Priority Fix Plan

### P0 — BLOCKERS (must fix before matching integration)

- Compression ratio too low (1.25x < 1.5x target)
- Found 15 semantic duplicate groups


### P1 — Important (before production)

- Review 8 over-specific canonical skills
- Fix domain tags on 1786 skills


### P2 — Cleanup (post-Phase 2 optional)

- Clean 222 low quality labels


---

## Recommendation

### ❌ DO NOT PROCEED TO DB IMPLEMENTATION YET

**Reason:** Dictionary is not semantically ready for CV↔offer matching.

**Issues:**
1. Compression ratio too low (1.25x < 1.5x target)
2. 15 semantic duplicate groups unmerged
3. 0 critical polluted clusters
4. 8 over-specific skills need consolidation
5. 1786 domain tags semantically mismatched

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

**Final Verdict:** NOT_READY — Score 22/100
