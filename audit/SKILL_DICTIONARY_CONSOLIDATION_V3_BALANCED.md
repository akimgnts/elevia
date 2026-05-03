# Skill Dictionary Consolidation — V3 Balanced
**Date:** 2026-05-02
**Status:** READY

---

## Executive Summary

Targeted consolidation: Hard merges from QA + over-specificity + low-occurrence cleanup.

### Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Canonical skills | 2,586 | 1,968 | ~2,150 |
| Compression ratio | 1.25x | 1.64x | ≥1.5x |
| Merges performed | — | — | 1164 |
| Ready for matching | NO | YES ✓ | YES |

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

**Merges:** 21

### 2. Over-Specificity Cleanup

Remove weak suffixes: programming, development, scripting, proficiency, knowledge, expertise, etc.
Example: python_knowledge → python; technical_documentation_management → technical_documentation

**Merges:** 3

### 3. Low-Occurrence Cleanup

Consolidate rare skills (1-2 occurrences) to closest high-frequency parent by string similarity.

**Merges:** 1140

---

## Top Merges

| Source | Target | Occurrences | Reason |
|--------|--------|-------------|--------|
| client_relationship_management | customer_relationship_management | 19 | QA hard merge (semantic duplicate group) |
| python_programming | python | 11 | QA hard merge (semantic duplicate group) |
| contract_negotiation | negotiation | 10 | QA hard merge (semantic duplicate group) |
| commercial_negotiation | negotiation | 7 | QA hard merge (semantic duplicate group) |
| commercial_development | business_development | 6 | QA hard merge (semantic duplicate group) |
| dashboard_creation | data_analysis | 5 | QA hard merge (semantic duplicate group) |
| market_research | market_analysis | 5 | QA hard merge (semantic duplicate group) |
| java_programming | java | 4 | QA hard merge (semantic duplicate group) |
| dashboard_development | dashboard_creation | 4 | low-occurrence consolidation (<4 occ, sim: 0.48) |
| cross_functional_teamwork | cross_functional_collaboration | 4 | low-occurrence consolidation (<4 occ, sim: 0.57) |
| stakeholder_communication | stakeholder_management | 4 | low-occurrence consolidation (<4 occ, sim: 0.48) |
| c_and_c++_programming | c/c++_programming | 3 | QA hard merge (semantic duplicate group) |
| gestion_de_projet | project_management | 3 | QA hard merge (semantic duplicate group) |
| java_application_development | java | 3 | QA hard merge (semantic duplicate group) |
| powerbi | power_bi | 3 | QA hard merge (semantic duplicate group) |
| powerpoint | power_bi | 3 | low-occurrence consolidation (<3 occ, sim: 0.50) |
| python_scripting | python | 3 | QA hard merge (semantic duplicate group) |
| requirements_management | requirements_gathering | 3 | low-occurrence consolidation (<3 occ, sim: 0.57) |
| client_portfolio_management | client_portfolio_development | 3 | low-occurrence consolidation (<3 occ, sim: 0.61) |
| contrôle_de_gestion | contrôle_qualité | 3 | low-occurrence consolidation (<3 occ, sim: 0.47) |
| financial_compliance | financial_reporting | 3 | low-occurrence consolidation (<3 occ, sim: 0.50) |
| financial_modeling | financial_analysis | 3 | low-occurrence consolidation (<3 occ, sim: 0.56) |
| financial_reporting_management | financial_reporting | 3 | low-occurrence consolidation (<3 occ, sim: 0.63) |
| monthly_reporting | financial_reporting | 3 | QA hard merge (semantic duplicate group) |
| performance_management | performance_analysis | 3 | low-occurrence consolidation (<3 occ, sim: 0.55) |

---

## Compression Analysis

**Before:** 1.25x (3,223 labels → 2,586 canonicals)
**After:** 1.64x (3,223 labels → 1968 canonicals)
**Target:** ≥1.5x

**Status:** ✓ READY FOR MATCHING

---

## Top 25 Skills (by occurrences)

| # | Label | Domain | Occurrences |
|---|-------|--------|-------------|
| 1 | international_environment | domain_specific | 68 |
| 2 | customer_relationship_management | soft_skills | 55 |
| 3 | data_analysis | data | 54 |
| 4 | technical_documentation | domain_specific | 33 |
| 5 | financial_reporting | finance | 31 |
| 6 | excel | tools | 30 |
| 7 | project_management | soft_skills | 28 |
| 8 | business_development | domain_specific | 26 |
| 9 | market_analysis | domain_specific | 24 |
| 10 | client_relationship_management | soft_skills | 21 |
| 11 | cross_functional_collaboration | soft_skills | 18 |
| 12 | negotiation | soft_skills | 18 |
| 13 | technical_support | domain_specific | 18 |
| 14 | b2b_prospecting | sales | 17 |
| 15 | procurement | supply_chain | 17 |
| 16 | performance_analysis | domain_specific | 17 |
| 17 | power_bi | data | 16 |
| 18 | english_language_proficiency | languages | 15 |
| 19 | analyse_des_données | domain_specific | 15 |
| 20 | gestion_de_projet | domain_specific | 15 |
| 21 | candidate_sourcing | domain_specific | 14 |
| 22 | développement_commercial | domain_specific | 14 |
| 23 | contract_negotiation | soft_skills | 14 |
| 24 | salesforce | tools | 13 |
| 25 | technology_monitoring | domain_specific | 13 |

---

## Next Steps

✓ Ready for Phase 2 DB implementation. Proceed with canonical_skills + canonical_aliases table creation.
