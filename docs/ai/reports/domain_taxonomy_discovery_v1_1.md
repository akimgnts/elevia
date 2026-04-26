# Domain Taxonomy Discovery v1.1 — Consolidation Patch

> Artifact-only patch on `consolidated_v1` and `classification_validation_v1`. No new AI discovery, no DB mutation, no schema change, no scoring change.

- based_on: `consolidated_v1.json` + `classification_validation_v1.json`
- closed_domain_count_before: **14**
- closed_domain_count_after: **12**
- removed_domains: `product_ecommerce`, `administration_support`
- offers_changed: **5 / 250 (2.0%)**
- needs_ai_review_after: **3 / 250 (1.2%)** (unchanged)

## 1. Closed domain list v1.1 (12)

`operations_project`, `finance`, `hr`, `engineering_industrial`, `data`, `marketing_communication`, `consulting_strategy`, `sales_business_development`, `supply_chain_logistics`, `legal_compliance`, `engineering_software`, `other`

## 2. Removal routing rules

### `administration_support` → split
| Raw domain | New target |
|---|---|
| information technology | engineering_software |
| real estate and parking services | other |
| construction and safety management | operations_project |

### `product_ecommerce` → split
| Raw domain | New target |
|---|---|
| mining industry solutions | sales_business_development |
| cosmetics and beauty | marketing_communication |
| product development | engineering_industrial |
| agricultural and construction equipment | sales_business_development |

## 3. `data` tightening

Removed from `data` raw_to_closed:
- `transportation` → `supply_chain_logistics`
- `transportation and mobility` → `supply_chain_logistics`
- `biopharmaceutical supply chain management` → `supply_chain_logistics`
- `legal services` → `legal_compliance`
- `biotechnology` → `engineering_industrial`
- `digital e-commerce management` → `sales_business_development`
- `sustainability consulting` → `consulting_strategy`
- `building information modeling (bim)` → `engineering_industrial`
- `sales operations` → `sales_business_development`

Required evidence to keep `data` tag: explicit signal among `analytics`, `business intelligence`, `bi`, `machine learning`, `ml`, `data pipeline`, `data governance`, `dashboard`, `database`, `data science`, `data engineering`, `data analyst`, `data analytics`, `data analysis`, `etl`, `sql`, `power bi`, `tableau`, `ai engineer`, `ai operations`, `predictive analytics`, `predictive maintenance`, `deep learning`, `big data`, `data integration`, `data modeling`, `data quality`, `data warehouse`, `data lake`, `donnees systemiques`, `flux de donnees`, `architecture de reporting`.

## 4. `engineering_consulting` disambiguation

- Default: `engineering_industrial`
- Override to `consulting_strategy` if subdomain matches advisory signals: `strategy`, `transformation`, `advisory`, `change management`, `consulting`
- This rule applies to future runs; v1 classifications retroactively respected unless title evidence clearly indicates advisory work (see offer 242327 below).

## 5. Distribution before / after

| Domain | Before (v1) | After (v1.1) | Δ |
|---|---:|---:|---:|
| engineering_industrial | 51 | 52 | +1 |
| finance | 32 | 32 | 0 |
| sales_business_development | 31 | 31 | 0 |
| data | 27 | 25 | -2 |
| engineering_software | 22 | 24 | +2 |
| supply_chain_logistics | 19 | 19 | 0 |
| consulting_strategy | 17 | 18 | +1 |
| hr | 16 | 16 | 0 |
| operations_project | 11 | 12 | +1 |
| legal_compliance | 9 | 9 | 0 |
| marketing_communication | 9 | 9 | 0 |
| other | 3 | 3 | 0 |
| administration_support | 2 | — | removed |
| product_ecommerce | 1 | — | removed |
| **Total** | **250** | **250** | |

## 6. Changed offers (5)

| offer_id | title | from | to | reason |
|---|---|---|---|---|
| 238157 | VIE-Synthesis Researcher (M/F/D) | data | engineering_industrial | lacks explicit data evidence (chemistry/lab role) |
| 242327 | Analyst Transformation | data | consulting_strategy | lacks explicit data evidence; transformation advisory role |
| 236316 | Product Owner | product_ecommerce | operations_project | removed top-level domain; PO/agile role |
| 237348 | Business Applications Support Analyst | administration_support | engineering_software | removed top-level domain; IT/applications support |
| 238347 | IT Installation & Support Technician | administration_support | engineering_software | removed top-level domain; IT support |

## 7. Remaining ambiguous cases (needs_ai_review)

3 offers still flagged `needs_ai_review = true`, all tagged `other`:

| offer_id | title | confidence |
|---|---|---:|
| 238291 | Assistant(e) Architecte d'intérieur | 0.50 |
| 242510 | VIA Chargé(e) de mission pédagogique | 0.30 |
| 238429 | Hydro(géo)logue de terrain et recherches pluridisciplinaires sur l'eau | 0.50 |

These are genuine taxonomy edge cases (interior architecture, pedagogy/cultural mission, hydrogeology field research). They are correctly routed to `other` and flagged for human review — the v1.1 taxonomy is not the appropriate place to absorb them.

## 8. Validation

- closed_domain_count = **12** ✓
- no new AI discovery run ✓
- no DB mutation ✓
- no scoring / matching / `matching_v1.py` / schema / frontend change ✓
- 5 offers reclassified deterministically from offer text + v1 evidence ✓

## 9. Artifacts

- `baseline/domain_taxonomy_discovery/full_v1/consolidated_v1_1.json`
- `baseline/domain_taxonomy_discovery/full_v1/classification_validation_v1_1.json`
- `docs/ai/reports/domain_taxonomy_discovery_v1_1.md` (this file)
