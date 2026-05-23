# Elevia PostgreSQL Multi-Domain Audit v1

- Generated at: `2026-05-11T10:36:41.901407+00:00`
- Scope: `clean_offers WHERE source='business_france' AND COALESCE(is_active, TRUE)=TRUE`
- Mode: `full`
- Read-only: `True`

## Methodology

- Approach: `SQL-first with light Python synthesis`
- Read active Business France offers from clean_offers
- Join offer_domain_enrichment read-only on (source, external_id)
- Join offer_skills if available, otherwise fact_offer_skills if available
- Aggregate volume, titles, skills, tools, contextual keywords and representative examples by domain
- Compute noisy generic signal spread and emerging pattern counts in Python

## Domain Distribution

- `data`: 65 offers (7.42%)
- `finance`: 107 offers (12.21%)
- `sales`: 129 offers (14.73%)
- `marketing`: 20 offers (2.28%)
- `hr`: 39 offers (4.45%)
- `supply`: 115 offers (13.13%)
- `operations`: 77 offers (8.79%)
- `engineering`: 272 offers (31.05%)
- `legal`: 12 offers (1.37%)
- `admin`: 28 offers (3.2%)
- `other`: 12 offers (1.37%)

## Representation Strength

- Well represented: `['data', 'finance', 'sales', 'supply', 'operations', 'engineering']`
- Weak domains: `['legal', 'other']`

## BI Absorption Risk

- BI/data-oriented labels absorb cross-functional offers because generic analytics vocabulary is spread across finance, hr, operations, supply and sales.
- SQL becomes discriminant only when paired with warehouse/API/ETL/backend signals.
- Excel and reporting become discriminant only when paired with finance control, supply forecasting, HRIS, CRM or campaign context.
- KPI alone is cross-domain; it needs product, finance, sales, operations or marketing anchors.

## Generic Signals Problematiques

- `reporting` total=222 | finance=47, sales=38, engineering=35, data=30, supply=27
- `analysis` total=300 | engineering=71, sales=59, finance=41, data=38, supply=35
- `communication` total=146 | engineering=31, sales=25, operations=20, supply=17, marketing=11
- `management` total=526 | engineering=107, supply=100, sales=86, finance=63, operations=60
- `sql` total=21 | engineering=9, data=7, hr=2, marketing=2, admin=1
- `excel` total=34 | finance=18, operations=5, data=5, engineering=2, supply=2
- `kpi` total=61 | finance=12, supply=12, engineering=11, sales=8, operations=7

## Emerging Patterns

- `Compliance`: 47 offers | domains=['admin', 'data', 'engineering', 'finance', 'hr', 'legal', 'operations', 'sales', 'supply']
- `Finance Ops`: 39 offers | domains=['finance']
- `Project Operations`: 23 offers | domains=['operations']
- `Backend Automation`: 18 offers | domains=['engineering']
- `Sales Ops`: 16 offers | domains=['sales']
- `HR Operations`: 14 offers | domains=['hr']
- `RevOps`: 10 offers | domains=['hr', 'marketing', 'sales', 'supply']
- `Supply Analytics`: 10 offers | domains=['supply']
- `Marketing Ops`: 5 offers | domains=['marketing']
- `Cybersecurity`: 2 offers | domains=['engineering']

## Domain Details

### data
- Volume: `65`
- Top titles: ['Data Scientist (H/F)', 'Business Analyst (H/F)', 'SAP Functional Analyst - Spanish Speaker F/M (H/F)', 'Data engineer (H/F)', 'Analyste SOC & CTI (H/F)']
- Top skills: ['data analysis', 'business intelligence', 'project management', 'power bi', 'sql querying', 'process optimization', 'machine learning']
- Top tools: ['python', 'power bi', 'sql', 'excel', 'spark', 'aws', 'tableau']
- Context keywords: ['solutions', 'donnees', 'equipes', 'processes', 'clients', 'projects', 'teams']
- Discriminant signals: ['machine learning', 'data engineering', 'spark']
- Generic/noisy signals: ['analysis', 'management', 'reporting', 'communication', 'sql', 'kpi', 'excel']
- Representative offers:
  - `242078` AI Transformation & Adoption Manager (H/F) (SERVIER INTERNATIONAL, ARGENTINE)
  - `238422` Corporate Credit Analyst (H/F) (BANQUE FEDERATIVE DU CREDIT MUTUEL, ALLEMAGNE)
  - `242187` Privacy Analyst (H/F) (M&L DISTRIBUTION (FRANCE) S.A.R.L., ETATS-UNIS)

### finance
- Volume: `107`
- Top titles: ['CONTROLEUR DE GESTION (H/F)', 'Ingénieur qualité (H/F)', 'INGENIEUR QUALITE H/F (H/F)', 'VIE Management Controller (H/F)', 'Finance controller (H/F)']
- Top skills: ['business intelligence', 'budgeting', 'excel', 'compliance', 'process optimization', 'project management', 'financial analysis']
- Top tools: ['excel', 'sap', 'power bi', 'crm', 'powerpoint', 'linux', 'python']
- Context keywords: ['gestion', 'controle', 'suivi', 'financial', 'qualite', 'finance', 'groupe']
- Discriminant signals: ['financial analysis', 'financial reporting', 'management control', 'accounting basics']
- Generic/noisy signals: ['management', 'reporting', 'analysis', 'excel', 'kpi', 'communication']
- Representative offers:
  - `242154` Trade Finance Junior (H/F) (ULTIMAT, COTE D'IVOIRE)
  - `242156` Contrôleur de Gestion (H/F) (INNOHA, ESPAGNE)
  - `236331` Contrôleur des ventes et des opérations (S&OP) (H/F) (RAIL LOGISTICS EUROPE, BELGIQUE)

### sales
- Volume: `129`
- Top titles: ['BUSINESS DEVELOPER (H/F)', 'BUSINESS MANAGER (H/F)', 'REPRESENTANT TECHNICO COMMERCIAL (H/F)', 'Accounting Specialist (H/F)', 'COMMERCIAL TERRAIN (H/F)']
- Top skills: ['b2b sales', 'market analysis', 'crm management', 'project management', 'business development', 'b2b prospecting', 'salesforce']
- Top tools: ['crm', 'salesforce', 'hubspot', 'sap', 'excel', 'powerpoint']
- Context keywords: ['clients', 'commercial', 'sales', 'development', 'developpement', 'notre', 'client']
- Discriminant signals: ['b2b sales', 'market analysis', 'crm', 'crm management', 'salesforce', 'business development', 'b2b prospecting']
- Generic/noisy signals: ['management', 'analysis', 'reporting', 'communication', 'kpi', 'excel']
- Representative offers:
  - `242493` COMMERCIAL EXPORT (H/F) (CITE MARINE, ETATS-UNIS)
  - `238425` INTERNATIONAL BUSINESS DEVELOPPER (H/F) (HEF MECANIQUE ET SURFACES, INDE)
  - `232231` REPRESENTANT TECHNICO COMMERCIAL (H/F) (EJ PICARDIE, ESPAGNE)

### marketing
- Volume: `20`
- Top titles: ['REGIONAL DEALERS COMMUNICATION SPECIALIST H/F (H/F)', 'GRAPHIC DESIGNER (H/F)', 'Consultant SEA/SMA (H/F)', 'CHEF DE PROJET MARKETING DIGITAL (H/F)', 'Marketing Campaign Planning Officer (H/F)']
- Top skills: ['data analysis', 'salesforce', 'crm management', 'business intelligence', 'digital marketing', 'project management', 'lead generation']
- Top tools: ['crm', 'salesforce', 'hubspot', 'sql', 'powerpoint', 'looker', 'looker studio']
- Context keywords: ['marketing', 'product', 'service', 'across', 'digital', 'performance', 'developpement']
- Discriminant signals: []
- Generic/noisy signals: ['management', 'communication', 'analysis', 'reporting', 'kpi', 'sql']
- Representative offers:
  - `230774` REGIONAL DEALERS COMMUNICATION SPECIALIST H/F (H/F) (CNH INDUSTRIAL FRANCE, ITALIE)
  - `238205` GTM ENGINEER (GROWTH OPS) HF (H/F) (EFE INTERNATIONAL, ETATS-UNIS)
  - `242412` Lead/Demand Generation Specialist (H/F) (AMARIS FRANCE SAS, ESPAGNE)

### hr
- Volume: `39`
- Top titles: ['JR HR PMO (H/F)', 'BUSINESS MANAGER (H/F)', 'CONSULTANT.E EN RECRUTEMENT (H/F)', 'Talent Acquisition Specialist (H/F)', 'BUSINESS MANAGER BXL H/F (H/F)']
- Top skills: ['recruitment', 'business intelligence', 'b2b sales', 'data analysis', 'project management', 'candidate sourcing', 'international environment']
- Top tools: ['sap', 'crm', 'sql', 'successfactors', 'salesforce', 'python']
- Context keywords: ['talent', 'recrutement', 'equipe', 'global', 'votre', 'manager', 'acquisition']
- Discriminant signals: ['candidate sourcing', 'talent management', 'hr project tracking', 'hr systems and tools', 'hr reporting and dashboards']
- Generic/noisy signals: ['management', 'reporting', 'analysis', 'communication', 'kpi', 'sql']
- Representative offers:
  - `232562` BUSINESS MANAGER (H/F) (ALPINEO CONSULTING LYON, SUISSE)
  - `242326` HRIS Project Professional (H/F) (OPMOBILITY GESTION, ALLEMAGNE)
  - `231640` JR HR PMO (H/F) (TYCO ELECTRONICS FRANCE SAS, SUISSE)

### supply
- Volume: `115`
- Top titles: ['Purchasing VIE (H/F)', 'Acheteur (H/F)', 'Fleet Coordinator (H/F)', 'INGENIEUR MECANIQUE - INGENIERIE H/F (H/F)', 'OPERATIONS MANAGER (H/F)']
- Top skills: ['project management', 'supply chain management', 'sap', 'market analysis', 'compliance', 'budgeting', 'process optimization']
- Top tools: ['sap', 'power bi', 'salesforce', 'excel', 'crm', 'spark', 'tableau']
- Context keywords: ['supply', 'chain', 'performance', 'purchasing', 'procurement', 'supplier', 'production']
- Discriminant signals: ['supply chain management', 'supplier relationship management', 'procurement basics']
- Generic/noisy signals: ['management', 'analysis', 'reporting', 'communication', 'kpi', 'excel']
- Representative offers:
  - `242199` ACHETEUR(SE) (H/F) (FORTIL GROUP, BELGIQUE)
  - `232738` ACHETEUR(SE) - APPROVISIONNEUR(SE) (H/F) (TWYCE, CANADA)
  - `242419` INGÉNIEUR AMÉLIORATION CONTINUE (H/F) (FORTIL GROUP, BELGIQUE)

### operations
- Volume: `77`
- Top titles: ['PROJECT MANAGER (H/F)', 'JUNIOR WAGON ENGINEER (H/F)', 'INGENIEUR CONCEPTION ELECTRONIQUE (H/F)', 'ADJOINT CHEF DE FERME H/F (H/F)', 'CHEF(FE) DE PROJET ELECTRICITÉ (H/F)']
- Top skills: ['project management', 'business intelligence', 'process optimization', 'budgeting', 'compliance', 'documentation', 'excel']
- Top tools: ['excel', 'jira', 'power bi', 'sap', 'tableau', 'powerpoint', 'servicenow']
- Context keywords: ['project', 'manager', 'projet', 'projets', 'suivi', 'operations', 'equipes']
- Discriminant signals: ['budget tracking']
- Generic/noisy signals: ['management', 'reporting', 'communication', 'analysis', 'kpi', 'excel']
- Representative offers:
  - `238393` Conseiller/Conseillère en affaires publiques (H/F) (GEOPOST, BELGIQUE)
  - `242367` Responsable financier H/F/X (H/F) (INVENTEC PERFORMANCE CHEMICALS, JAPON)
  - `238074` Approval Planner (H/F) (EIFFAGE ENERGIE SYSTEMES - GESTION & DEVELOPPEMENT, ALLEMAGNE)

### engineering
- Volume: `272`
- Top titles: ['Embedded Software Engineer (H/F)', 'INGÉNIEUR CONCEPTION MÉCANIQUE (H/F)', 'Ingénieur qualité (H/F)', 'INGÉNIEUR PROCESS (H/F)', 'CONSULTANT(E) ANALYSTE SECURITÉ (H/F)']
- Top skills: ['project management', 'documentation', 'compliance', 'process optimization', 'data analysis', 'backend development', 'mechanical design']
- Top tools: ['python', 'sql', 'linux', 'azure', 'docker', 'kubernetes', 'gitlab']
- Context keywords: ['ingenieur', 'engineer', 'projets', 'quality', 'techniques', 'solutions', 'developpement']
- Discriminant signals: ['backend development', 'mechanical design', 'version control', 'veille technologique', 'software testing', 'azure', 'containerization']
- Generic/noisy signals: ['management', 'analysis', 'reporting', 'communication', 'kpi', 'sql', 'excel']
- Representative offers:
  - `242530` INGÉNIEUR CONCEPTION MÉCANIQUE (H/F) (FORTIL GROUP, BELGIQUE)
  - `238223` Ingénieur Design (H/F) (EJ PICARDIE, ALLEMAGNE)
  - `236333` Ingénieur EHS & Ingénieur Général CAPEX (Industrie Pharmaceutique) (H/F) (AMARIS FRANCE SAS, BELGIQUE)

### legal
- Volume: `12`
- Top titles: ['Junior Legal Counsel (H/F)', 'COMPLIANCE ANALYST M/F (H/F)', 'VIE – JURISTE H/F (H/F)', 'Junior Legal Officer (H/F)', 'Associate Legal Advisor- VIE (H/F)']
- Top skills: ['compliance', 'legal analysis', 'contract management', 'business intelligence', 'financial analysis', 'regulatory compliance analysis', 'compliance process improvement']
- Top tools: ['sap', 'powerpoint']
- Context keywords: ['compliance', 'legal', 'contrats', 'contract', 'clients', 'votre', 'international']
- Discriminant signals: ['legal analysis']
- Generic/noisy signals: ['analysis', 'management', 'reporting', 'communication', 'kpi']
- Representative offers:
  - `238267` Junior Legal Counsel (H/F) (ARCELORMITTAL FRANCE, LUXEMBOURG)
  - `242342` V.I.E – Juriste Data Privacy & Contrats Commerciaux (H/F) (ICOMERA FRANCE, SUEDE)
  - `242490` Junior Legal Counsel (H/F) (GRAITEC INNOVATION, ESPAGNE)

### admin
- Volume: `28`
- Top titles: ['Technology training support (H/F)', 'PRODUCT OWNER E-COMMERCE (H/F)', 'Administrateur informatique adjoint (H/F)', 'Spécialiste Support Manufacturing & Conformité GMP (H/F)', 'CONSULTANT(E) (M/F) (H/F) - San Francisco, CA']
- Top skills: ['project management', 'planisware solution deployment', 'client process understanding', 'project and portfolio management', 'educational content creation', 'compliance', 'planisware application support']
- Top tools: ['crm', 'aws', 'azure', 'sql', 'jira', 'sap', 'excel']
- Context keywords: ['planisware', 'office', 'clients', 'solutions', 'client', 'product', 'project']
- Discriminant signals: ['planisware solution deployment', 'client process understanding', 'project and portfolio management', 'educational content creation', 'planisware application support', 'user certification database management', 'blasting operational process mapping']
- Generic/noisy signals: ['management', 'communication', 'analysis', 'sql', 'excel', 'reporting']
- Representative offers:
  - `242435` Gestionnaire/administrateur(trice) de contrats F/H (H/F) (ORANO MINING, CANADA)
  - `236352` Spécialiste Support Manufacturing & Conformité GMP (H/F) (AMARIS FRANCE SAS, BELGIQUE)
  - `238371` VIE Functional Excellence Support (H/F) (VALEO COMFORT AND DRIVING ASSISTANCE, ALLEMAGNE)

### other
- Volume: `12`
- Top titles: ['VIE - Strategy Consultant (H/F)', 'PRODUCT OWNER JUNIOR (H/F)', 'Product Owner (H/F)', 'OT Security Consultant (H/F)', 'Responsable Qualité – Spécialiste ISO 27001 (H/F)']
- Top skills: ['compliance', 'project management', 'qualitative and quantitative analysis', 'research plan design', 'client engagement management', 'presentation materials development', 'strategic recommendations frameworks']
- Top tools: []
- Context keywords: ['product', 'service', 'cooperation', 'client', 'etre', 'charge', 'affaires']
- Discriminant signals: ['qualitative and quantitative analysis', 'research plan design', 'client engagement management', 'presentation materials development', 'strategic recommendations frameworks']
- Generic/noisy signals: ['management', 'communication', 'analysis', 'reporting']
- Representative offers:
  - `238369` Responsable Qualité – Spécialiste ISO 27001 (H/F) (ASF ACT DIGITAL, CANADA)
  - `242398` VIE - Strategy Consultant (H/F) (SIA PARTNERS, ETATS-UNIS)
  - `242399` VIE - Strategy Consultant (H/F) (SIA PARTNERS, ETATS-UNIS)

## Recommendations V1

- Keep the current V0 clusters out of runtime until generic cross-domain analytics vocabulary is better contextualized.
- Introduce domain-context rules before adding new clusters: SQL, Excel, KPI, reporting and analysis should never be strong standalone anchors.
- Prioritize non-data cluster discovery from strongly represented domains first: finance, sales, supply, engineering, operations and HR if confirmed by corpus volume.
- Use representative title+tooling+skill triples to define future clusters instead of title-only labels.
- Finance Ops appears naturally enough to study as a future V1 cluster family, but not implement yet.
- HR Operations appears as a better framing than generic BI for HR dashboard/reporting roles.
- Backend Automation can help separate engineering automation from data-centric pipeline logic.

## Data-Centric Bias Risks

- Cross-domain generic analytics signals can over-route offers toward data/BI interpretations.
- A data-heavy seed set would under-represent finance, HR, legal and admin nuances even if the DB contains them.
- If future calibration relies too much on SQL/Power BI/reporting frequency, BI will absorb finance control, HR digital, supply analytics and sales operations roles.
- Lower-volume domains like legal/admin may be overshadowed unless calibrated with domain-specific title and context anchors.
- SQL is widespread enough in the corpus that it must be treated as contextual, not domain-defining.
