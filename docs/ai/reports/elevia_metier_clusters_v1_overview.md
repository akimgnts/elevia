# Elevia Metier Clusters V1 Overview

- Registry version: `elevia_metier_v0_finance_control`
- Registry path: `/Users/akimguentas/Dev/elevia-compass/apps/api/src/compass/registry/elevia_metier_registry.json`
- Clusters shown: `8`

This is a DEV/debug-only overview of the current official Elevia V1 clusters.

## `DATA_ENGINEERING`

**Strong signals**
- `data engineer`
- `etl`
- `elt`
- `data pipeline`
- `data pipelines`
- `pipeline`
- `pipelines`
- `orchestration`
- `api`
- `apis`
- `ingestion`
- `batch processing`
- `streaming`
- `data modeling`

**Weak/contextual signals**
- `sql`
- `python`
- `analytics engineering`
- `backend data`
- `warehouse`
- `data platform`
- `backend`
- `infrastructure`
- `reliability`
- `orchestrated workflows`
- `data architecture`

**Forbidden standalone anchors**
_none_

**Project patterns**
- `etl_api_postgres_pipeline`: `etl`, `api`, `postgresql`
- `orchestrated_data_pipeline`: `airflow`, `pipeline`
- `warehouse_transformation_stack`: `dbt`, `sql`

**Negative signals**
- `cohort analysis`
- `experimentation`
- `ab testing`
- `a/b testing`
- `product manager`
- `recruitment`
- `candidate sourcing`

**Representative examples**
_none_

## `BI_ANALYTICS`

**Strong signals**
- `business intelligence`
- `bi`
- `dashboard`
- `dashboards`
- `kpi`
- `executive reporting`
- `self service analytics`
- `data visualization`

**Weak/contextual signals**
- `reporting`
- `sql`
- `excel`
- `analysis`
- `analytics`
- `stakeholder reporting`
- `business stakeholders`
- `executive visibility`
- `performance tracking`
- `management reporting`

**Forbidden standalone anchors**
_none_

**Project patterns**
- `power_bi_kpi_dashboard`: `power bi`, `kpi`, `dashboard`
- `reporting_stack`: `reporting`, `sql`

**Negative signals**
- `product analytics`
- `cohort analysis`
- `experimentation`
- `feature adoption`
- `retention`
- `funnel`

**Representative examples**
_none_

## `FINANCE_CONTROL`

**Strong signals**
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

**Weak/contextual signals**
- `excel`
- `reporting`
- `analysis`
- `kpi`
- `management`
- `dashboard`
- `variance analysis`
- `monthly close`
- `budget follow-up`
- `p&l`
- `profitability`
- `forecasting`
- `cost control`
- `financial close`

**Forbidden standalone anchors**
- `excel`
- `reporting`
- `analysis`
- `kpi`
- `sql`

**Project patterns**
- `sap_budgeting_reporting`: `sap`, `budgeting`, `financial reporting`
- `controlling_close_cycle`: `controlling`, `monthly close`

**Negative signals**
- `cohort analysis`
- `experimentation`
- `product analytics`
- `candidate sourcing`
- `talent acquisition`
- `supplier management`
- `procurement`
- `logistics`

**Representative examples**
- `controleur de gestion`
- `finance controller`
- `vie management controller`

## `SALES_BUSINESS_DEVELOPMENT`

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
- `sales development`
- `commercial development`

**Weak/contextual signals**
- `reporting`
- `analysis`
- `excel`
- `kpi`
- `communication`
- `management`
- `dashboard`
- `pipeline follow-up`
- `client portfolio`
- `deal flow`
- `revenue growth`
- `commercial performance`
- `sales cycle`

**Forbidden standalone anchors**
- `excel`
- `reporting`
- `analysis`
- `kpi`
- `communication`
- `management`

**Project patterns**
- `crm_prospecting_growth`: `crm`, `prospecting`, `account management`
- `salesforce_pipeline_cycle`: `salesforce`, `pipeline`, `sales`

**Negative signals**
- `candidate sourcing`
- `recruitment`
- `procurement`
- `supply chain`
- `management control`

**Representative examples**
- `business developer`
- `commercial export`
- `technico-commercial`

## `SUPPLY_CHAIN_PROCUREMENT`

**Strong signals**
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

**Weak/contextual signals**
- `reporting`
- `analysis`
- `excel`
- `kpi`
- `management`
- `dashboard`
- `supplier governance`
- `stock planning`
- `inventory coordination`
- `sourcing operations`
- `procurement planning`
- `supply flows`

**Forbidden standalone anchors**
- `excel`
- `reporting`
- `analysis`
- `kpi`
- `management`

**Project patterns**
- `procurement_supplier_inventory`: `procurement`, `supplier management`, `inventory`
- `sap_supply_logistics`: `sap supply`, `logistics`

**Negative signals**
- `financial reporting`
- `management control`
- `candidate sourcing`
- `recruitment`

**Representative examples**
- `acheteur`
- `approvisionneur`
- `purchasing vie`

## `OPERATIONS_PROJECT_PMO`

**Strong signals**
- `project management`
- `pmo`
- `governance`
- `process improvement`
- `operational coordination`
- `project coordination`
- `service management`
- `process governance`

**Weak/contextual signals**
- `reporting`
- `analysis`
- `excel`
- `kpi`
- `communication`
- `management`
- `dashboard`
- `project reporting`
- `cross-functional coordination`
- `operational follow-up`
- `project streams`
- `process standardization`
- `governance cadence`

**Forbidden standalone anchors**
- `excel`
- `reporting`
- `analysis`
- `kpi`
- `communication`
- `management`

**Project patterns**
- `pmo_governance_jira`: `pmo`, `governance`, `jira`
- `operations_process_coordination`: `process improvement`, `operational coordination`

**Negative signals**
- `candidate sourcing`
- `recruitment`
- `b2b sales`
- `supply chain`

**Representative examples**
- `pmo coordinator`
- `project operations coordinator`
- `operations project manager`

## `ENGINEERING_BUILD_RUN`

**Strong signals**
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

**Weak/contextual signals**
- `reporting`
- `analysis`
- `excel`
- `kpi`
- `communication`
- `management`
- `python`
- `deployment automation`
- `platform reliability`
- `build pipelines`
- `run reliability`
- `cloud services`
- `production support`

**Forbidden standalone anchors**
- `excel`
- `reporting`
- `analysis`
- `kpi`
- `communication`
- `management`

**Project patterns**
- `container_platform_reliability`: `docker`, `kubernetes`, `containerization`
- `backend_devops_stack`: `backend development`, `devops`

**Negative signals**
- `etl`
- `data pipeline`
- `cohort analysis`
- `candidate sourcing`

**Representative examples**
- `backend engineer`
- `devops engineer`
- `mechanical design engineer`

## `HR_TALENT_OPERATIONS`

**Strong signals**
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

**Weak/contextual signals**
- `reporting`
- `analysis`
- `excel`
- `kpi`
- `communication`
- `management`
- `dashboard`
- `hiring workflows`
- `recruitment funnel`
- `employee lifecycle`
- `hr governance`
- `people processes`
- `talent operations`

**Forbidden standalone anchors**
- `excel`
- `reporting`
- `analysis`
- `kpi`
- `communication`
- `management`

**Project patterns**
- `recruitment_onboarding_systems`: `recruitment`, `onboarding`, `hr systems`
- `talent_operations_workforce`: `talent management`, `workforce planning`

**Negative signals**
- `b2b sales`
- `procurement`
- `management control`
- `etl`

**Representative examples**
- `talent acquisition specialist`
- `hr coordinator`
- `people operations specialist`

## Notes

The registry currently contains non-V1 clusters excluded from this overview:
- `PRODUCT_ANALYTICS`
