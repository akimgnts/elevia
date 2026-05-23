# Elevia Métier Audit V0

- Mode: `full`
- Profiles audited: `14`
- Offers audited: `35`

## Lecture rapide

- Faux positifs observés: `7`
- Cas ambigus: `8`
- Impact outils: `{'cluster_changed': 0, 'confidence_dropped': 0}`
- Impact projets: `{'cluster_changed': 0, 'confidence_dropped': 0}`
- Impact expériences: `{'cluster_changed': 0, 'confidence_dropped': 0}`

## Signaux les plus fiables

- `sql`: 18
- `excel`: 5
- `power bi`: 4
- `reporting_stack`: 4
- `api`: 3
- `kpi`: 3
- `dashboard`: 3
- `tableau`: 3
- `business intelligence`: 2
- `dashboards`: 2

## Signaux trop génériques

- `sql`: 33
- `reporting`: 21
- `excel`: 18
- `kpi`: 11
- `analysis`: 9
- `python`: 6
- `analytics`: 4
- `dashboard`: 4
- `conversion`: 2
- `warehouse`: 1

## Faux positifs observés

- `cv_07_pierre_lemaire` → `BI_ANALYTICS` (conf=0.71)
- `cv_09_ines_barbier` → `BI_ANALYTICS` (conf=0.54)
- `vie_fixture_003` → `None` (conf=0.0)
- `vie_fixture_008` → `None` (conf=0.0)
- `vie_fixture_011` → `DATA_ENGINEERING` (conf=0.5)
- `sample20_238287` → `BI_ANALYTICS` (conf=0.71)
- `sample20_231644` → `BI_ANALYTICS` (conf=0.54)

## Clusters ambigus

- `cv_fixture_v0`: [{'cluster': 'BI_ANALYTICS', 'score': 28.5, 'eligible': True}, {'cluster': 'DATA_ENGINEERING', 'score': 27.0, 'eligible': True}]
- `cv_07_pierre_lemaire`: [{'cluster': 'BI_ANALYTICS', 'score': 8.5, 'eligible': True}, {'cluster': 'DATA_ENGINEERING', 'score': 0.0, 'eligible': False}]
- `cv_09_ines_barbier`: [{'cluster': 'BI_ANALYTICS', 'score': 6.5, 'eligible': True}, {'cluster': 'DATA_ENGINEERING', 'score': 0.0, 'eligible': False}]
- `vie_fixture_004`: [{'cluster': 'BI_ANALYTICS', 'score': 12.5, 'eligible': True}, {'cluster': 'DATA_ENGINEERING', 'score': 12.0, 'eligible': True}]
- `vie_fixture_009`: []
- `vie_fixture_011`: [{'cluster': 'DATA_ENGINEERING', 'score': 6.0, 'eligible': True}, {'cluster': 'BI_ANALYTICS', 'score': 0.0, 'eligible': False}]
- `sample20_238287`: [{'cluster': 'BI_ANALYTICS', 'score': 8.5, 'eligible': True}, {'cluster': 'PRODUCT_ANALYTICS', 'score': 1.0, 'eligible': False}]
- `sample20_231644`: [{'cluster': 'BI_ANALYTICS', 'score': 6.5, 'eligible': True}, {'cluster': 'DATA_ENGINEERING', 'score': 3.0, 'eligible': False}]

## Signaux manquants / limites

- No real local product-analytics tool signal observed (Amplitude/Mixpanel absent in corpus)
- Airflow/dbt appear under-used in the audited corpus; DATA_ENGINEERING still leans on ETL/API/SQL/PostgreSQL
- `reporting` remains too generic to discriminate BI vs non-BI alone
- `bi` is too short and behaves like a noisy strong signal in out-of-scope texts

## Focus frontières métier

- `DATA_ENGINEERING ↔ BI_ANALYTICS`: 12 cas notables
- `BI_ANALYTICS ↔ PRODUCT_ANALYTICS`: 12 cas notables
- DE/BI `sample_delta_txt`: [{'cluster': 'DATA_ENGINEERING', 'score': 24.0, 'eligible': True}, {'cluster': 'BI_ANALYTICS', 'score': 6.5, 'eligible': True}]
- DE/BI `cv_fixture_v0`: [{'cluster': 'BI_ANALYTICS', 'score': 28.5, 'eligible': True}, {'cluster': 'DATA_ENGINEERING', 'score': 27.0, 'eligible': True}]
- DE/BI `golden_01`: [{'cluster': 'BI_ANALYTICS', 'score': 9.0, 'eligible': True}, {'cluster': 'DATA_ENGINEERING', 'score': 4.0, 'eligible': False}]
- DE/BI `akim_guentas_matching`: [{'cluster': 'BI_ANALYTICS', 'score': 22.0, 'eligible': True}, {'cluster': 'DATA_ENGINEERING', 'score': 7.0, 'eligible': True}]
- DE/BI `cv_07_pierre_lemaire`: [{'cluster': 'BI_ANALYTICS', 'score': 8.5, 'eligible': True}, {'cluster': 'DATA_ENGINEERING', 'score': 0.0, 'eligible': False}]
- DE/BI `cv_09_ines_barbier`: [{'cluster': 'BI_ANALYTICS', 'score': 6.5, 'eligible': True}, {'cluster': 'DATA_ENGINEERING', 'score': 0.0, 'eligible': False}]
- BI/Product `sample_delta_txt`: [{'cluster': 'DATA_ENGINEERING', 'score': 24.0, 'eligible': True}, {'cluster': 'BI_ANALYTICS', 'score': 6.5, 'eligible': True}]
- BI/Product `cv_fixture_v0`: [{'cluster': 'BI_ANALYTICS', 'score': 28.5, 'eligible': True}, {'cluster': 'DATA_ENGINEERING', 'score': 27.0, 'eligible': True}]
- BI/Product `golden_01`: [{'cluster': 'BI_ANALYTICS', 'score': 9.0, 'eligible': True}, {'cluster': 'DATA_ENGINEERING', 'score': 4.0, 'eligible': False}]
- BI/Product `akim_guentas_matching`: [{'cluster': 'BI_ANALYTICS', 'score': 22.0, 'eligible': True}, {'cluster': 'DATA_ENGINEERING', 'score': 7.0, 'eligible': True}]
- BI/Product `cv_07_pierre_lemaire`: [{'cluster': 'BI_ANALYTICS', 'score': 8.5, 'eligible': True}, {'cluster': 'DATA_ENGINEERING', 'score': 0.0, 'eligible': False}]
- BI/Product `cv_09_ines_barbier`: [{'cluster': 'BI_ANALYTICS', 'score': 6.5, 'eligible': True}, {'cluster': 'DATA_ENGINEERING', 'score': 0.0, 'eligible': False}]

## Détail profils

- `sample_delta_txt` → `DATA_ENGINEERING` conf `1.0`
  strong: {'DATA_ENGINEERING': ['data engineer', 'etl', 'pipeline', 'pipelines', 'api'], 'BI_ANALYTICS': ['bi'], 'PRODUCT_ANALYTICS': ['a/b testing']}
  weak: {'DATA_ENGINEERING': ['sql'], 'BI_ANALYTICS': ['sql'], 'PRODUCT_ANALYTICS': ['sql']}
  tools: {'DATA_ENGINEERING': ['airflow', 'dbt', 'sql'], 'BI_ANALYTICS': ['power bi', 'sql'], 'PRODUCT_ANALYTICS': ['sql']}
  patterns: {'DATA_ENGINEERING': ['orchestrated_data_pipeline', 'warehouse_transformation_stack'], 'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': []}
- `cv_fixture_v0` → `BI_ANALYTICS` conf `1.0`
  strong: {'BI_ANALYTICS': ['bi', 'dashboard', 'dashboards', 'kpi'], 'DATA_ENGINEERING': ['etl', 'data pipeline', 'pipeline', 'pipelines', 'api', 'apis'], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['reporting', 'sql', 'excel', 'analysis', 'analytics'], 'DATA_ENGINEERING': ['sql', 'python', 'warehouse'], 'PRODUCT_ANALYTICS': ['dashboard', 'kpi', 'sql', 'analytics']}
  tools: {'BI_ANALYTICS': ['power bi', 'tableau', 'excel', 'sql'], 'DATA_ENGINEERING': ['postgresql', 'python', 'sql'], 'PRODUCT_ANALYTICS': ['sql']}
  patterns: {'BI_ANALYTICS': ['power_bi_kpi_dashboard', 'reporting_stack'], 'DATA_ENGINEERING': ['etl_api_postgres_pipeline'], 'PRODUCT_ANALYTICS': []}
- `golden_01` → `BI_ANALYTICS` conf `0.75`
  strong: {'BI_ANALYTICS': ['bi'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['sql', 'excel'], 'DATA_ENGINEERING': ['sql', 'python'], 'PRODUCT_ANALYTICS': ['sql']}
  tools: {'BI_ANALYTICS': ['excel', 'sql'], 'DATA_ENGINEERING': ['python', 'sql'], 'PRODUCT_ANALYTICS': ['sql']}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `golden_02` → `None` conf `0.0`
  strong: {'DATA_ENGINEERING': [], 'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': []}
  weak: {'DATA_ENGINEERING': ['sql', 'python'], 'BI_ANALYTICS': ['sql'], 'PRODUCT_ANALYTICS': ['sql']}
  tools: {'DATA_ENGINEERING': ['python', 'sql'], 'BI_ANALYTICS': ['sql'], 'PRODUCT_ANALYTICS': ['sql']}
  patterns: {'DATA_ENGINEERING': [], 'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': []}
- `akim_guentas_matching` → `BI_ANALYTICS` conf `1.0`
  strong: {'BI_ANALYTICS': ['business intelligence', 'bi', 'kpi'], 'DATA_ENGINEERING': ['api'], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['reporting', 'sql', 'excel', 'analysis'], 'DATA_ENGINEERING': ['sql', 'python'], 'PRODUCT_ANALYTICS': ['kpi', 'sql']}
  tools: {'BI_ANALYTICS': ['power bi', 'tableau', 'excel', 'sql'], 'DATA_ENGINEERING': ['python', 'sql'], 'PRODUCT_ANALYTICS': ['sql']}
  patterns: {'BI_ANALYTICS': ['reporting_stack'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `cv_01_lina_morel` → `None` conf `0.0`
  strong: {'BI_ANALYTICS': ['bi'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['reporting', 'excel'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  tools: {'BI_ANALYTICS': ['excel'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `cv_02_hugo_renaud` → `None` conf `0.0`
  strong: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['excel'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  tools: {'BI_ANALYTICS': ['excel'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `cv_03_sarah_el_mansouri` → `None` conf `0.0`
  strong: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['reporting', 'excel'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  tools: {'BI_ANALYTICS': ['excel'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `cv_04_benoit_caron` → `None` conf `0.0`
  strong: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['excel'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  tools: {'BI_ANALYTICS': ['tableau', 'excel'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `cv_05_camille_vasseur` → `None` conf `0.0`
  strong: {'BI_ANALYTICS': ['bi'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  tools: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `cv_06_yasmine_haddad` → `None` conf `0.0`
  strong: {'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': [], 'DATA_ENGINEERING': []}
  weak: {'BI_ANALYTICS': ['reporting', 'excel'], 'PRODUCT_ANALYTICS': ['conversion'], 'DATA_ENGINEERING': []}
  tools: {'BI_ANALYTICS': ['tableau', 'looker', 'excel'], 'PRODUCT_ANALYTICS': [], 'DATA_ENGINEERING': []}
  patterns: {'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': [], 'DATA_ENGINEERING': []}
- `cv_07_pierre_lemaire` → `BI_ANALYTICS` conf `0.71`
  strong: {'BI_ANALYTICS': ['bi'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['reporting', 'excel'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  tools: {'BI_ANALYTICS': ['power bi', 'tableau', 'excel'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `cv_08_amel_dufour` → `None` conf `0.0`
  strong: {'BI_ANALYTICS': ['bi'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['excel'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  tools: {'BI_ANALYTICS': ['excel'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `cv_09_ines_barbier` → `BI_ANALYTICS` conf `0.54`
  strong: {'BI_ANALYTICS': ['bi'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['excel'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  tools: {'BI_ANALYTICS': ['tableau', 'excel'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}

## Détail offres

- `vie_fixture_001` Data Analyst VIE - KPI & Reporting → `BI_ANALYTICS` conf `1.0`
  strong: {'BI_ANALYTICS': ['bi', 'dashboard', 'kpi'], 'DATA_ENGINEERING': ['api'], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['reporting', 'sql', 'excel', 'analysis'], 'DATA_ENGINEERING': ['sql'], 'PRODUCT_ANALYTICS': ['dashboard', 'kpi', 'sql']}
  patterns: {'BI_ANALYTICS': ['power_bi_kpi_dashboard', 'reporting_stack'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `vie_fixture_002` Business Intelligence Analyst VIE - Tableau → `BI_ANALYTICS` conf `1.0`
  strong: {'BI_ANALYTICS': ['business intelligence', 'bi', 'dashboard', 'dashboards', 'kpi', 'data visualization'], 'PRODUCT_ANALYTICS': [], 'DATA_ENGINEERING': []}
  weak: {'BI_ANALYTICS': ['reporting', 'sql'], 'PRODUCT_ANALYTICS': ['dashboard', 'kpi', 'sql'], 'DATA_ENGINEERING': ['sql']}
  patterns: {'BI_ANALYTICS': ['reporting_stack'], 'PRODUCT_ANALYTICS': [], 'DATA_ENGINEERING': []}
- `vie_fixture_003` Data Ops Analyst VIE - Normalisation → `None` conf `0.0`
  strong: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['reporting', 'sql'], 'DATA_ENGINEERING': ['sql', 'python'], 'PRODUCT_ANALYTICS': ['sql']}
  patterns: {'BI_ANALYTICS': ['reporting_stack'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `vie_fixture_004` Analytics Engineer VIE - API & BI → `BI_ANALYTICS` conf `1.0`
  strong: {'BI_ANALYTICS': ['bi', 'kpi'], 'DATA_ENGINEERING': ['api', 'apis'], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['reporting', 'sql', 'analysis', 'analytics'], 'DATA_ENGINEERING': ['sql', 'python'], 'PRODUCT_ANALYTICS': ['kpi', 'sql', 'analytics']}
  patterns: {'BI_ANALYTICS': ['reporting_stack'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `vie_fixture_005` Reporting Analyst VIE - Power BI → `BI_ANALYTICS` conf `1.0`
  strong: {'BI_ANALYTICS': ['bi', 'kpi'], 'PRODUCT_ANALYTICS': [], 'DATA_ENGINEERING': []}
  weak: {'BI_ANALYTICS': ['reporting', 'excel', 'analysis'], 'PRODUCT_ANALYTICS': ['kpi'], 'DATA_ENGINEERING': []}
  patterns: {'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': [], 'DATA_ENGINEERING': []}
- `vie_fixture_006` Business Analyst VIE - Operations → `None` conf `0.0`
  strong: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['reporting', 'excel'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `vie_fixture_007` Data Reporting Analyst VIE - CRM → `BI_ANALYTICS` conf `1.0`
  strong: {'BI_ANALYTICS': ['dashboard', 'dashboards', 'kpi', 'data visualization'], 'PRODUCT_ANALYTICS': [], 'DATA_ENGINEERING': []}
  weak: {'BI_ANALYTICS': ['reporting', 'sql', 'excel'], 'PRODUCT_ANALYTICS': ['dashboard', 'kpi', 'sql'], 'DATA_ENGINEERING': ['sql']}
  patterns: {'BI_ANALYTICS': ['reporting_stack'], 'PRODUCT_ANALYTICS': [], 'DATA_ENGINEERING': []}
- `vie_fixture_008` Data Ops VIE - Inventory → `None` conf `0.0`
  strong: {'BI_ANALYTICS': ['bi'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['sql'], 'DATA_ENGINEERING': ['sql'], 'PRODUCT_ANALYTICS': ['sql']}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `vie_fixture_009` Product Ops Analyst VIE - Metrics → `None` conf `0.0`
  strong: {'BI_ANALYTICS': ['kpi'], 'PRODUCT_ANALYTICS': [], 'DATA_ENGINEERING': []}
  weak: {'BI_ANALYTICS': ['reporting', 'analysis'], 'PRODUCT_ANALYTICS': ['kpi'], 'DATA_ENGINEERING': []}
  patterns: {'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': [], 'DATA_ENGINEERING': []}
- `vie_fixture_010` Supply Analyst VIE - Forecasting → `None` conf `0.0`
  strong: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['reporting', 'excel', 'analysis'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `vie_fixture_011` ML Engineer VIE - Deep Learning → `DATA_ENGINEERING` conf `0.5`
  strong: {'DATA_ENGINEERING': ['pipeline', 'pipelines'], 'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': []}
  weak: {'DATA_ENGINEERING': [], 'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'DATA_ENGINEERING': [], 'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': []}
- `vie_fixture_012` Backend Engineer VIE - Golang → `None` conf `0.0`
  strong: {'DATA_ENGINEERING': [], 'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': []}
  weak: {'DATA_ENGINEERING': [], 'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'DATA_ENGINEERING': [], 'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': []}
- `vie_fixture_013` DevOps Engineer VIE - Cloud → `None` conf `0.0`
  strong: {'BI_ANALYTICS': ['bi'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `vie_fixture_014` Quant Researcher VIE - Finance → `None` conf `0.0`
  strong: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `vie_fixture_015` Fullstack Engineer VIE - React/Node → `None` conf `0.0`
  strong: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `sample20_238371` VIE Functional Excellence Support (H/F) → `None` conf `0.0`
  strong: {'BI_ANALYTICS': ['bi'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['excel'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `sample20_238287` TALENT ACQUISITION SPECIALIST BERLIN (H/F) → `BI_ANALYTICS` conf `0.71`
  strong: {'BI_ANALYTICS': ['bi', 'kpi'], 'PRODUCT_ANALYTICS': [], 'DATA_ENGINEERING': []}
  weak: {'BI_ANALYTICS': ['reporting'], 'PRODUCT_ANALYTICS': ['kpi', 'conversion'], 'DATA_ENGINEERING': []}
  patterns: {'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': [], 'DATA_ENGINEERING': []}
- `sample20_236293` Field Engineer (H/F) → `None` conf `0.0`
  strong: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
- `sample20_227195` V.I.E JUNIOR ACCOUNTANT (M/W) (H/F) → `None` conf `0.0`
  strong: {'DATA_ENGINEERING': ['api'], 'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': []}
  weak: {'DATA_ENGINEERING': [], 'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': []}
  patterns: {'DATA_ENGINEERING': [], 'BI_ANALYTICS': [], 'PRODUCT_ANALYTICS': []}
- `sample20_231644` JR HR PMO (H/F) → `BI_ANALYTICS` conf `0.54`
  strong: {'BI_ANALYTICS': ['bi', 'kpi'], 'DATA_ENGINEERING': ['pipeline'], 'PRODUCT_ANALYTICS': []}
  weak: {'BI_ANALYTICS': ['reporting'], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': ['kpi']}
  patterns: {'BI_ANALYTICS': [], 'DATA_ENGINEERING': [], 'PRODUCT_ANALYTICS': []}
