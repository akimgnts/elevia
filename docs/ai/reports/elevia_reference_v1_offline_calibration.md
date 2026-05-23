# Elevia Reference V1 Offline Calibration

## Scope

This document records the offline / DEV-only calibration state of the current Elevia V1 referential.

It covers the V1 clusters currently implemented in the static registry:
- `FINANCE_CONTROL`
- `SALES_BUSINESS_DEVELOPMENT`
- `SUPPLY_CHAIN_PROCUREMENT`
- `OPERATIONS_PROJECT_PMO`
- `ENGINEERING_BUILD_RUN`
- `HR_TALENT_OPERATIONS`

It remains:
- deterministic
- explainable
- audit-friendly
- unconnected to runtime product behavior

It does **not**:
- modify scoring
- modify ranking
- modify filtering
- modify `/inbox`
- modify `matching_v1.py`
- modify `idf.py`
- modify `weights_*`
- add frontend exposure
- add DB migrations

---

## Calibration Principles

- Cluster construction is based on the Business France corpus audit, not on title-only heuristics.
- Generic signals such as `sql`, `excel`, `reporting`, `analysis`, `communication`, `management`, `kpi` remain weak or contextual only.
- Emerging patterns such as `RevOps`, `Finance Ops`, `Supply Analytics` remain internal calibration signals, not official V1 clusters.
- Ambiguity is expected and should stay visible through candidate ordering rather than being hidden by runtime heuristics.

---

## Cluster Calibration Summary

### `FINANCE_CONTROL`

1. **Justification corpus BF**
- `finance`: `107` offers (`12.21 %`)
- strongly represented titles include `CONTROLEUR DE GESTION`, `VIE Management Controller`, `Finance controller`

2. **Strong signals**
- `financial analysis`
- `financial reporting`
- `management control`
- `accounting`
- `budgeting`
- `sap`
- `controlling`
- `financial planning`
- `finance controller`
- `management controller`
- `business controller`
- `controle de gestion`
- `contrôle de gestion`

3. **Weak/contextual signals**
- `excel`
- `reporting`
- `analysis`
- `kpi`
- `management`
- `dashboard`

4. **Forbidden standalone anchors**
- `excel`
- `reporting`
- `analysis`
- `kpi`
- `sql`

5. **Patterns métier détectés**
- controller + budgeting + financial reporting
- SAP-assisted control cycles
- monthly close / variance analysis / management control loops

6. **Exemples d’offres représentatives**
- `CONTROLEUR DE GESTION (H/F)`
- `VIE Management Controller (H/F)`
- `Finance controller (H/F)`

7. **Ambiguïtés observées**
- overlap with `BI_ANALYTICS` when Power BI / dashboard / KPI appear in finance reporting roles
- overlap with `OPERATIONS_PROJECT_PMO` for process-heavy control roles

8. **Limites connues**
- `sap` is useful but not finance-exclusive
- finance / compliance / operations hybrids are not separated yet

9. **Résultats des tests**
- clear finance case classified `FINANCE_CONTROL`
- BI case with `Power BI` + `Excel` + `reporting` does not drift to finance
- finance / BI overlap remains visible, with finance staying primary

---

### `SALES_BUSINESS_DEVELOPMENT`

1. **Justification corpus BF**
- `sales`: `129` offers (`14.73 %`)
- representative BF surface includes business development, commercial export, CRM-heavy commercial roles

2. **Strong signals**
- `b2b sales`
- `business development`
- `crm`
- `crm management`
- `salesforce`
- `hubspot`
- `prospecting`
- `lead generation`
- `account management`
- `sales development`
- `commercial development`

3. **Weak/contextual signals**
- `reporting`
- `analysis`
- `excel`
- `kpi`
- `communication`
- `management`
- `dashboard`

4. **Forbidden standalone anchors**
- `excel`
- `reporting`
- `analysis`
- `kpi`
- `communication`
- `management`

5. **Patterns métier détectés**
- CRM + prospecting + account management
- Salesforce / HubSpot pipeline follow-up
- revenue growth driven commercial execution

6. **Exemples d’offres représentatives**
- `Business Developer`
- `Commercial export`
- `Technico-commercial`

7. **Ambiguïtés observées**
- overlap with future `Sales Ops` patterns when dashboards and pipeline governance dominate
- overlap with `BI_ANALYTICS` if CRM reporting outweighs commercial execution signals
- overlap with `HR_TALENT_OPERATIONS` for talent / business manager hybrids

8. **Limites connues**
- `crm` is useful but not sales-exclusive
- some revops-flavored surfaces remain intentionally unmodeled as official clusters

9. **Résultats des tests**
- positive CRM / Salesforce / prospecting case classified `SALES_BUSINESS_DEVELOPMENT`
- generic management / reporting / Excel case does not create a sales cluster

---

### `SUPPLY_CHAIN_PROCUREMENT`

1. **Justification corpus BF**
- `supply`: `115` offers (`13.13 %`)
- the BF audit showed stable procurement, purchasing, supplier management and logistics patterns

2. **Strong signals**
- `supply chain`
- `supply chain management`
- `procurement`
- `purchasing`
- `supplier management`
- `inventory`
- `logistics`
- `replenishment`
- `approvisionnement`
- `acheteur`
- `sap supply`

3. **Weak/contextual signals**
- `reporting`
- `analysis`
- `excel`
- `kpi`
- `management`
- `dashboard`

4. **Forbidden standalone anchors**
- `excel`
- `reporting`
- `analysis`
- `kpi`
- `management`

5. **Patterns métier détectés**
- procurement + supplier management + inventory control
- SAP-enabled supply flows
- logistics follow-up + replenishment planning

6. **Exemples d’offres représentatives**
- `Acheteur`
- `Approvisionneur`
- `Purchasing VIE`

7. **Ambiguïtés observées**
- overlap with `OPERATIONS_PROJECT_PMO` on supply coordination roles
- overlap with `FINANCE_CONTROL` when cost control and SAP appear without supply anchors
- overlap with future `Supply Analytics` when forecasting and dashboards dominate

8. **Limites connues**
- `sap` had to be disambiguated from finance by negative signals and stronger supply anchors
- some supply / operations hybrids remain broad by design

9. **Résultats des tests**
- procurement / logistics / supplier management case classified `SUPPLY_CHAIN_PROCUREMENT`
- supply / operations overlap remains visible, with supply staying primary

---

### `OPERATIONS_PROJECT_PMO`

1. **Justification corpus BF**
- `operations`: `77` offers (`8.79 %`)
- project, governance and process-coordination surfaces are recurrent enough to justify a V1 cluster

2. **Strong signals**
- `project management`
- `pmo`
- `governance`
- `process improvement`
- `operational coordination`
- `project coordination`
- `service management`
- `process governance`

3. **Weak/contextual signals**
- `reporting`
- `analysis`
- `excel`
- `kpi`
- `communication`
- `management`
- `dashboard`

4. **Forbidden standalone anchors**
- `excel`
- `reporting`
- `analysis`
- `kpi`
- `communication`
- `management`

5. **Patterns métier détectés**
- PMO + governance + Jira
- process improvement + operational coordination
- cross-functional project stream management

6. **Exemples d’offres représentatives**
- `PMO Coordinator`
- `Project Operations Coordinator`
- `Operations Project Manager`

7. **Ambiguïtés observées**
- overlap with `SUPPLY_CHAIN_PROCUREMENT` when the role coordinates supply projects
- overlap with `HR_TALENT_OPERATIONS` for HR operations / onboarding coordination roles
- overlap with `FINANCE_CONTROL` for process-heavy control surfaces

8. **Limites connues**
- this cluster is intentionally broad in V1
- project-heavy roles still need future sub-cluster decisions to become more specific

9. **Résultats des tests**
- governance / PMO / process-improvement case classified `OPERATIONS_PROJECT_PMO`
- supply and HR overlaps remain visible but secondary when domain anchors are stronger elsewhere

---

### `ENGINEERING_BUILD_RUN`

1. **Justification corpus BF**
- `engineering`: `272` offers (`31.05 %`)
- this is the largest BF domain and must not be absorbed into data-centric logic

2. **Strong signals**
- `backend development`
- `software testing`
- `docker`
- `kubernetes`
- `containerization`
- `mechanical design`
- `devops`
- `azure`
- `cloud operations`
- `backend engineer`
- `build and run`

3. **Weak/contextual signals**
- `reporting`
- `analysis`
- `excel`
- `kpi`
- `communication`
- `management`
- `python`

4. **Forbidden standalone anchors**
- `excel`
- `reporting`
- `analysis`
- `kpi`
- `communication`
- `management`

5. **Patterns métier détectés**
- Docker + Kubernetes + containerization
- backend development + devops
- cloud operations + build/run reliability

6. **Exemples d’offres représentatives**
- `Backend Engineer`
- `DevOps Engineer`
- `Mechanical Design Engineer`

7. **Ambiguïtés observées**
- overlap with `DATA_ENGINEERING` when backend/API/automation appears in data-adjacent contexts
- overlap with future `Backend Automation` sub-patterns

8. **Limites connues**
- `python` remains weak only because it is too cross-domain
- some platform / data-engineering boundary cases still rely on negative signals and score balance

9. **Résultats des tests**
- backend / devops / containerization case classified `ENGINEERING_BUILD_RUN`
- engineering / data overlap remains visible, with engineering staying primary when data signals are weak

---

### `HR_TALENT_OPERATIONS`

1. **Justification corpus BF**
- `hr`: `39` offers (`4.45 %`)
- smaller than sales/supply/finance, but coherent enough to justify a first V1 HR cluster

2. **Strong signals**
- `recruitment`
- `candidate sourcing`
- `talent management`
- `onboarding`
- `successfactors`
- `hr systems`
- `workforce planning`
- `talent acquisition`
- `hr operations`
- `people operations`

3. **Weak/contextual signals**
- `reporting`
- `analysis`
- `excel`
- `kpi`
- `communication`
- `management`
- `dashboard`

4. **Forbidden standalone anchors**
- `excel`
- `reporting`
- `analysis`
- `kpi`
- `communication`
- `management`

5. **Patterns métier détectés**
- recruitment + candidate sourcing + onboarding
- HR systems governance
- talent operations + workforce planning

6. **Exemples d’offres représentatives**
- `Talent Acquisition Specialist`
- `HR Coordinator`
- `People Operations Specialist`

7. **Ambiguïtés observées**
- overlap with `OPERATIONS_PROJECT_PMO` for onboarding or HR coordination programs
- overlap with `BI_ANALYTICS` if HR dashboards and reporting dominate without talent anchors
- overlap with `SALES_BUSINESS_DEVELOPMENT` on “business manager” style titles without HR evidence

8. **Limites connues**
- HR digital / HR analytics is not split yet
- successfactors helps, but HR roles still need semantic anchors beyond tooling

9. **Résultats des tests**
- recruitment / onboarding / HR systems case classified `HR_TALENT_OPERATIONS`
- HR / operations overlap remains visible, with HR staying primary when talent anchors dominate

---

## Generic Signals Kept Weak

The following remain weak or contextual only across V1:
- `sql`
- `excel`
- `reporting`
- `analysis`
- `communication`
- `management`
- `kpi`

This is deliberate and directly aligned with the PostgreSQL Business France audit.

---

## Global Ambiguity Map

The main cross-cluster ambiguity zones remain:
- `FINANCE_CONTROL` vs `BI_ANALYTICS`
- `SUPPLY_CHAIN_PROCUREMENT` vs `OPERATIONS_PROJECT_PMO`
- `ENGINEERING_BUILD_RUN` vs `DATA_ENGINEERING`
- `HR_TALENT_OPERATIONS` vs `OPERATIONS_PROJECT_PMO`
- `SALES_BUSINESS_DEVELOPMENT` vs future `Sales Ops`

These ambiguities are acceptable at this stage because they are explicit, inspectable, and still offline only.

---

## Test Status

Current unit test scope covers:
- positive cases for all current V1 clusters
- weak-signal insufficiency
- ambiguity visibility
- overlap stability
- anti-regression on pre-existing V0/V1 clusters

Latest run:
- `apps/api/.venv/bin/python -m pytest apps/api/tests/test_elevia_metier.py -q`
- result: `19 passed`

---

## Current Limits

- The referential is still registry-driven and heuristic.
- `BI_ANALYTICS` remains broader than the target end-state because its neighbors are only now being added.
- Emerging patterns such as `RevOps`, `Finance Ops`, `Supply Analytics`, `HR Operations`, `Backend Automation` stay internal only.
- No runtime product integration exists yet by design.

---

## Recommended Next Step

Do not branch anything into runtime yet.

The next coherent step is to run another offline audit pass against representative BF-like offers and profiles using the now-extended registry, to see:
- whether `BI_ANALYTICS` is naturally less absorbent
- whether supply / operations and HR / operations ambiguities stay acceptable
- whether additional negative signals are needed before any DEV-only exposure
