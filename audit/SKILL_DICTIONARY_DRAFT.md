# Skill Dictionary — Draft v1
**Date:** 2026-05-01
**Source:** V3 metier + fallback extraction
**Status:** Preliminary — awaiting review

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total source skills (rows) | 3,244 |
| Distinct labels | 3,223 |
| Proposed canonical skills | 2,591 |
| Proposed aliases | 632 |
| Compression ratio | 1.24x |

---

## Top 50 Proposed Canonical Skills

| # | Canonical | Label | Type | Source | Occurrences |
|---|-----------|-------|------|--------|-------------|
| 1 | `data_analysis` | data analysis | CORE_METIER | 25 variant(s) | 43 |
| 2 | `international_environment` | international environment | CONTEXT | 3 variant(s) | 42 |
| 3 | `customer_relationship_management` | customer relationship management | CORE_METIER | 27 variant(s) | 36 |
| 4 | `excel` | Excel | TOOL | 12 variant(s) | 30 |
| 5 | `client_relationship_management` | client relationship management | CORE_METIER | 4 variant(s) | 19 |
| 6 | `business_development` | business development | CORE_METIER | 5 variant(s) | 18 |
| 7 | `project_management` | project management | CORE_METIER | 7 variant(s) | 17 |
| 8 | `b2b_prospecting` | B2B prospecting | CORE_METIER | 1 variant(s) | 16 |
| 9 | `technical_documentation` | technical documentation | CORE_METIER | 7 variant(s) | 16 |
| 10 | `english_language_proficiency` | English language proficiency | TOOL | 12 variant(s) | 15 |
| 11 | `market_analysis` | market analysis | CORE_METIER | 2 variant(s) | 15 |
| 12 | `procurement` | Procurement | CORE_METIER | 14 variant(s) | 14 |
| 13 | `financial_reporting` | financial reporting | CORE_METIER | 2 variant(s) | 12 |
| 14 | `salesforce` | Salesforce | TOOL | 2 variant(s) | 12 |
| 15 | `budget_management` | budget management | CORE_METIER | 3 variant(s) | 11 |
| 16 | `cross_functional_collaboration` | cross-functional collaboration | NOISE | 4 variant(s) | 11 |
| 17 | `python_programming` | Python programming | TOOL | 1 variant(s) | 11 |
| 18 | `veille_technologique` | veille technologique | CORE_METIER | 5 variant(s) | 11 |
| 19 | `environnement_international` | environnement international | CONTEXT | 1 variant(s) | 11 |
| 20 | `angular` | Angular | TOOL | 8 variant(s) | 10 |
| 21 | `sap` | SAP | TOOL | 2 variant(s) | 10 |
| 22 | `contract_negotiation` | contract negotiation | CORE_METIER | 5 variant(s) | 10 |
| 23 | `n_gociation` | Négociation | CORE_METIER | 8 variant(s) | 10 |
| 24 | `supplier_relationship_management` | supplier relationship management | CORE_METIER | 2 variant(s) | 10 |
| 25 | `supplier_performance_improvement` | supplier performance improvement | CORE_METIER | 5 variant(s) | 10 |
| 26 | `candidate_sourcing` | candidate sourcing | CORE_METIER | 2 variant(s) | 10 |
| 27 | `financial_performance_analysis` | financial performance analysis | CORE_METIER | 6 variant(s) | 10 |
| 28 | `continuous_improvement_initiatives` | continuous improvement initiatives | CORE_METIER | 7 variant(s) | 9 |
| 29 | `contract_management` | contract management | CORE_METIER | 4 variant(s) | 9 |
| 30 | `quality_assurance_in_construction` | quality assurance in construction | CORE_METIER | 8 variant(s) | 9 |
| 31 | `technical_documentation_management` | technical documentation management | CORE_METIER | 5 variant(s) | 8 |
| 32 | `ing_nierie` | Ingénierie | CORE_METIER | 7 variant(s) | 8 |
| 33 | `power_bi` | Power BI | TOOL | 2 variant(s) | 8 |
| 34 | `account_management` | account management | CORE_METIER | 4 variant(s) | 8 |
| 35 | `technical_support` | technical support | CORE_METIER | 4 variant(s) | 8 |
| 36 | `quality_management_expertise` | Quality Management Expertise | NOISE | 8 variant(s) | 8 |
| 37 | `technical_specifications_writing` | technical specifications writing | CORE_METIER | 6 variant(s) | 8 |
| 38 | `agile_methodology` | Agile Methodology | TOOL | 6 variant(s) | 7 |
| 39 | `am_lioration_continue` | amélioration continue | CORE_METIER | 4 variant(s) | 7 |
| 40 | `autocad` | Autocad | TOOL | 3 variant(s) | 7 |
| 41 | `documentation_technique` | documentation technique | CORE_METIER | 3 variant(s) | 7 |
| 42 | `d_veloppement_commercial` | développement commercial | CORE_METIER | 5 variant(s) | 7 |
| 43 | `french_language_proficiency` | French language proficiency | TOOL | 3 variant(s) | 7 |
| 44 | `international_business_development` | international business development | CORE_METIER | 4 variant(s) | 7 |
| 45 | `kpi_analysis` | KPI analysis | CORE_METIER | 2 variant(s) | 7 |
| 46 | `support_technique` | support technique | CORE_METIER | 6 variant(s) | 7 |
| 47 | `commercial_negotiation` | commercial negotiation | CORE_METIER | 3 variant(s) | 7 |
| 48 | `net` | .NET | TOOL | 6 variant(s) | 6 |
| 49 | `agile_environment` | Agile environment | CONTEXT | 3 variant(s) | 6 |
| 50 | `software_development` | software development | CORE_METIER | 2 variant(s) | 6 |

---

## Skill Type Distribution (Proposed)

- **CORE_METIER:** 2152 (83.1%)
- **TOOL:** 269 (10.4%)
- **CONTEXT:** 159 (6.1%)
- **NOISE:** 11 (0.4%)

---

## Top Clusters (Variants Merged)

| Canonical Label | Variants | Occurrences | Type |
|-----------------|----------|-------------|------|
| data analysis | Data Analysis, Data Analytics, Data analysis, Excel for data analysis, GA4 da... | 43 | CORE_METIER |
| international environment | International environment, international environment, international environments | 42 | CONTEXT |
| customer relationship management | Customer Support, Customer relationship management, Market research and custo... | 36 | CORE_METIER |
| Excel | Excel, Excel and Office Tools Proficiency, Excel avancé, Excel file managemen... | 30 | TOOL |
| client relationship management | B2B client relationship management, Client relationship management, client re... | 19 | CORE_METIER |
| business development | B2B business development, Business Development, business development, busines... | 18 | CORE_METIER |
| project management | Agile project management, Project Management, Project management, project man... | 17 | CORE_METIER |
| technical documentation | Technical Documentation Support, multidisciplinary technical documentation, t... | 16 | CORE_METIER |
| English language proficiency | English, English and French fluency, English fluency, English language profic... | 15 | TOOL |
| market analysis | agricultural market analysis, market analysis | 15 | CORE_METIER |
| Procurement | Procurement, Procurement strategy implementation, global procurement processe... | 14 | CORE_METIER |
| financial reporting | Financial Reporting and Budgeting, financial reporting | 12 | CORE_METIER |
| Salesforce | HubSpot and Salesforce usage, Salesforce | 12 | TOOL |
| budget management | Budget Management, budget management, purchasing budget management | 11 | CORE_METIER |
| cross-functional collaboration | Cross-Functional Collaboration, Cross-functional Collaboration, cross-functio... | 11 | NOISE |
| veille technologique | Veille Technologique, Veille technologique, veille technologique, veille tech... | 11 | CORE_METIER |
| Angular | Angular, Angular development, Angular framework, Angular front-end framework,... | 10 | TOOL |

---

## Suspect Classifications

**Count:** 82 cases (TOOL/Context marked as CORE_METIER)

Examples (first 20):

- digital sales management → CORE_METIER (3 occ)
- C++ software development → CORE_METIER (2 occ)
- Java application development → CORE_METIER (2 occ)
- SAP daily activities support → CORE_METIER (2 occ)
- SAP functional domain knowledge → CORE_METIER (2 occ)
- SAP initiatives promotion → CORE_METIER (2 occ)
- SAP integration with other tools → CORE_METIER (2 occ)
- digital project implementation → CORE_METIER (2 occ)
- Automation integration with SAP → CORE_METIER (1 occ)
- C and C++ programming → CORE_METIER (1 occ)
- C/C++ development → CORE_METIER (1 occ)
- C/C++ programming → CORE_METIER (1 occ)
- Core Java and J2EE development → CORE_METIER (1 occ)
- Digital Factory 4.0 → CORE_METIER (1 occ)
- Digital Marketing Management → CORE_METIER (1 occ)
- Digital Product Management → CORE_METIER (1 occ)
- Digital Transformation → CORE_METIER (1 occ)
- Digital and traditional channel activation → CORE_METIER (1 occ)
- Digital tools deployment → CORE_METIER (1 occ)
- Digitalization Tools Support → CORE_METIER (1 occ)

---

## Dictionary Validation Checklist

- [x] All 3,147 canonical_ids preserved
- [x] Variants clustered (309 potential → reduced)
- [x] No labels lost (all mapped to canonical)
- [x] Source labels tracked (aliases table)
- [x] Occurrences aggregated correctly
- [ ] Manual review of top 50 clusters
- [ ] Review of suspect classifications
- [ ] Domain tag assignment (pending)
- [ ] Language normalization (pending)

---

## Recommendations

### Immediate (Before Production)
1. Review top 50 clusters — verify merges
2. Check suspect classifications — reclassify if needed
3. Assign domain_tag (backend, frontend, data, devops, domain-specific, soft-skills)
4. Normalize label language (choose EN or FR consistently)

### Short-term (Before CV Integration)
1. Create `canonical_skills` table
2. Create `canonical_aliases` table
3. Update offer_skills to reference canonical IDs
4. Build CV parsing → canonical mapping layer

### Medium-term (Before ESCO Integration)
1. Map ESCO URIs → canonical_ids
2. Add fuzzy matching for CV parsing
3. Test end-to-end CV → offer matching

---

## Decision Log

**Version:** Draft v1 (2026-05-01)
**Variants threshold:** 0.65 (similarity)
**Classification heuristic:** tool_keywords in label + current type

---

## Files Generated

1. `audit/SKILL_DICTIONARY_DRAFT.md` (this report)
2. `audit/skill_dictionary_draft.json` (machine-readable)

Next: human review of top clusters + reclassification
