# Elevia Reference V1 Design

## Scope

This document defines the **design only** for Elevia Reference V1.

It does **not**:
- modify the existing V0 registry
- add runtime exposure
- change `/inbox`
- change scoring
- change matching
- create new DB structures

The purpose is to convert the validated Business France corpus audit into a coherent V1 cluster plan that is less data-centric and more representative of the real market in the current product scope.

---

## Design Principles

### 1. Intermediate business clusters, not ultra-broad domains

V1 should not stay at the level of raw domains such as `data`, `finance`, or `sales`, because that recreates the ambiguity already observed in the audit.

V1 should also not jump directly to dozens of micro-clusters, because the current evidence is not stable enough to support that level of granularity.

The target level for V1 is therefore:
- narrower than pure domains
- broader than micro-specializations
- stable enough to calibrate deterministically on Business France

### 2. Non data-centric by construction

The PostgreSQL audit showed that the real BF corpus is **not** dominated by data roles by volume:
- `engineering`: 272 offers
- `sales`: 129
- `supply`: 115
- `finance`: 107
- `operations`: 77
- `data`: 65
- `hr`: 39

So V1 must be built to reflect that reality.

### 3. Generic analytics vocabulary must not define clusters

The audit showed that the following signals are too cross-domain to be trusted alone:
- `sql`
- `excel`
- `kpi`
- `reporting`
- `analysis`
- `communication`
- `management`
- `bi`

These must become contextual signals, never standalone anchors.

### 4. Emerging patterns are signals, not official clusters yet

The audit surfaced patterns such as:
- `Finance Ops`
- `Sales Ops`
- `RevOps`
- `HR Operations`
- `Supply Analytics`
- `Backend Automation`
- `Compliance`

These patterns are useful and real, but they should remain **internal calibration signals** in V1, not official clusters yet.

---

## Recommended V1 Clusters

The recommended official V1 clusters are:

1. `DATA_ENGINEERING`
2. `BI_ANALYTICS`
3. `FINANCE_CONTROL`
4. `SALES_BUSINESS_DEVELOPMENT`
5. `SUPPLY_CHAIN_PROCUREMENT`
6. `OPERATIONS_PROJECT_PMO`
7. `ENGINEERING_BUILD_RUN`
8. `HR_TALENT_OPERATIONS`

---

## Cluster Justification By BF Corpus Volume

### `DATA_ENGINEERING`

- Anchored in the `data` domain, which has `65` BF offers.
- Justified because the audit still shows a real technical data layer distinct from BI.
- Needed to separate pipelines / backend data / orchestration from reporting-heavy analytics roles.

### `BI_ANALYTICS`

- Also anchored in the `data` domain, but driven by dashboarding / business intelligence / reporting surfaces.
- Needed because BI exists strongly in the corpus, but is currently too broad and too absorbent.
- V1 must keep it, while constraining it.

### `FINANCE_CONTROL`

- `finance` has `107` BF offers, which is more than enough for a first-class V1 cluster.
- The audit shows stable recurring signals around management control, reporting, budgeting, accounting, and SAP.
- This is the first major non-data cluster that should be explicit in V1.

### `SALES_BUSINESS_DEVELOPMENT`

- `sales` has `129` BF offers.
- Strong recurring corpus anchors exist: CRM, Salesforce, HubSpot, B2B sales, business development, prospecting.
- This cluster is necessary to avoid sales roles being flattened into generic business/analysis language.

### `SUPPLY_CHAIN_PROCUREMENT`

- `supply` has `115` BF offers.
- The corpus shows stable procurement / purchasing / supplier / supply chain patterns.
- This is sufficiently dense and coherent to become a V1 official cluster.

### `OPERATIONS_PROJECT_PMO`

- `operations` has `77` BF offers.
- The audit shows recurring project / PMO / governance / process-improvement surfaces.
- It is broad, but stable enough for a first V1 grouping.

### `ENGINEERING_BUILD_RUN`

- `engineering` is the largest BF domain with `272` offers.
- The corpus clearly supports a cluster that captures technical build/run execution roles without collapsing them into data.
- This is essential to prevent engineering from being read through a BI/data lens.

### `HR_TALENT_OPERATIONS`

- `hr` has `39` BF offers.
- Smaller than the other major domains, but still sufficient to justify a first V1 cluster.
- The corpus exposes recruiting, onboarding, HR systems, talent operations, and HR dashboards as a coherent surface.

---

## Cluster Definitions

### `DATA_ENGINEERING`

**Intent**
- Capture backend data, pipelines, ingestion, orchestration, transformation, warehouse-oriented execution.

**Strong signals**
- `etl`
- `elt`
- `pipeline`
- `pipelines`
- `data pipeline`
- `orchestration`
- `data engineering`
- `api`
- `postgresql`
- `airflow`
- `dbt`
- `spark`
- `databricks`

**Weak/contextual signals**
- `sql`
- `python`
- `warehouse`
- `automation`
- `data quality`

**Representative BF examples**
- data engineer titles
- analytics engineer titles with strong pipeline / API / warehouse evidence
- backend automation / data platform flavored roles

**Main confusion risk**
- with `BI_ANALYTICS` when reporting and SQL dominate but pipeline evidence is weak
- with `ENGINEERING_BUILD_RUN` when backend/API/automation is present without clearly data-oriented context

### `BI_ANALYTICS`

**Intent**
- Capture dashboarding, business intelligence, data visualization, reporting surfaces, business-facing analytics.

**Strong signals**
- `business intelligence`
- `dashboard`
- `dashboards`
- `data visualization`
- `power bi`
- `tableau`
- `looker`

**Weak/contextual signals**
- `reporting`
- `kpi`
- `analysis`
- `sql`
- `excel`

**Representative BF examples**
- business intelligence analyst
- reporting analyst
- dashboard / KPI governance roles

**Main confusion risk**
- with `FINANCE_CONTROL`
- with `HR_TALENT_OPERATIONS`
- with `SUPPLY_CHAIN_PROCUREMENT`
- with `OPERATIONS_PROJECT_PMO`

This is the cluster most exposed to false absorption and therefore must be tightly constrained by context and tooling.

### `FINANCE_CONTROL`

**Intent**
- Capture management control, financial reporting, budgeting, accounting/control execution.

**Strong signals**
- `financial analysis`
- `financial reporting`
- `management control`
- `accounting`
- `budgeting`
- `controller`
- `contrôle de gestion`
- `controle de gestion`
- `sap`

**Weak/contextual signals**
- `excel`
- `reporting`
- `kpi`
- `analysis`
- `process`

**Representative BF examples**
- contrôleur de gestion
- finance controller
- trade finance / finance reporting roles

**Main confusion risk**
- with `BI_ANALYTICS` when Power BI/reporting/Excel appear without finance anchors
- with `OPERATIONS_PROJECT_PMO` for control/process-heavy roles

### `SALES_BUSINESS_DEVELOPMENT`

**Intent**
- Capture business development, B2B sales execution, account development, CRM-driven commercial roles.

**Strong signals**
- `b2b sales`
- `business development`
- `crm`
- `crm management`
- `salesforce`
- `hubspot`
- `prospecting`
- `lead generation`
- `account management`

**Weak/contextual signals**
- `reporting`
- `kpi`
- `analysis`
- `excel`
- `pipeline`

**Representative BF examples**
- business developer
- commercial export
- technico-commercial

**Main confusion risk**
- with future `Sales Ops`
- with `BI_ANALYTICS` when reporting/CRM dashboards dominate
- with `HR_TALENT_OPERATIONS` for talent acquisition/business manager hybrids

### `SUPPLY_CHAIN_PROCUREMENT`

**Intent**
- Capture purchasing, procurement, supplier management, inventory/supply execution.

**Strong signals**
- `supply chain`
- `supply chain management`
- `procurement`
- `purchasing`
- `acheteur`
- `approvisionnement`
- `supplier management`
- `inventory`
- `sap`

**Weak/contextual signals**
- `forecast`
- `excel`
- `reporting`
- `analysis`
- `performance`

**Representative BF examples**
- acheteur
- approvisionneur
- purchasing VIE

**Main confusion risk**
- with `OPERATIONS_PROJECT_PMO`
- with future `Supply Analytics`
- with `FINANCE_CONTROL` when cost/process evidence dominates

### `OPERATIONS_PROJECT_PMO`

**Intent**
- Capture project management, PMO, governance, process coordination, project operations.

**Strong signals**
- `project management`
- `pmo`
- `governance`
- `process improvement`
- `project manager`
- `chef de projet`
- `jira`
- `servicenow`

**Weak/contextual signals**
- `reporting`
- `excel`
- `kpi`
- `coordination`
- `documentation`

**Representative BF examples**
- project manager
- PMO-flavored operations roles
- governance / planning roles

**Main confusion risk**
- with `ENGINEERING_BUILD_RUN` in technical project roles
- with `SUPPLY_CHAIN_PROCUREMENT` in operations-heavy industrial contexts
- with `FINANCE_CONTROL` when budget/control terms dominate

### `ENGINEERING_BUILD_RUN`

**Intent**
- Capture technical engineering execution roles outside data-specific pipeline logic.

**Strong signals**
- `backend development`
- `mechanical design`
- `software testing`
- `version control`
- `containerization`
- `docker`
- `kubernetes`
- `azure`
- `linux`
- `devops`

**Weak/contextual signals**
- `sql`
- `analysis`
- `documentation`
- `automation`
- `quality`

**Representative BF examples**
- embedded software engineer
- ingénieur conception mécanique
- backend / cloud / infra flavored engineering roles

**Main confusion risk**
- with `DATA_ENGINEERING` when automation/API/SQL are present
- with `OPERATIONS_PROJECT_PMO` when project/process language dominates

### `HR_TALENT_OPERATIONS`

**Intent**
- Capture recruitment, onboarding, HR systems, HR project support, talent operations.

**Strong signals**
- `recruitment`
- `candidate sourcing`
- `talent management`
- `onboarding`
- `hr systems`
- `hris`
- `successfactors`
- `talent acquisition`

**Weak/contextual signals**
- `reporting`
- `analysis`
- `kpi`
- `sql`
- `communication`

**Representative BF examples**
- talent acquisition specialist
- HRIS project professional
- HR PMO / HR operations roles

**Main confusion risk**
- with `BI_ANALYTICS` when dashboards/reporting appear
- with `SALES_BUSINESS_DEVELOPMENT` when business manager/commercial vocabulary leaks in

---

## Weak / Contextual Signal Policy

The following signals must be treated as **contextual only** in V1:
- `sql`
- `excel`
- `kpi`
- `reporting`
- `analysis`
- `communication`
- `management`

They may reinforce a cluster only when one of the following is also true:
- a cluster-specific strong signal is present
- a coherent tooling bundle is present
- the title clearly anchors the business function
- the description contains domain-specific context words

---

## Forbidden Standalone Anchors

The following must not define a V1 cluster by themselves:
- `sql`
- `excel`
- `kpi`
- `reporting`
- `analysis`
- `communication`
- `management`
- `bi`

Reason:
- The PostgreSQL audit showed they are distributed across too many domains.
- Used alone, they recreate exactly the BI absorption problem V1 is meant to solve.

---

## Expected Cluster Confusions

### `DATA_ENGINEERING` vs `BI_ANALYTICS`

Main source of confusion:
- SQL + reporting + dashboards + APIs in mixed analytics engineer / data ops roles.

Resolution principle:
- prefer `DATA_ENGINEERING` only when pipeline / orchestration / warehouse / backend data evidence is explicit.

### `BI_ANALYTICS` vs `FINANCE_CONTROL`

Main source of confusion:
- Power BI / reporting / Excel / KPI also appear heavily in finance control.

Resolution principle:
- finance titles, SAP, budgeting, accounting, management control must override generic BI language.

### `BI_ANALYTICS` vs `HR_TALENT_OPERATIONS`

Main source of confusion:
- HR digital / HR dashboards / HRIS reporting roles.

Resolution principle:
- recruitment / talent / onboarding / HRIS anchors must dominate over generic reporting vocabulary.

### `SUPPLY_CHAIN_PROCUREMENT` vs `OPERATIONS_PROJECT_PMO`

Main source of confusion:
- project/process/performance language appears in both.

Resolution principle:
- supplier / procurement / stock / planning evidence should push toward supply.

### `ENGINEERING_BUILD_RUN` vs `DATA_ENGINEERING`

Main source of confusion:
- backend automation, APIs, containers, SQL.

Resolution principle:
- explicit data pipeline / warehouse / transformation context is required for `DATA_ENGINEERING`.

### `SALES_BUSINESS_DEVELOPMENT` vs future `Sales Ops`

Main source of confusion:
- CRM + KPI + reporting + pipeline terms.

Resolution principle:
- in V1, keep these roles inside `SALES_BUSINESS_DEVELOPMENT` unless the operational layer becomes independently stable later.

---

## Order of Implementation Recommended

Implementation order should follow both corpus density and risk reduction against data-centric drift.

### Phase 1
- `FINANCE_CONTROL`
- `SALES_BUSINESS_DEVELOPMENT`
- `SUPPLY_CHAIN_PROCUREMENT`

Reason:
- strong BF volume
- strong non-data value
- immediately reduces BI over-absorption

### Phase 2
- `ENGINEERING_BUILD_RUN`
- `OPERATIONS_PROJECT_PMO`
- `HR_TALENT_OPERATIONS`

Reason:
- strong or sufficient corpus support
- helps separate technical engineering and operational/project language from BI/data

### Phase 3
- recalibration of `DATA_ENGINEERING`
- recalibration of `BI_ANALYTICS`

Reason:
- these already exist conceptually, but must be tightened only after the non-data anchors are explicit

---

## Why We Do Not Create RevOps / Finance Ops / Supply Analytics Yet

These patterns were observed in the BF corpus, but they should remain **internal signals** in V1.

### Why not official clusters yet

- Their semantic boundaries are still overlapping with broader parent clusters.
- The current evidence is strong enough to detect them as sub-patterns, but not yet strong enough to make them stable public clusters.
- Creating them now would over-fragment the referential too early.
- This would increase confusion instead of reducing it.

### V1 treatment

- `RevOps` stays an internal pattern inside `SALES_BUSINESS_DEVELOPMENT` and adjacent CRM-heavy roles.
- `Finance Ops` stays an internal pattern inside `FINANCE_CONTROL`.
- `Supply Analytics` stays an internal pattern inside `SUPPLY_CHAIN_PROCUREMENT`.
- `HR Operations` stays an internal pattern inside `HR_TALENT_OPERATIONS`.
- `Backend Automation` stays an internal pattern inside `ENGINEERING_BUILD_RUN`.

---

## Criteria To Move Later From V1 Clusters To Sub-Clusters

Sub-clusters should only be created when all of the following are true:

### 1. Corpus volume is sufficient

- The candidate sub-pattern appears often enough in BF to be stable.
- It is not supported by just a handful of titles.

### 2. Strong signals are distinct

- The sub-pattern has a reusable set of anchors not already shared too broadly with the parent cluster.

### 3. Generic-signal leakage is controlled

- The sub-pattern is not mostly driven by `reporting`, `analysis`, `excel`, `sql`, `kpi`, or similar transversal terms.

### 4. Representative offers are coherent

- The representative sample clearly looks like one business family, not several adjacent ones mixed together.

### 5. Confusion matrix is acceptable

- The future sub-cluster does not create more ambiguity than it resolves.

### 6. Product value is explicit

- The sub-cluster would improve profile understanding or cluster precision in a way that is visible and useful, not just taxonomically elegant.

---

## Final Position

V1 should not try to become a universal ontology.

V1 should become:
- more representative of the actual BF corpus
- less dependent on generic analytics vocabulary
- less centered on data roles
- better at separating finance, sales, supply, operations, engineering, HR, and data

The proposed 8-cluster design is the smallest coherent step in that direction.
