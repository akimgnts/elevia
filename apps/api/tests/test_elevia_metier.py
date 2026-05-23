from api.utils.elevia_metier import infer_elevia_metier


def test_infers_data_engineering_from_etl_pipeline_api_and_postgresql():
    result = infer_elevia_metier(
        {
            "title": "Data Engineer",
            "skills": ["ETL", "API", "PostgreSQL", "Python", "data pipeline"],
            "tools": ["Airflow", "dbt", "PostgreSQL"],
            "projects": [
                "Built ETL pipelines from APIs into PostgreSQL with Airflow orchestration"
            ],
            "experiences": [
                "Designed ingestion workflows and backend data pipelines for analytics teams"
            ],
        }
    )

    assert result["primary_cluster"] == "DATA_ENGINEERING"
    assert result["confidence"] >= 0.75
    assert "etl" in result["strong_matches"]["DATA_ENGINEERING"]
    assert "postgresql" in result["tools_matched"]["DATA_ENGINEERING"]
    assert result["project_patterns_matched"]["DATA_ENGINEERING"]


def test_infers_bi_analytics_from_power_bi_dashboards_and_kpis():
    result = infer_elevia_metier(
        {
            "title": "BI Analyst",
            "skills": ["dashboarding", "KPI", "reporting", "business intelligence"],
            "tools": ["Power BI", "SQL", "Excel"],
            "projects": [
                "Created executive dashboards and KPI monitoring in Power BI for weekly reporting"
            ],
            "experiences": [
                "Produced BI reports, dashboards and self-serve analytics for business stakeholders"
            ],
        }
    )

    assert result["primary_cluster"] == "BI_ANALYTICS"
    assert result["confidence"] >= 0.75
    assert "power bi" in result["tools_matched"]["BI_ANALYTICS"]
    assert "kpi" in result["strong_matches"]["BI_ANALYTICS"]


def test_infers_product_analytics_from_cohort_and_experimentation_signals():
    result = infer_elevia_metier(
        {
            "title": "Product Analyst",
            "skills": ["product analytics", "cohort analysis", "a/b testing", "experimentation"],
            "tools": ["Amplitude", "Mixpanel", "SQL"],
            "projects": [
                "Ran experimentation roadmap with cohort analysis and product funnel measurement"
            ],
            "experiences": [
                "Partnered with product managers to analyze feature adoption and retention"
            ],
        }
    )

    assert result["primary_cluster"] == "PRODUCT_ANALYTICS"
    assert result["confidence"] >= 0.75
    assert "cohort analysis" in result["strong_matches"]["PRODUCT_ANALYTICS"]
    assert "amplitude" in result["tools_matched"]["PRODUCT_ANALYTICS"]


def test_generic_signals_only_do_not_create_strong_cluster():
    result = infer_elevia_metier(
        {
            "title": "Business Support",
            "skills": ["communication", "reporting", "analyse"],
            "tools": ["Excel", "PowerPoint"],
            "projects": ["Supported cross-functional communication and reporting"],
            "experiences": ["Produced recurring analysis and coordination updates"],
        }
    )

    assert result["primary_cluster"] is None
    assert result["confidence"] == 0.0
    assert result["candidate_clusters"] == []


def test_weak_signals_alone_are_not_enough_for_cluster_assignment():
    result = infer_elevia_metier(
        {
            "title": "Analyst",
            "skills": ["sql", "excel", "analysis"],
            "tools": ["SQL", "Excel"],
            "projects": ["Worked on ad hoc reporting and data requests"],
            "experiences": ["Supported teams with analysis"],
        }
    )

    assert result["primary_cluster"] is None
    assert result["confidence"] == 0.0
    assert result["weak_matches"]["BI_ANALYTICS"]
    assert result["strong_matches"]["BI_ANALYTICS"] == []


def test_negative_signals_prevent_wrong_bi_assignment_for_product_profile():
    result = infer_elevia_metier(
        {
            "title": "Product Analyst",
            "skills": ["dashboard", "KPI", "cohort analysis", "experimentation"],
            "tools": ["Power BI", "Amplitude"],
            "projects": [
                "Measured feature adoption, retention and experimentation outcomes for product squads"
            ],
            "experiences": [
                "Worked closely with product managers on activation and funnel analysis"
            ],
        }
    )

    assert result["primary_cluster"] == "PRODUCT_ANALYTICS"
    assert result["candidate_clusters"][0]["cluster"] == "PRODUCT_ANALYTICS"
    assert result["candidate_clusters"][0]["score"] > result["candidate_clusters"][1]["score"]


def test_infers_finance_control_from_controller_budgeting_and_sap():
    result = infer_elevia_metier(
        {
            "title": "Finance Controller",
            "skills": [
                "financial analysis",
                "financial reporting",
                "budgeting",
                "accounting",
                "controlling",
            ],
            "tools": ["SAP", "Excel"],
            "projects": [
                "Prepared budgeting cycles and financial reporting packs in SAP for management control"
            ],
            "experiences": [
                "Led controlling routines, variance analysis and monthly accounting close"
            ],
        }
    )

    assert result["primary_cluster"] == "FINANCE_CONTROL"
    assert result["confidence"] >= 0.75
    assert "financial analysis" in result["strong_matches"]["FINANCE_CONTROL"]
    assert "sap" in result["tools_matched"]["FINANCE_CONTROL"]


def test_bi_reporting_and_excel_do_not_trigger_finance_control():
    result = infer_elevia_metier(
        {
            "title": "BI Analyst",
            "skills": ["dashboard", "reporting", "analysis"],
            "tools": ["Power BI", "Excel", "SQL"],
            "projects": [
                "Built KPI dashboards and executive reporting in Power BI for sales leadership"
            ],
            "experiences": [
                "Delivered self-service analytics and dashboard governance for stakeholders"
            ],
        }
    )

    assert result["primary_cluster"] == "BI_ANALYTICS"
    assert result["strong_matches"]["FINANCE_CONTROL"] == []
    assert result["weak_matches"]["FINANCE_CONTROL"]


def test_finance_weak_signals_alone_are_not_enough_for_finance_control():
    result = infer_elevia_metier(
        {
            "title": "Business Analyst",
            "skills": ["excel", "reporting", "analysis"],
            "tools": ["Excel"],
            "projects": ["Created weekly reporting packs for managers"],
            "experiences": ["Supported managers with analysis and reporting"],
        }
    )

    assert result["primary_cluster"] is None
    assert result["strong_matches"]["FINANCE_CONTROL"] == []
    assert result["weak_matches"]["FINANCE_CONTROL"]


def test_finance_and_bi_overlap_stays_stable_and_exposes_ambiguity():
    result = infer_elevia_metier(
        {
            "title": "Business Controller BI",
            "skills": [
                "financial analysis",
                "financial reporting",
                "dashboard",
                "business intelligence",
                "budgeting",
            ],
            "tools": ["SAP", "Power BI", "Excel"],
            "projects": [
                "Built finance dashboards in Power BI and delivered budgeting and management control reviews"
            ],
            "experiences": [
                "Owned monthly financial reporting and KPI visibility for business stakeholders"
            ],
        }
    )

    assert result["primary_cluster"] == "FINANCE_CONTROL"
    assert [row["cluster"] for row in result["candidate_clusters"][:2]] == [
        "FINANCE_CONTROL",
        "BI_ANALYTICS",
    ]
    assert result["candidate_clusters"][0]["score"] > result["candidate_clusters"][1]["score"]


def test_infers_sales_business_development_from_crm_salesforce_and_prospecting():
    result = infer_elevia_metier(
        {
            "title": "Business Developer",
            "skills": [
                "business development",
                "b2b sales",
                "prospecting",
                "account management",
            ],
            "tools": ["Salesforce", "HubSpot", "CRM"],
            "projects": [
                "Built B2B prospecting playbooks and managed CRM pipeline follow-up for account growth"
            ],
            "experiences": [
                "Owned sales development and account management for export clients"
            ],
        }
    )

    assert result["primary_cluster"] == "SALES_BUSINESS_DEVELOPMENT"
    assert result["confidence"] >= 0.75
    assert "business development" in result["strong_matches"]["SALES_BUSINESS_DEVELOPMENT"]
    assert "salesforce" in result["tools_matched"]["SALES_BUSINESS_DEVELOPMENT"]


def test_infers_supply_chain_procurement_from_procurement_logistics_and_supplier_management():
    result = infer_elevia_metier(
        {
            "title": "Procurement Specialist",
            "skills": [
                "supply chain",
                "procurement",
                "supplier management",
                "inventory",
            ],
            "tools": ["SAP Supply", "Excel"],
            "projects": [
                "Led procurement planning, supplier management and inventory coordination in SAP supply flows"
            ],
            "experiences": [
                "Managed purchasing operations, logistics follow-up and replenishment planning"
            ],
        }
    )

    assert result["primary_cluster"] == "SUPPLY_CHAIN_PROCUREMENT"
    assert result["confidence"] >= 0.75
    assert "procurement" in result["strong_matches"]["SUPPLY_CHAIN_PROCUREMENT"]


def test_infers_operations_project_pmo_from_governance_and_process_improvement():
    result = infer_elevia_metier(
        {
            "title": "PMO Coordinator",
            "skills": [
                "project management",
                "pmo",
                "governance",
                "process improvement",
            ],
            "tools": ["Jira", "ServiceNow", "Excel"],
            "projects": [
                "Coordinated PMO governance, project reporting and operational process improvement workflows"
            ],
            "experiences": [
                "Led operational coordination across project streams with Jira and ServiceNow"
            ],
        }
    )

    assert result["primary_cluster"] == "OPERATIONS_PROJECT_PMO"
    assert result["confidence"] >= 0.75
    assert "pmo" in result["strong_matches"]["OPERATIONS_PROJECT_PMO"]
    assert "jira" in result["tools_matched"]["OPERATIONS_PROJECT_PMO"]


def test_infers_engineering_build_run_from_backend_devops_and_containerization():
    result = infer_elevia_metier(
        {
            "title": "Backend Engineer",
            "skills": [
                "backend development",
                "software testing",
                "containerization",
                "devops",
            ],
            "tools": ["Docker", "Kubernetes", "Azure"],
            "projects": [
                "Built backend services, automated deployment pipelines and containerized workloads on Kubernetes"
            ],
            "experiences": [
                "Owned build and run reliability with software testing and cloud operations"
            ],
        }
    )

    assert result["primary_cluster"] == "ENGINEERING_BUILD_RUN"
    assert result["confidence"] >= 0.75
    assert "backend development" in result["strong_matches"]["ENGINEERING_BUILD_RUN"]
    assert "docker" in result["tools_matched"]["ENGINEERING_BUILD_RUN"]


def test_infers_hr_talent_operations_from_recruitment_onboarding_and_hr_systems():
    result = infer_elevia_metier(
        {
            "title": "Talent Acquisition Specialist",
            "skills": [
                "recruitment",
                "candidate sourcing",
                "talent management",
                "onboarding",
            ],
            "tools": ["SuccessFactors", "CRM"],
            "projects": [
                "Managed recruitment funnels, candidate sourcing and onboarding workflows in HR systems"
            ],
            "experiences": [
                "Supported workforce planning and talent operations across multiple hiring teams"
            ],
        }
    )

    assert result["primary_cluster"] == "HR_TALENT_OPERATIONS"
    assert result["confidence"] >= 0.75
    assert "recruitment" in result["strong_matches"]["HR_TALENT_OPERATIONS"]
    assert "successfactors" in result["tools_matched"]["HR_TALENT_OPERATIONS"]


def test_generic_management_reporting_and_excel_do_not_create_sales_cluster():
    result = infer_elevia_metier(
        {
            "title": "Coordinator",
            "skills": ["reporting", "communication", "management"],
            "tools": ["Excel"],
            "projects": ["Handled recurring reporting and coordination updates"],
            "experiences": ["Supported managers with communication and planning"],
        }
    )

    assert result["primary_cluster"] is None
    assert result["strong_matches"]["SALES_BUSINESS_DEVELOPMENT"] == []
    assert result["weak_matches"]["SALES_BUSINESS_DEVELOPMENT"]


def test_supply_and_operations_overlap_stays_stable_and_favors_supply_cluster():
    result = infer_elevia_metier(
        {
            "title": "Supply Project Coordinator",
            "skills": [
                "supply chain",
                "procurement",
                "project management",
                "supplier management",
            ],
            "tools": ["SAP Supply", "Jira", "Excel"],
            "projects": [
                "Coordinated supply chain projects, procurement milestones and supplier governance"
            ],
            "experiences": [
                "Managed logistics follow-up and cross-functional operational coordination"
            ],
        }
    )

    assert result["primary_cluster"] == "SUPPLY_CHAIN_PROCUREMENT"
    assert [row["cluster"] for row in result["candidate_clusters"][:2]] == [
        "SUPPLY_CHAIN_PROCUREMENT",
        "OPERATIONS_PROJECT_PMO",
    ]


def test_engineering_and_data_overlap_stays_stable_and_favors_engineering_when_data_signals_are_weak():
    result = infer_elevia_metier(
        {
            "title": "Backend Platform Engineer",
            "skills": [
                "backend development",
                "devops",
                "containerization",
                "api",
            ],
            "tools": ["Docker", "Kubernetes", "Azure", "Python"],
            "projects": [
                "Built backend APIs and containerized platform services with deployment automation"
            ],
            "experiences": [
                "Owned build and run reliability for cloud services used by internal data teams"
            ],
        }
    )

    assert result["primary_cluster"] == "ENGINEERING_BUILD_RUN"
    assert result["candidate_clusters"][0]["score"] > result["candidate_clusters"][1]["score"]
    assert result["candidate_clusters"][1]["cluster"] == "DATA_ENGINEERING"


def test_hr_and_operations_overlap_stays_stable_and_favors_hr_cluster():
    result = infer_elevia_metier(
        {
            "title": "HR Operations Coordinator",
            "skills": [
                "recruitment",
                "candidate sourcing",
                "onboarding",
                "project management",
            ],
            "tools": ["SuccessFactors", "Jira", "Excel"],
            "projects": [
                "Coordinated onboarding projects, recruitment workflows and HR systems governance"
            ],
            "experiences": [
                "Supported talent operations and workforce planning across operational teams"
            ],
        }
    )

    assert result["primary_cluster"] == "HR_TALENT_OPERATIONS"
    assert [row["cluster"] for row in result["candidate_clusters"][:2]] == [
        "HR_TALENT_OPERATIONS",
        "OPERATIONS_PROJECT_PMO",
    ]
