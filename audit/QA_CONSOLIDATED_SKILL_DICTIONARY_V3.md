# QA — Skill Dictionary Consolidated V3
**Date:** 2026-05-02
**Status:** READY

---

## Executive Summary

Validation of 1,164 merges from V3 consolidation. Focus: detect false positives from low-occurrence consolidation.

### Metrics

| Check | Result | Status |
|-------|--------|--------|
| Suspicious low-similarity merges | 0 found | ✓ OK |
| Cluster coherence issues | 6 flagged | ✓ OK |
| QA Score | 88/100 | ✓ PASS |
| Ready for DB | YES | ✓ |

---

## Findings

### 1. Suspicious Low-Similarity Merges (0)

These merged skills have low word overlap — potential false positives:

| Canonical | Source | Similarity | Severity |
|-----------|--------|------------|----------|

---

### 2. Low-Coherence Clusters (6)

High-frequency skills with low average word overlap in aliases:

| Canonical | Occurrences | Aliases | Avg Overlap | Issue |
|-----------|-------------|---------|-------------|-------|
| customer_relationship_management | 55 | 32 | 0.25 | Diverse merged skills |
| excel | 30 | 12 | 0.25 | Diverse merged skills |
| negotiation | 18 | 14 | 0.17 | Diverse merged skills |
| procurement | 17 | 16 | 0.28 | Diverse merged skills |
| technology_monitoring | 13 | 9 | 0.06 | Diverse merged skills |
| industrial_environment | 13 | 19 | 0.2 | Diverse merged skills |

---

## Top 25 Consolidated Skills (Validation)

| # | Canonical | Occurrences | Aliases | Top Aliases |
|---|-----------|-------------|---------|------------|
| 1 | international_environment | 68 | 27 | international_recruitment, international presence, international_teamwork_dynamics |
| 2 | customer_relationship_management | 55 | 32 | customer presentations and negotiations, prospecting potential customers, customer service support |
| 3 | data_analysis | 54 | 39 | data_asset_analysis, Data Visualisation, dashboard creation |
| 4 | technical_documentation | 33 | 30 | technical_manual_creation, technical_queries_management, Documentation Technique |
| 5 | financial_reporting | 31 | 30 | financial due diligence, financial_reporting_management, financial compliance processes |
| 6 | excel | 30 | 12 | Faurecia Excellence System methodologies, Excel, Excel file management |
| 7 | project_management | 28 | 27 | project success tracking, project KPIs tracking, project_quality_plan |
| 8 | business_development | 26 | 14 | commercial_development, business_unit_development, commercial development in equine veterinary |
| 9 | market_analysis | 24 | 13 | market_analysis_and_benchmarking, market_trends_analysis, Market research and sourcing |
| 10 | client_relationship_management | 21 | 8 | relationship management, Client relationship management, client relationship development |
| 11 | cross_functional_collaboration | 18 | 13 | Cross-functional Collaboration, Cross-Functional Collaboration, cross-functional collaboration |
| 12 | negotiation | 18 | 14 | négociation conditions d'achat, rédaction et négociation des clauses commerciales, négociation et closing de contrats |
| 13 | technical_support | 18 | 21 | technical_support_provision, technical support for sales teams, technical support provision |
| 14 | b2b_prospecting | 17 | 3 | b2b_project_scoping, B2B prospecting, B2B project scoping |
| 15 | procurement | 17 | 16 | international procurement environment, purchase order management, procurement project portfolio |
| 16 | performance_analysis | 17 | 26 | performance tracking tools, performance management dashboarding, performance review cycle |
| 17 | power_bi | 16 | 14 | PowerBI Knowledge, utilisation de PowerBI, powerpoint |
| 18 | english_language_proficiency | 15 | 12 | English proficiency, Fluent English, English and French fluency |
| 19 | analyse_des_données | 15 | 23 | analyse_des_besoins_clients, analyse_des_défaillances_fournisseurs, analyse des défaillances fournisseurs |
| 20 | gestion_de_projet | 15 | 25 | gestion_client, gestion de portefeuille fournisseurs, gestion de la qualité |
| 21 | candidate_sourcing | 14 | 8 | candidate sourcing, candidate_headhunting, candidate headhunting |
| 22 | développement_commercial | 14 | 19 | développement LabVIEW, développement de marché local, développement de supervision |
| 23 | contract_negotiation | 14 | 13 | Contract Negotiation & Management, contract_law_support, contract_negotiation_management |
| 24 | salesforce | 13 | 4 | salesforce_management, HubSpot and Salesforce usage, Salesforce management |
| 25 | technology_monitoring | 13 | 9 | veille technologique et marché, veille technologique et réglementaire, Veille technologique |

---

## Recommendation

✓ READY FOR DB IMPLEMENTATION

### Action Items:

2. Review 6 low-coherence clusters

✓ All QA checks passed. Safe to proceed to Phase 2 DB implementation.
