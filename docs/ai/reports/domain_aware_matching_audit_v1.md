# Domain-aware Matching Audit v1

> Audit only. No runtime / route / scoring / matching / schema / frontend / DB change. Reads BF tables only (SELECT).

## Summary

- audit_date: `2026-04-26T15:10:55+00:00`
- profiles_audited: **7**
- active_bf_offers: **876**
- skill_universe_in_offer_skills: **93**
- expected_vs_inferred_match_rate: **100.0%**
- average_hard_filter_exclusion_pct: **86.4%**
- average_aligned_pct: **12.2%**
- average_adjacent_pct: **25.4%**
- average_distant_pct: **61.1%**
- average_neutral_pct: **1.4%**
- average_soft_keep (aligned + adjacent): **37.5%**
- average_distant_only_exclusion_pct: **61.1%**
- average_exclusion_reduction_vs_binary_pct: **25.4%**

## Method (v2 — strong vs weak signal weighting)

1. For each `canonical_id` in `offer_skills` (BF), compute its `domain_tag` distribution from `offer_domain_enrichment`.
2. For each sample profile (canonical-id list), accumulate domain scores using:
   - **Strong signal** (curated per domain): +3.0 to that domain.
   - **Data-driven distribution**: ×1.0 normal weight, ×0.2 for weak signals (excel, powerpoint, reporting, etc.).
   - Require **≥1 strong signal**; otherwise `cv_domain = "other"` (low confidence).
3. For each active BF offer, classify as `aligned` (offer.domain_tag == cv_domain), `mismatched`, or `neutral` (`unknown`/`other`).
4. Project hypothetical hard filter (drop mismatched) and soft filter (low-priority mismatched, neutral kept).

## Domain Affinity Matrix v1 (DB 11-tag)

Three-level classification per offer:
- **aligned**: `offer.domain_tag == cv_domain`
- **adjacent**: pair listed in `ADJACENCY` (cross-domain mobility / hybrid roles)
- **distant**: known domain, no listed adjacency
- **neutral**: `unknown` / `other`

Adjacency pairs (unordered):

- `admin` ↔ `hr`
- `admin` ↔ `operations`
- `data` ↔ `engineering`
- `data` ↔ `finance`
- `data` ↔ `marketing`
- `data` ↔ `operations`
- `engineering` ↔ `operations`
- `engineering` ↔ `supply`
- `finance` ↔ `legal`
- `finance` ↔ `operations`
- `hr` ↔ `operations`
- `legal` ↔ `operations`
- `marketing` ↔ `sales`
- `operations` ↔ `sales`

## Per-profile results

### P1_data_analyst — expected `data` / inferred `data` ✓
- skills with signal: 6 / 6 · strong: 5 · weak: 1 · confidence: `ok`
- score top5: data=15.46 · finance=0.57 · engineering=0.29 · sales=0.23 · operations=0.23
- offers: aligned **65** · adjacent **476** · distant **323** · neutral **12** · total 876
- affinity %: aligned 7.4 · adjacent 54.3 · distant 36.9 · neutral 1.4 · soft_keep 61.8 · exclusion_reduction 54.3
- hard filter: keep **65** (or 77 if neutral kept), exclude **799** (91.2%)
- soft filter: high **65**, low **799**, neutral **12**

**Sample aligned:**
  - `237194` [data] BUSINESS ANALYST/MOA (F/M) (H/F)
  - `237414` [data] Data engineer (H/F)
  - `238049` [data] V.I.E. – Project Coordinator – Edmonton, CANADA- (H/F)

**Sample adjacent (kept by soft, dropped by hard):**
  - `242491` [operations] T&C CFO – Ingénieur Essais et Mise en Service CFO (H/F)
  - `242548` [finance] Contrôleur de gestion (H/F)
  - `242530` [engineering] INGÉNIEUR CONCEPTION MÉCANIQUE (H/F)
  - `237232` [engineering] CONTAINER PROCESS DEVELOPMENT ENGINEER (H/F)
  - `242466` [engineering] Ingénieur Méthodes (F/H/X) - Aéronautique-Spatial-Défense (H/F)

**Sample distant (would be excluded by both soft and hard):**
  - `242301` [sales] Growth & Account Manager – Villa Supply (H/F)
  - `242504` [supply] Supply Chain Manager in Singapore (H/F)
  - `242441` [supply] Responsable Technico-Commercial (H/F)
  - `242532` [supply] HES Engineer M/W (H/F)
  - `237014` [sales] AI Solutions & Automation Specialist (H/F)

### P2_software_engineer — expected `engineering` / inferred `engineering` ✓
- skills with signal: 6 / 6 · strong: 4 · weak: 2 · confidence: `ok`
- score top5: engineering=12.67 · data=1.19 · supply=0.17 · operations=0.12 · sales=0.09
- offers: aligned **272** · adjacent **257** · distant **335** · neutral **12** · total 876
- affinity %: aligned 31.1 · adjacent 29.3 · distant 38.2 · neutral 1.4 · soft_keep 60.4 · exclusion_reduction 29.3
- hard filter: keep **272** (or 284 if neutral kept), exclude **592** (67.6%)
- soft filter: high **272**, low **592**, neutral **12**

**Sample aligned:**
  - `242530` [engineering] INGÉNIEUR CONCEPTION MÉCANIQUE (H/F)
  - `237232` [engineering] CONTAINER PROCESS DEVELOPMENT ENGINEER (H/F)
  - `242466` [engineering] Ingénieur Méthodes (F/H/X) - Aéronautique-Spatial-Défense (H/F)

**Sample adjacent (kept by soft, dropped by hard):**
  - `242491` [operations] T&C CFO – Ingénieur Essais et Mise en Service CFO (H/F)
  - `242504` [supply] Supply Chain Manager in Singapore (H/F)
  - `242441` [supply] Responsable Technico-Commercial (H/F)
  - `242532` [supply] HES Engineer M/W (H/F)
  - `237194` [data] BUSINESS ANALYST/MOA (F/M) (H/F)

**Sample distant (would be excluded by both soft and hard):**
  - `242301` [sales] Growth & Account Manager – Villa Supply (H/F)
  - `242548` [finance] Contrôleur de gestion (H/F)
  - `242337` [finance] ASSISTANT CONTROLE DE GESTION (H/F) BODEN (SUEDE)
  - `237014` [sales] AI Solutions & Automation Specialist (H/F)
  - `242521` [finance] INGENIEUR QUALITE (H/F)

### P3_finance_controller — expected `finance` / inferred `finance` ✓
- skills with signal: 5 / 6 · strong: 3 · weak: 3 · confidence: `ok`
- score top5: finance=10.23 · operations=0.37 · engineering=0.20 · supply=0.20 · sales=0.15
- offers: aligned **107** · adjacent **154** · distant **603** · neutral **12** · total 876
- affinity %: aligned 12.2 · adjacent 17.6 · distant 68.8 · neutral 1.4 · soft_keep 29.8 · exclusion_reduction 17.6
- hard filter: keep **107** (or 119 if neutral kept), exclude **757** (86.4%)
- soft filter: high **107**, low **757**, neutral **12**

**Sample aligned:**
  - `242548` [finance] Contrôleur de gestion (H/F)
  - `242337` [finance] ASSISTANT CONTROLE DE GESTION (H/F) BODEN (SUEDE)
  - `242521` [finance] INGENIEUR QUALITE (H/F)

**Sample adjacent (kept by soft, dropped by hard):**
  - `242491` [operations] T&C CFO – Ingénieur Essais et Mise en Service CFO (H/F)
  - `237194` [data] BUSINESS ANALYST/MOA (F/M) (H/F)
  - `238269` [operations] Chargé de HSE (H/F)
  - `242450` [operations] VIE - Operations Oversight Officer (12 months) (H/F)
  - `242367` [operations] Responsable financier H/F/X (H/F)

**Sample distant (would be excluded by both soft and hard):**
  - `242301` [sales] Growth & Account Manager – Villa Supply (H/F)
  - `242504` [supply] Supply Chain Manager in Singapore (H/F)
  - `242530` [engineering] INGÉNIEUR CONCEPTION MÉCANIQUE (H/F)
  - `237232` [engineering] CONTAINER PROCESS DEVELOPMENT ENGINEER (H/F)
  - `242466` [engineering] Ingénieur Méthodes (F/H/X) - Aéronautique-Spatial-Défense (H/F)

### P4_marketing_manager — expected `marketing` / inferred `marketing` ✓
- skills with signal: 5 / 5 · strong: 5 · weak: 0 · confidence: `ok`
- score top5: marketing=15.40 · sales=0.40 · supply=0.20
- offers: aligned **20** · adjacent **194** · distant **650** · neutral **12** · total 876
- affinity %: aligned 2.3 · adjacent 22.1 · distant 74.2 · neutral 1.4 · soft_keep 24.4 · exclusion_reduction 22.1
- hard filter: keep **20** (or 32 if neutral kept), exclude **844** (96.3%)
- soft filter: high **20**, low **844**, neutral **12**

**Sample aligned:**
  - `242519` [marketing] D&IS Product Marketing (H/F)
  - `242311` [marketing] Chargé·e partenariats et sponsoring (H/F)
  - `242231` [marketing] User Acquisition Specialist (H/F)

**Sample adjacent (kept by soft, dropped by hard):**
  - `242301` [sales] Growth & Account Manager – Villa Supply (H/F)
  - `237014` [sales] AI Solutions & Automation Specialist (H/F)
  - `242471` [sales] COMMERCIAL TERRAIN (H/F)
  - `237194` [data] BUSINESS ANALYST/MOA (F/M) (H/F)
  - `238346` [sales] Digital Account Manager - FR & ITALIAN MARKET (H/F)

**Sample distant (would be excluded by both soft and hard):**
  - `242491` [operations] T&C CFO – Ingénieur Essais et Mise en Service CFO (H/F)
  - `242548` [finance] Contrôleur de gestion (H/F)
  - `242504` [supply] Supply Chain Manager in Singapore (H/F)
  - `242530` [engineering] INGÉNIEUR CONCEPTION MÉCANIQUE (H/F)
  - `237232` [engineering] CONTAINER PROCESS DEVELOPMENT ENGINEER (H/F)

### P5_hr_recruiter — expected `hr` / inferred `hr` ✓
- skills with signal: 4 / 4 · strong: 4 · weak: 0 · confidence: `ok`
- score top5: hr=13.05 · sales=0.49 · engineering=0.26 · other=0.06 · admin=0.06
- offers: aligned **39** · adjacent **105** · distant **720** · neutral **12** · total 876
- affinity %: aligned 4.5 · adjacent 12.0 · distant 82.2 · neutral 1.4 · soft_keep 16.4 · exclusion_reduction 12.0
- hard filter: keep **39** (or 51 if neutral kept), exclude **825** (94.2%)
- soft filter: high **39**, low **825**, neutral **12**

**Sample aligned:**
  - `238239` [hr] TALENT ACQUISITION SPECIALIST (H/F)
  - `242510` [hr] VIA Chargé(e) de mission pédagogique (H/F)
  - `242511` [hr] Sales Operations B2B - RevOps - VIE - Barcelone (H/F)

**Sample adjacent (kept by soft, dropped by hard):**
  - `242491` [operations] T&C CFO – Ingénieur Essais et Mise en Service CFO (H/F)
  - `238269` [operations] Chargé de HSE (H/F)
  - `242450` [operations] VIE - Operations Oversight Officer (12 months) (H/F)
  - `242367` [operations] Responsable financier H/F/X (H/F)
  - `242327` [operations] Analyst Transformation (H/F)

**Sample distant (would be excluded by both soft and hard):**
  - `242301` [sales] Growth & Account Manager – Villa Supply (H/F)
  - `242548` [finance] Contrôleur de gestion (H/F)
  - `242504` [supply] Supply Chain Manager in Singapore (H/F)
  - `242530` [engineering] INGÉNIEUR CONCEPTION MÉCANIQUE (H/F)
  - `237232` [engineering] CONTAINER PROCESS DEVELOPMENT ENGINEER (H/F)

### P6_supply_chain — expected `supply` / inferred `supply` ✓
- skills with signal: 4 / 4 · strong: 4 · weak: 0 · confidence: `ok`
- score top5: supply=12.84 · sales=0.08 · operations=0.03 · admin=0.03 · data=0.03
- offers: aligned **115** · adjacent **272** · distant **477** · neutral **12** · total 876
- affinity %: aligned 13.1 · adjacent 31.1 · distant 54.5 · neutral 1.4 · soft_keep 44.2 · exclusion_reduction 31.1
- hard filter: keep **115** (or 127 if neutral kept), exclude **749** (85.5%)
- soft filter: high **115**, low **749**, neutral **12**

**Sample aligned:**
  - `242504` [supply] Supply Chain Manager in Singapore (H/F)
  - `242441` [supply] Responsable Technico-Commercial (H/F)
  - `242532` [supply] HES Engineer M/W (H/F)

**Sample adjacent (kept by soft, dropped by hard):**
  - `242530` [engineering] INGÉNIEUR CONCEPTION MÉCANIQUE (H/F)
  - `237232` [engineering] CONTAINER PROCESS DEVELOPMENT ENGINEER (H/F)
  - `242466` [engineering] Ingénieur Méthodes (F/H/X) - Aéronautique-Spatial-Défense (H/F)
  - `242528` [engineering] INGÉNIEUR MATÉRIAUX COMPOSITE (H/F)
  - `242474` [engineering] Data Management & Analytical Method Lifecycle (H/F)

**Sample distant (would be excluded by both soft and hard):**
  - `242301` [sales] Growth & Account Manager – Villa Supply (H/F)
  - `242491` [operations] T&C CFO – Ingénieur Essais et Mise en Service CFO (H/F)
  - `242548` [finance] Contrôleur de gestion (H/F)
  - `242337` [finance] ASSISTANT CONTROLE DE GESTION (H/F) BODEN (SUEDE)
  - `237014` [sales] AI Solutions & Automation Specialist (H/F)

### P7_sales_b2b — expected `sales` / inferred `sales` ✓
- skills with signal: 5 / 5 · strong: 5 · weak: 0 · confidence: `ok`
- score top5: sales=17.47 · supply=0.45 · engineering=0.31 · hr=0.29 · finance=0.20
- offers: aligned **129** · adjacent **97** · distant **638** · neutral **12** · total 876
- affinity %: aligned 14.7 · adjacent 11.1 · distant 72.8 · neutral 1.4 · soft_keep 25.8 · exclusion_reduction 11.1
- hard filter: keep **129** (or 141 if neutral kept), exclude **735** (83.9%)
- soft filter: high **129**, low **735**, neutral **12**

**Sample aligned:**
  - `242301` [sales] Growth & Account Manager – Villa Supply (H/F)
  - `237014` [sales] AI Solutions & Automation Specialist (H/F)
  - `242471` [sales] COMMERCIAL TERRAIN (H/F)

**Sample adjacent (kept by soft, dropped by hard):**
  - `242491` [operations] T&C CFO – Ingénieur Essais et Mise en Service CFO (H/F)
  - `242519` [marketing] D&IS Product Marketing (H/F)
  - `238269` [operations] Chargé de HSE (H/F)
  - `242450` [operations] VIE - Operations Oversight Officer (12 months) (H/F)
  - `242367` [operations] Responsable financier H/F/X (H/F)

**Sample distant (would be excluded by both soft and hard):**
  - `242548` [finance] Contrôleur de gestion (H/F)
  - `242504` [supply] Supply Chain Manager in Singapore (H/F)
  - `242530` [engineering] INGÉNIEUR CONCEPTION MÉCANIQUE (H/F)
  - `237232` [engineering] CONTAINER PROCESS DEVELOPMENT ENGINEER (H/F)
  - `242466` [engineering] Ingénieur Méthodes (F/H/X) - Aéronautique-Spatial-Défense (H/F)

## Manual interpretation guide

- A **good mismatch** is an offer whose `domain_tag` correctly diverges from the cv_domain — hard filter helps.
- A **false mismatch** is an offer the user would actually want — hard filter would harm. Hint: check titles for cross-domain roles (e.g. data analyst in finance dept).
- Neutral (`unknown`/`other`) offers are not actionable for a domain filter without taxonomy upgrade.
- An expected-vs-inferred mismatch on a profile signals either (a) skill set is multi-domain by nature, or (b) the data-driven map needs more skills.

## Decision criteria for next sprint

- If average_hard_filter_exclusion_pct is high but mismatch samples look mostly good → hard filter may be safe.
- If false mismatches dominate → prefer soft filter (re-rank only) when this becomes a runtime sprint.
- If expected_vs_inferred_match_rate < 80% → strengthen the cv_domain inference (more skills, smarter weighting) before any runtime activation.
- If `average_exclusion_reduction_vs_binary_pct` is significant and adjacent samples look correct → adopt 3-level affinity as soft signal.
- If adjacent samples look mostly wrong → tighten or remove specific adjacency pairs before adoption.

