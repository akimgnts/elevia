#!/usr/bin/env python3
"""
eval_role_resolver_terrain.py — FR/EN terrain validation sprint for Role Resolver.

Builds a 40-case annotated evaluation dataset (real offers + synthetic profiles),
runs the resolver on each case, computes metrics, and produces a reviewable CSV + JSONL.

Usage:
    cd apps/api
    python scripts/eval_role_resolver_terrain.py

Outputs:
    data/eval/role_resolver_eval_cases.jsonl    — annotated eval dataset
    data/eval/role_resolver_eval_results.csv    — reviewable results table
    data/eval/role_resolver_eval_metrics.json   — computed metrics
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent
API_SRC = REPO_ROOT / "apps" / "api" / "src"
sys.path.insert(0, str(API_SRC))

from compass.roles.role_resolver import RoleResolver  # noqa: E402

EVAL_DIR = REPO_ROOT / "apps" / "api" / "data" / "eval"
OFFERS_DB = REPO_ROOT / "apps" / "api" / "data" / "db" / "offers.db"
ONET_DB = REPO_ROOT / "apps" / "api" / "data" / "db" / "onet.db"

# ── Offer descriptions fetched from DB ───────────────────────────────────────

def _fetch_offer(offer_id: str) -> dict:
    if not OFFERS_DB.exists():
        return {"title": "", "description": ""}
    conn = sqlite3.connect(str(OFFERS_DB))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT title, description FROM fact_offers WHERE id=?", (offer_id,)
    ).fetchone()
    conn.close()
    if row:
        return {"title": row["title"], "description": row["description"] or ""}
    return {"title": "", "description": ""}


# ── Static eval case definitions ─────────────────────────────────────────────
# source_type: "real_db" = from fact_offers DB, "synthetic" = hand-crafted fixture
# human_verdict_expected: "good" | "acceptable" | "wrong" | "unclear"
#   good       = resolver should clearly nail it
#   acceptable = resolver might get it right with some imprecision
#   wrong      = known hard/impossible case (test for graceful failure)
#   unclear    = genuinely ambiguous even for a human

STATIC_CASES: list[dict] = [
    # ══════════════════════════════════════════════════════════════
    # REAL OFFERS from fact_offers DB (20 cases)
    # ══════════════════════════════════════════════════════════════

    # — EN title, EN description —
    {
        "id": "OFFER-REAL-01",
        "type": "offer",
        "language": "en",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-237359",
        "canonical_skills": ["Data Analysis", "SQL", "Python", "Business Intelligence"],
        "expected_role_family": "data_analytics",
        "expected_occupation_hint": "Data Scientists / Operations Research Analysts",
        "human_verdict_expected": "good",
        "notes": "Clear EN title 'Data Analyst Operations', rich EN description. Baseline case.",
    },
    {
        "id": "OFFER-REAL-02",
        "type": "offer",
        "language": "en",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-235427",
        "canonical_skills": ["Financial Analysis", "Financial Modeling", "M&A"],
        "expected_role_family": "finance",
        "expected_occupation_hint": "Financial Quantitative Analysts / Management Analysts",
        "human_verdict_expected": "acceptable",
        "notes": "'M&A Analyst' is a niche title. O*NET has 'Financial Quantitative Analysts' covering M&A. Title is EN.",
    },
    {
        "id": "OFFER-REAL-03",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-236044",
        "canonical_skills": ["AI", "Consulting", "Product Management"],
        "expected_role_family": "consulting",
        "expected_occupation_hint": "Management Consultants / Computer Occupations",
        "human_verdict_expected": "unclear",
        "notes": "'AI Deployment Strategist' is a novel title not in O*NET. FR description. Tests graceful fallback.",
    },
    {
        "id": "OFFER-REAL-04",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-236045",
        "canonical_skills": ["Sales", "CRM", "B2B Sales"],
        "expected_role_family": "sales",
        "expected_occupation_hint": "Sales Representatives / Sales Managers",
        "human_verdict_expected": "good",
        "notes": "EN title 'Sales Executive' in FR-context offer. Title is canonical for O*NET.",
    },
    {
        "id": "OFFER-REAL-05",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-236542",
        "canonical_skills": ["Project Management", "Operations Management", "CRM"],
        "expected_role_family": "project_management",
        "expected_occupation_hint": "Project Management Specialists",
        "human_verdict_expected": "good",
        "notes": "Title 'Project Manager / School Launcher' — compound. 'Project Manager' half should anchor resolution.",
    },
    {
        "id": "OFFER-REAL-06",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-237154",
        "canonical_skills": ["Financial Reporting", "Financial Analysis", "SAP", "Excel"],
        "expected_role_family": "finance",
        "expected_occupation_hint": "Budget Analysts / Financial Analysts",
        "human_verdict_expected": "good",
        "notes": "FR title 'Finance / Contrôle de gestion'. Tests FR title with slash compound.",
    },
    {
        "id": "OFFER-REAL-07",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-237189",
        "canonical_skills": ["Engineering", "Project Management"],
        "expected_role_family": "engineering",
        "expected_occupation_hint": "Environmental Engineers / Civil Engineers",
        "human_verdict_expected": "wrong",
        "notes": "'Ingénieur station d\u2019\u00e9puration' is ultra-niche. FR → EN translation will fail. Tests worst-case niche.",
    },
    {
        "id": "OFFER-REAL-08",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-237241",
        "canonical_skills": ["Business Development", "Sales", "Marketing"],
        "expected_role_family": "sales",
        "expected_occupation_hint": "Sales Representatives / Business Development Managers",
        "human_verdict_expected": "acceptable",
        "notes": "TYPO in title: 'Business Developper' (missing 'e'). Tests typo resilience in FR context.",
    },
    {
        "id": "OFFER-REAL-09",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-237362",
        "canonical_skills": ["Automation", "Engineering", "Process Improvement"],
        "expected_role_family": "engineering",
        "expected_occupation_hint": "Industrial Engineers / Electrical Engineers",
        "human_verdict_expected": "acceptable",
        "notes": "'Ing\u00e9nieur Automatisation' — FR engineering. Tests FR→EN translation for specific engineering subdomain.",
    },
    {
        "id": "OFFER-REAL-10",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-233040",
        "canonical_skills": ["Procurement", "Supply Chain Management", "SAP", "Negotiation"],
        "expected_role_family": "supply_chain",
        "expected_occupation_hint": "Purchasing Agents / Logisticians",
        "human_verdict_expected": "acceptable",
        "notes": "UPPERCASE title 'INGENIEUR ACHETEUR'. Tests casing normalisation. Supply chain / procurement niche.",
    },

    # — VIE compound titles (vague FR patterns) —
    {
        "id": "OFFER-REAL-11",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-AZ-0001",
        "canonical_skills": ["Financial Analysis", "Accounting", "Reporting"],
        "expected_role_family": "finance",
        "expected_occupation_hint": "Financial Analysts",
        "human_verdict_expected": "acceptable",
        "notes": "VIE compound title 'VIE - Finance - LVMH Allemagne'. Tests extract_title() on compound VIE format.",
    },
    {
        "id": "OFFER-REAL-12",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-AZ-0002",
        "canonical_skills": ["DevOps", "Software Engineering", "Git"],
        "expected_role_family": "software_engineering",
        "expected_occupation_hint": "Software Developers / DevOps Engineers",
        "human_verdict_expected": "acceptable",
        "notes": "VIE 'Informatique' — FR generic word for IT. Tests whether 'informatique' maps to software_engineering.",
    },
    {
        "id": "OFFER-REAL-13",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-AZ-0003",
        "canonical_skills": ["Engineering", "R&D", "Simulation"],
        "expected_role_family": "engineering",
        "expected_occupation_hint": "Industrial Engineers / Mechanical Engineers",
        "human_verdict_expected": "acceptable",
        "notes": "VIE 'Ing\u00e9nierie' — generic French engineering label. Tests broad engineering coverage.",
    },
    {
        "id": "OFFER-REAL-14",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-AZ-0004",
        "canonical_skills": ["Sales", "Business Development", "Client Relations"],
        "expected_role_family": "sales",
        "expected_occupation_hint": "Sales Representatives",
        "human_verdict_expected": "acceptable",
        "notes": "VIE 'Commerce' — FR word for commerce/trade. Tests whether 'commerce' maps to sales.",
    },
    {
        "id": "OFFER-REAL-15",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-AZ-0005",
        "canonical_skills": ["Supply Chain Management", "Logistics", "Inventory Management"],
        "expected_role_family": "supply_chain",
        "expected_occupation_hint": "Logisticians / Supply Chain Managers",
        "human_verdict_expected": "good",
        "notes": "VIE 'Supply Chain' — English term used in French context. Should resolve well.",
    },
    {
        "id": "OFFER-REAL-16",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-AZ-0006",
        "canonical_skills": ["Engineering", "Manufacturing", "Process Engineering"],
        "expected_role_family": "engineering",
        "expected_occupation_hint": "Industrial Engineers",
        "human_verdict_expected": "acceptable",
        "notes": "VIE 'Ing\u00e9nierie' Michelin — same pattern as REAL-13, different company/country.",
    },
    {
        "id": "OFFER-REAL-17",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-AZ-0008",
        "canonical_skills": ["Legal", "Compliance", "Contract Law"],
        "expected_role_family": "legal",
        "expected_occupation_hint": "Lawyers / Paralegals",
        "human_verdict_expected": "good",
        "notes": "VIE 'Juridique' — FR for legal. Tests legal domain coverage.",
    },
    {
        "id": "OFFER-REAL-18",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-AZ-0009",
        "canonical_skills": ["Supply Chain Management", "SAP", "Logistics"],
        "expected_role_family": "supply_chain",
        "expected_occupation_hint": "Logisticians / Supply Chain Analysts",
        "human_verdict_expected": "good",
        "notes": "VIE 'Supply Chain' Engie. Duplicate of REAL-15 pattern — checks consistency.",
    },
    {
        "id": "OFFER-REAL-19",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-AZ-0010",
        "canonical_skills": ["Human Resources", "Recruitment", "HRIS"],
        "expected_role_family": "hr",
        "expected_occupation_hint": "Human Resources Specialists",
        "human_verdict_expected": "good",
        "notes": "VIE 'RH' — FR acronym for HR. Tests acronym handling in title normalization.",
    },
    {
        "id": "OFFER-REAL-20",
        "type": "offer",
        "language": "fr",
        "source_type": "real_db",
        "source_path": "fact_offers:BF-230224",
        "canonical_skills": ["Agriculture", "Farm Management"],
        "expected_role_family": "other",
        "expected_occupation_hint": "None - no O*NET match expected",
        "human_verdict_expected": "wrong",
        "notes": "'ADJOINT CHEF DE FERME' (farm deputy). Zero O*NET coverage. Tests graceful no-match.",
    },

    # ══════════════════════════════════════════════════════════════
    # SYNTHETIC PROFILES (20 cases) — clearly labelled as synthetic
    # ══════════════════════════════════════════════════════════════

    # — EN clean profiles with explicit title (5) —
    {
        "id": "PROFILE-EN-01",
        "type": "profile",
        "language": "en",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Senior Data Scientist",
        "cv_text": (
            "Jane Smith\nSenior Data Scientist\n"
            "5 years experience in machine learning, statistical modeling, Python, "
            "R, SQL, TensorFlow, scikit-learn, data pipelines, A/B testing, "
            "NLP. PhD in Statistics. Led data science team at Accenture."
        ),
        "canonical_skills": ["Machine Learning", "Python", "SQL", "Data Analysis", "Statistical Programming"],
        "expected_role_family": "data_analytics",
        "expected_occupation_hint": "Data Scientists",
        "human_verdict_expected": "good",
        "notes": "Clean EN title + rich skills. Easiest case. Validates baseline EN resolution.",
    },
    {
        "id": "PROFILE-EN-02",
        "type": "profile",
        "language": "en",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Software Engineer",
        "cv_text": (
            "Tom Brown\nSoftware Engineer\n"
            "Backend development with Python, Java, SQL. REST APIs, Docker, "
            "Kubernetes, Git, CI/CD, AWS. Microservices architecture. "
            "4 years at fintech startup, 2 years at consulting firm."
        ),
        "canonical_skills": ["Software Engineering", "Python", "Git", "Docker", "REST API"],
        "expected_role_family": "software_engineering",
        "expected_occupation_hint": "Software Developers",
        "human_verdict_expected": "good",
        "notes": "Clean EN title + classic dev skills. Validates software_engineering path.",
    },
    {
        "id": "PROFILE-EN-03",
        "type": "profile",
        "language": "en",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Product Manager",
        "cv_text": (
            "Sarah Lee\nProduct Manager\n"
            "Led product roadmap for SaaS B2B platform. Agile/Scrum, Jira, "
            "user research, A/B testing, stakeholder management, KPIs, analytics."
        ),
        "canonical_skills": ["Product Management", "Agile", "Scrum", "Analytics"],
        "expected_role_family": "product_management",
        "expected_occupation_hint": "Project Management Specialists / Computer Occupations",
        "human_verdict_expected": "good",
        "notes": "Clean EN title. O*NET doesn't have a perfect 'Product Manager' — tests nearest match.",
    },
    {
        "id": "PROFILE-EN-04",
        "type": "profile",
        "language": "en",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Digital Marketing Analyst",
        "cv_text": (
            "Alice Martin\nDigital Marketing Analyst\n"
            "SEO, SEM, Google Analytics, Facebook Ads, email marketing, "
            "content strategy, CRM (HubSpot, Salesforce), A/B testing, "
            "performance reporting, SQL for marketing attribution."
        ),
        "canonical_skills": ["Digital Marketing", "SEO", "Analytics", "CRM", "SQL"],
        "expected_role_family": "marketing",
        "expected_occupation_hint": "Market Research Analysts / Marketing Specialists",
        "human_verdict_expected": "good",
        "notes": "Clean EN title with marketing + analytics mix. Tests marketing family resolution.",
    },
    {
        "id": "PROFILE-EN-05",
        "type": "profile",
        "language": "en",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Financial Analyst",
        "cv_text": (
            "Mark Chen\nFinancial Analyst\n"
            "Financial modeling, DCF analysis, Excel, Bloomberg, SQL, "
            "financial reporting, budget management, variance analysis, "
            "IFRS, audit support. CFA Level 2."
        ),
        "canonical_skills": ["Financial Analysis", "Excel", "Financial Modeling", "Financial Reporting"],
        "expected_role_family": "finance",
        "expected_occupation_hint": "Financial Analysts",
        "human_verdict_expected": "good",
        "notes": "Clean EN title. Well-mapped in O*NET. Validates finance resolution.",
    },

    # — FR clean profiles (5) —
    {
        "id": "PROFILE-FR-01",
        "type": "profile",
        "language": "fr",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Ingénieur Data",
        "cv_text": (
            "Karim Bensaid\nIngénieur Data\n"
            "Développement de pipelines de données, Python, Spark, SQL, "
            "Airflow, GCP, BigQuery, orchestration ETL, architecture data lakehouse."
        ),
        "canonical_skills": ["Data Engineering", "Python", "SQL", "Apache Spark"],
        "expected_role_family": "data_analytics",
        "expected_occupation_hint": "Data Scientists / Computer Occupations",
        "human_verdict_expected": "good",
        "notes": "FR title in _TITLE_PHRASE_MAP: 'ingénieur data' → 'data engineer'. Tests phrase map.",
    },
    {
        "id": "PROFILE-FR-02",
        "type": "profile",
        "language": "fr",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Développeur Web",
        "cv_text": (
            "Louis Petit\nDéveloppeur Web\n"
            "React, TypeScript, Node.js, REST APIs, PostgreSQL, Docker, Git. "
            "3 ans en agence web, 1 an startup SaaS."
        ),
        "canonical_skills": ["Web Development", "JavaScript", "REST API", "Git", "Docker"],
        "expected_role_family": "software_engineering",
        "expected_occupation_hint": "Web Developers / Software Developers",
        "human_verdict_expected": "good",
        "notes": "FR title in _TITLE_PHRASE_MAP: 'développeur web' → 'web developer'. Tests FR→EN phrase map.",
    },
    {
        "id": "PROFILE-FR-03",
        "type": "profile",
        "language": "fr",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Chef de Projet Digital",
        "cv_text": (
            "Emilie Rousseau\nChef de Projet Digital\n"
            "Pilotage de projets web et digital, coordination des parties prenantes, "
            "gestion des plannings, budget, CRM, reporting KPI, méthode Agile."
        ),
        "canonical_skills": ["Project Management", "Digital Marketing", "Agile", "CRM"],
        "expected_role_family": "project_management",
        "expected_occupation_hint": "Project Management Specialists",
        "human_verdict_expected": "good",
        "notes": "FR title in _TITLE_PHRASE_MAP: 'chef de projet digital' → 'digital project manager'. Best-case FR.",
    },
    {
        "id": "PROFILE-FR-04",
        "type": "profile",
        "language": "fr",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Responsable Marketing Digital",
        "cv_text": (
            "Nadia Moreau\nResponsable Marketing Digital\n"
            "Stratégie digitale, SEO, SEA, social media, email marketing, "
            "analytics web, Google Analytics, HubSpot, management d'équipe."
        ),
        "canonical_skills": ["Digital Marketing", "SEO", "Analytics", "Social Media Marketing", "CRM"],
        "expected_role_family": "marketing",
        "expected_occupation_hint": "Marketing Managers / Market Research Analysts",
        "human_verdict_expected": "acceptable",
        "notes": "'Responsable marketing' in phrase map → 'marketing manager'. 'digital' suffix may or may not be preserved.",
    },
    {
        "id": "PROFILE-FR-05",
        "type": "profile",
        "language": "fr",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Analyste de Données",
        "cv_text": (
            "Fatou Diallo\nAnalyste de Données\n"
            "Analyse de données SQL, Python, Power BI, reporting opérationnel, "
            "visualisation de données, Excel, KPI, bases de données."
        ),
        "canonical_skills": ["Data Analysis", "SQL", "Python", "Business Intelligence"],
        "expected_role_family": "data_analytics",
        "expected_occupation_hint": "Data Scientists / Operations Research Analysts",
        "human_verdict_expected": "good",
        "notes": "'analyste de données' in _TITLE_PHRASE_MAP → 'data analyst'. Key FR data analyst test.",
    },

    # — Bilingual profiles (3) —
    {
        "id": "PROFILE-BI-01",
        "type": "profile",
        "language": "bilingual",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Data Analyst / Analyste Données",
        "cv_text": (
            "Mia Gonzalez\nData Analyst / Analyste Données\n"
            "SQL, Python, Power BI, Tableau, data visualisation, reporting, "
            "analyse de données, ETL, Excel. 3 ans exp."
        ),
        "canonical_skills": ["Data Analysis", "SQL", "Business Intelligence", "Python"],
        "expected_role_family": "data_analytics",
        "expected_occupation_hint": "Data Scientists / Operations Research Analysts",
        "human_verdict_expected": "good",
        "notes": "Bilingual title: EN part 'Data Analyst' should be picked up by _score_line. Tests bilingual resilience.",
    },
    {
        "id": "PROFILE-BI-02",
        "type": "profile",
        "language": "bilingual",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Software Engineer / Ingénieur Logiciel",
        "cv_text": (
            "Pierre Chen\nSoftware Engineer / Ingénieur Logiciel\n"
            "Python, Java, C++, microservices, Docker, CI/CD, REST APIs, Git. "
            "Logiciels embarqués, développement backend, architecture système."
        ),
        "canonical_skills": ["Software Engineering", "Python", "Git", "Docker"],
        "expected_role_family": "software_engineering",
        "expected_occupation_hint": "Software Developers / Software Engineers",
        "human_verdict_expected": "good",
        "notes": "Bilingual title with phrase map match on FR side: 'ingénieur logiciel' → 'software engineer'.",
    },
    {
        "id": "PROFILE-BI-03",
        "type": "profile",
        "language": "bilingual",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Business Developer / Chargé de développement commercial",
        "cv_text": (
            "Andrea Ferroni\nBusiness Developer / Chargé de développement commercial\n"
            "Prospection B2B, pipeline commercial, négociation, CRM Salesforce, "
            "KPIs vente, partenariats, développement marché EMEA."
        ),
        "canonical_skills": ["Business Development", "Sales", "CRM", "Negotiation"],
        "expected_role_family": "sales",
        "expected_occupation_hint": "Sales Representatives / Business Development Managers",
        "human_verdict_expected": "acceptable",
        "notes": "Bilingual compound title. 'Business Developer' not standard O*NET — maps to sales via keyword fallback.",
    },

    # — Noisy / degraded profiles (3) —
    {
        "id": "PROFILE-NOISY-01",
        "type": "profile",
        "language": "fr",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "",
        "cv_text": (
            "Python SQL Machine Learning Power BI Docker Kubernetes\n"
            "Spark Airflow BigQuery TensorFlow Pandas Git CI/CD\n"
            "Analyse de données visualisation reporting ETL\n"
            "3 ans expérience data ingénierie"
        ),
        "canonical_skills": ["Python", "SQL", "Machine Learning", "Data Engineering", "Business Intelligence"],
        "expected_role_family": "data_analytics",
        "expected_occupation_hint": "Data Scientists",
        "human_verdict_expected": "wrong",
        "notes": "No title at all — only skills dump. Tests extract_title() fallback on titleless CV.",
    },
    {
        "id": "PROFILE-NOISY-02",
        "type": "profile",
        "language": "fr",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Candidature spontanée - Profil polyvalent",
        "cv_text": (
            "Candidature spontanée - Profil polyvalent\n"
            "À l'attention du service RH\n"
            "Bonjour,\n"
            "Je me permets de vous contacter pour une candidature spontanée. "
            "Je dispose de compétences en Python, SQL, data analysis, "
            "ainsi qu'une expérience en gestion de projet Agile."
        ),
        "canonical_skills": ["Python", "SQL", "Data Analysis", "Project Management"],
        "expected_role_family": "other",
        "expected_occupation_hint": "None expected — noise title",
        "human_verdict_expected": "wrong",
        "notes": "Cover letter header as title. 'Candidature spontanée' should fail _SKIP_LINE_HINTS check. Tests filter.",
    },
    {
        "id": "PROFILE-NOISY-03",
        "type": "profile",
        "language": "fr",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "EXPÉRIENCE PROFESSIONNELLE",
        "cv_text": (
            "EXPÉRIENCE PROFESSIONNELLE\n"
            "2021-2023 : Analyste Data, BNP Paribas, Paris\n"
            "SQL, Python, Power BI, reporting hebdomadaire, KPI finance.\n"
            "2019-2021 : Contrôleur de gestion junior, KPMG\n"
            "Excel, SAP, analyses financières."
        ),
        "canonical_skills": ["Data Analysis", "SQL", "Python", "Financial Analysis"],
        "expected_role_family": "other",
        "expected_occupation_hint": "Ambiguous — could be data_analytics or finance",
        "human_verdict_expected": "wrong",
        "notes": "Section header as title. Tests whether 'expérience' is correctly ignored by extract_title().",
    },

    # — Strong skills, weak/vague title (2) —
    {
        "id": "PROFILE-SKILLS-01",
        "type": "profile",
        "language": "en",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Consultant",
        "cv_text": (
            "David Kumar\nConsultant\n"
            "Python, scikit-learn, TensorFlow, Machine Learning, Deep Learning, "
            "SQL, Power BI, data pipelines, cloud (AWS, GCP), "
            "statistical modeling, NLP, data visualization."
        ),
        "canonical_skills": ["Machine Learning", "Python", "Data Analysis", "Business Intelligence", "SQL"],
        "expected_role_family": "consulting",
        "expected_occupation_hint": "Management Consultants — but skills suggest data_analytics",
        "human_verdict_expected": "unclear",
        "notes": (
            "Vague title 'Consultant' but strong data skills. Title dominates (0.78 weight). "
            "Tests conflict between title signal (consulting) and skill signal (data_analytics)."
        ),
    },
    {
        "id": "PROFILE-SKILLS-02",
        "type": "profile",
        "language": "en",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Manager",
        "cv_text": (
            "Sophie Bernard\nManager\n"
            "SAP ERP, procurement, inventory management, logistics optimization, "
            "supplier negotiation, WMS, demand planning, S&OP, lean manufacturing."
        ),
        "canonical_skills": ["Supply Chain Management", "SAP", "Logistics", "Procurement", "Negotiation"],
        "expected_role_family": "operations",
        "expected_occupation_hint": "General and Operations Managers — but skills suggest supply_chain",
        "human_verdict_expected": "unclear",
        "notes": (
            "Ultra-vague title 'Manager'. Skills strongly suggest supply_chain. "
            "Tests whether skill signal (0.22) can override vague title."
        ),
    },

    # — Non-linear career (2) —
    {
        "id": "PROFILE-NLIN-01",
        "type": "profile",
        "language": "en",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Project Manager (ex-Software Developer)",
        "cv_text": (
            "Julien Moreau\nProject Manager (ex-Software Developer)\n"
            "Currently managing digital transformation projects (Agile, Scrum, Jira). "
            "Previously: 4 years Python / Java developer, REST APIs, Git. "
            "PMP certified. Stakeholder management, budget, risk management."
        ),
        "canonical_skills": ["Project Management", "Agile", "Python", "Software Engineering"],
        "expected_role_family": "project_management",
        "expected_occupation_hint": "Project Management Specialists",
        "human_verdict_expected": "acceptable",
        "notes": "Non-linear career with parenthetical qualification in title. Tests title extraction on complex line.",
    },
    {
        "id": "PROFILE-NLIN-02",
        "type": "profile",
        "language": "en",
        "source_type": "synthetic",
        "source_path": None,
        "raw_title": "Senior Consultant (Engineering Background)",
        "cv_text": (
            "Hugo Lefevre\nSenior Consultant (Engineering Background)\n"
            "Previously: mechanical engineer, industrial processes, CAD, SolidWorks. "
            "Now: strategy consulting, operational transformation, lean, six sigma, "
            "client presentations, business development, proposal writing."
        ),
        "canonical_skills": ["Consulting", "Engineering", "Lean Manufacturing", "Business Development"],
        "expected_role_family": "consulting",
        "expected_occupation_hint": "Management Consultants / Industrial Engineers",
        "human_verdict_expected": "unclear",
        "notes": "Mixed background. 'Consultant' in title should dominate. Tests parenthetical noise handling.",
    },
]


# ── Load DB descriptions for real offer cases ─────────────────────────────────

def _build_cases(static: list[dict]) -> list[dict]:
    cases = []
    for c in static:
        case = dict(c)
        if c["source_type"] == "real_db" and c["source_path"]:
            offer_id = c["source_path"].split(":")[-1]
            offer = _fetch_offer(offer_id)
            case["raw_title"] = offer["title"]
            case["cv_text"] = offer["description"]
        elif "cv_text" not in c:
            case["cv_text"] = ""
        cases.append(case)
    return cases


# ── Run resolver on a single case ─────────────────────────────────────────────

def _run_case(resolver: RoleResolver, case: dict) -> dict:
    try:
        if case["type"] == "offer":
            result = resolver.resolve_role_for_offer({
                "title": case.get("raw_title", ""),
                "description": case.get("cv_text", ""),
                "canonical_skills": case.get("canonical_skills", []),
            }, include_inferred_skills=True)
        else:
            result = resolver.resolve_role_for_profile({
                "title": case.get("raw_title", ""),
                "cv_text": case.get("cv_text", ""),
                "canonical_skills": case.get("canonical_skills", []),
            }, include_inferred_skills=True)
    except Exception as exc:
        return {
            "error": str(exc),
            "primary_role_family": None,
            "secondary_role_families": [],
            "candidate_occupations": [],
            "occupation_confidence": 0.0,
            "inferred_skills": [],
            "evidence": {},
        }
    return result


# ── Human verdict logic ───────────────────────────────────────────────────────

def _auto_verdict(case: dict, result: dict) -> str:
    """
    Compute an automated verdict by comparing resolver output to human annotation.
    Returns: 'match' | 'mismatch' | 'no_resolution' | 'partial'
    """
    has_occ = bool(result.get("candidate_occupations"))
    conf = float(result.get("occupation_confidence") or 0.0)
    primary_family = result.get("primary_role_family")
    expected_family = case.get("expected_role_family")

    if not has_occ or conf < 0.45:
        return "no_resolution"

    if primary_family == expected_family:
        return "match"

    # Accept "other" as partial match for wrong/unclear cases
    if case.get("human_verdict_expected") in ("wrong", "unclear"):
        return "partial"

    return "mismatch"


# ── Metric computation ────────────────────────────────────────────────────────

def compute_metrics(items: list[dict]) -> dict:
    total = len(items)
    if total == 0:
        return {}

    resolved = 0
    confidence_sum = 0.0
    added_sum = 0.0
    skills_dist: Counter = Counter()
    family_matches = 0
    family_evaluable = 0
    title_norm_improved = 0
    title_norm_evaluable = 0
    low_conf_but_resolved = 0

    for item in items:
        result = item["resolver_output"]
        case = item["case"]

        has_occ = bool(result.get("candidate_occupations"))
        conf = float(result.get("occupation_confidence") or 0.0)
        inferred = result.get("inferred_skills") or []
        added_count = len(inferred)
        primary_family = result.get("primary_role_family")
        expected_family = case.get("expected_role_family")
        norm_title = (result.get("evidence") or {}).get("normalized_title", "")
        raw_title = case.get("raw_title", "")

        if has_occ:
            resolved += 1
            confidence_sum += conf

        added_sum += added_count
        skills_dist[added_count] += 1

        # Family accuracy — only for cases where expected is not "other"
        if expected_family and expected_family != "other":
            family_evaluable += 1
            if primary_family == expected_family:
                family_matches += 1

        # Title normalization: improved if norm_title differs from raw (lowercased) and is non-empty
        raw_norm = raw_title.lower().strip()
        norm_norm = norm_title.lower().strip()
        if raw_norm:
            title_norm_evaluable += 1
            if norm_norm and norm_norm != raw_norm and len(norm_norm) >= 3:
                title_norm_improved += 1

        # False positive: resolved but confidence < 0.6
        if has_occ and conf < 0.6:
            low_conf_but_resolved += 1

    return {
        "total_cases": total,
        "occupation_resolution_rate": round(resolved / total, 4),
        "avg_confidence": round(confidence_sum / resolved, 4) if resolved else 0.0,
        "role_family_accuracy": round(family_matches / family_evaluable, 4) if family_evaluable else 0.0,
        "title_normalization_rate": round(title_norm_improved / title_norm_evaluable, 4) if title_norm_evaluable else 0.0,
        "inferred_skills_avg": round(added_sum / total, 4),
        "false_positive_rate": round(low_conf_but_resolved / total, 4),
        "skills_added_distribution": dict(sorted(skills_dist.items())),
        "resolved_count": resolved,
        "family_evaluable_count": family_evaluable,
        "family_match_count": family_matches,
    }


# ── Failure mode taxonomy ─────────────────────────────────────────────────────

def classify_failure(case: dict, result: dict) -> str | None:
    verdict = _auto_verdict(case, result)
    if verdict in ("match", "partial"):
        return None
    has_occ = bool(result.get("candidate_occupations"))
    conf = float(result.get("occupation_confidence") or 0.0)
    raw_title = case.get("raw_title", "")
    norm_title = (result.get("evidence") or {}).get("normalized_title", "")
    lang = case.get("language", "en")

    if not raw_title.strip():
        return "no_title"
    if lang == "fr" and norm_title and norm_title == raw_title.lower().strip():
        return "fr_translation_failed"
    if not has_occ:
        return "no_onet_match"
    if has_occ and conf < 0.45:
        return "confidence_too_low"
    if has_occ and conf >= 0.45:
        # resolved but wrong family
        return "wrong_role_family"
    return "other_failure"


# ── Main entry point ──────────────────────────────────────────────────────────

def main() -> int:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    print("⟳  Building evaluation cases...")
    cases = _build_cases(STATIC_CASES)

    # Save annotated cases JSONL
    cases_path = EVAL_DIR / "role_resolver_eval_cases.jsonl"
    with open(cases_path, "w", encoding="utf-8") as f:
        for case in cases:
            row = {k: v for k, v in case.items() if k != "cv_text"}
            row["cv_text_preview"] = (case.get("cv_text") or "")[:200]
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"✓  Wrote {len(cases)} cases → {cases_path}")

    print("⟳  Loading resolver...")
    resolver = RoleResolver(db_path=str(ONET_DB))

    print("⟳  Running resolver on 40 cases...")
    items = []
    for i, case in enumerate(cases, 1):
        result = _run_case(resolver, case)
        failure_mode = classify_failure(case, result)
        auto_v = _auto_verdict(case, result)
        items.append({
            "case": case,
            "resolver_output": result,
            "auto_verdict": auto_v,
            "failure_mode": failure_mode,
        })
        status = "✓" if auto_v == "match" else ("~" if auto_v == "partial" else "✗")
        fam = result.get("primary_role_family") or "—"
        conf = result.get("occupation_confidence") or 0.0
        inferred_count = len(result.get("inferred_skills") or [])
        norm = (result.get("evidence") or {}).get("normalized_title", "")
        print(
            f"  [{i:02d}] {status} {case['id']:<25} "
            f"fam={fam:<20} conf={conf:.3f}  "
            f"inferred={inferred_count}  norm='{norm[:35]}'"
        )

    print()

    # ── Metrics ──────────────────────────────────────────────────────────────
    metrics_all = compute_metrics(items)
    metrics_profiles = compute_metrics([it for it in items if it["case"]["type"] == "profile"])
    metrics_offers = compute_metrics([it for it in items if it["case"]["type"] == "offer"])
    metrics_fr = compute_metrics([it for it in items if it["case"]["language"] in ("fr", "bilingual")])
    metrics_en = compute_metrics([it for it in items if it["case"]["language"] == "en"])

    metrics_payload = {
        "overall": metrics_all,
        "by_type": {"profile": metrics_profiles, "offer": metrics_offers},
        "by_language": {"fr_or_bilingual": metrics_fr, "en": metrics_en},
    }

    # ── Role family frequency + confusion ────────────────────────────────────
    family_freq: Counter = Counter()
    family_confusion: dict[str, Counter] = {}
    for it in items:
        expected = it["case"].get("expected_role_family", "other")
        predicted = it["resolver_output"].get("primary_role_family") or "none"
        family_freq[predicted] += 1
        family_confusion.setdefault(expected, Counter())[predicted] += 1

    # ── Failure mode distribution ─────────────────────────────────────────────
    failure_dist: Counter = Counter()
    for it in items:
        fm = it["failure_mode"]
        if fm:
            failure_dist[fm] += 1

    # ── Save results CSV ──────────────────────────────────────────────────────
    csv_path = EVAL_DIR / "role_resolver_eval_results.csv"
    fieldnames = [
        "id", "type", "language", "source_type",
        "raw_title", "normalized_title",
        "primary_occupation", "occupation_confidence",
        "primary_role_family", "secondary_role_families",
        "inferred_skills_count", "inferred_skills",
        "expected_role_family", "human_verdict_expected",
        "auto_verdict", "failure_mode",
        "evidence_language", "title_tokens",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for it in items:
            case = it["case"]
            result = it["resolver_output"]
            evidence = result.get("evidence") or {}
            top_occ = (result.get("candidate_occupations") or [{}])[0]
            inferred = result.get("inferred_skills") or []
            writer.writerow({
                "id": case["id"],
                "type": case["type"],
                "language": case["language"],
                "source_type": case["source_type"],
                "raw_title": (case.get("raw_title") or "")[:80],
                "normalized_title": evidence.get("normalized_title", ""),
                "primary_occupation": top_occ.get("occupation_title", ""),
                "occupation_confidence": round(result.get("occupation_confidence") or 0.0, 4),
                "primary_role_family": result.get("primary_role_family") or "",
                "secondary_role_families": "|".join(result.get("secondary_role_families") or []),
                "inferred_skills_count": len(inferred),
                "inferred_skills": "|".join(
                    (s.get("label") or s.get("canonical_skill_id") or "") for s in inferred
                )[:200],
                "expected_role_family": case.get("expected_role_family", ""),
                "human_verdict_expected": case.get("human_verdict_expected", ""),
                "auto_verdict": it["auto_verdict"],
                "failure_mode": it["failure_mode"] or "",
                "evidence_language": evidence.get("language", ""),
                "title_tokens": " ".join(evidence.get("title_tokens") or []),
            })
    print(f"✓  Wrote CSV → {csv_path}")

    # ── Save full JSONL results ───────────────────────────────────────────────
    results_jsonl_path = EVAL_DIR / "role_resolver_eval_results.jsonl"
    with open(results_jsonl_path, "w", encoding="utf-8") as f:
        for it in items:
            row = {
                "id": it["case"]["id"],
                "type": it["case"]["type"],
                "language": it["case"]["language"],
                "raw_title": it["case"].get("raw_title", ""),
                "resolver": it["resolver_output"],
                "expected_role_family": it["case"].get("expected_role_family"),
                "human_verdict_expected": it["case"].get("human_verdict_expected"),
                "auto_verdict": it["auto_verdict"],
                "failure_mode": it["failure_mode"],
                "notes": it["case"].get("notes", ""),
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # ── Save metrics JSON ─────────────────────────────────────────────────────
    metrics_path = EVAL_DIR / "role_resolver_eval_metrics.json"
    full_metrics = {
        "metrics": metrics_payload,
        "family_frequency": dict(family_freq.most_common()),
        "family_confusion_matrix": {k: dict(v) for k, v in family_confusion.items()},
        "failure_mode_distribution": dict(failure_dist.most_common()),
    }
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(full_metrics, f, ensure_ascii=False, indent=2)
    print(f"✓  Wrote metrics → {metrics_path}")

    # ── Print summary ─────────────────────────────────────────────────────────
    m = metrics_all
    print()
    print("═" * 65)
    print("  ROLE RESOLVER TERRAIN VALIDATION — SUMMARY")
    print("═" * 65)
    print(f"  Total cases          : {m['total_cases']} ({metrics_profiles['total_cases']} profiles / {metrics_offers['total_cases']} offers)")
    print(f"  EN cases             : {metrics_en['total_cases']}   FR/bilingual: {metrics_fr['total_cases']}")
    print()
    print(f"  occupation_resolution_rate  : {m['occupation_resolution_rate']:.1%}")
    print(f"  role_family_accuracy        : {m['role_family_accuracy']:.1%}  (of {m['family_evaluable_count']} evaluable cases)")
    print(f"  title_normalization_rate    : {m['title_normalization_rate']:.1%}")
    print(f"  avg_confidence              : {m['avg_confidence']:.4f}")
    print(f"  false_positive_rate         : {m['false_positive_rate']:.1%}")
    print(f"  inferred_skills_avg         : {m['inferred_skills_avg']:.2f}")
    print()
    print(f"  Skills added distribution   : {dict(sorted(m['skills_added_distribution'].items()))}")
    print()
    print("  EN metrics:")
    print(f"    resolution={metrics_en['occupation_resolution_rate']:.1%}  "
          f"family_acc={metrics_en['role_family_accuracy']:.1%}  "
          f"avg_conf={metrics_en['avg_confidence']:.4f}")
    print("  FR/bilingual metrics:")
    print(f"    resolution={metrics_fr['occupation_resolution_rate']:.1%}  "
          f"family_acc={metrics_fr['role_family_accuracy']:.1%}  "
          f"avg_conf={metrics_fr['avg_confidence']:.4f}")
    print()
    print("  Role family frequency (predicted):")
    for fam, cnt in sorted(family_freq.items(), key=lambda x: -x[1]):
        print(f"    {fam:<25} : {cnt}")
    print()
    print("  Failure modes:")
    for mode, cnt in failure_dist.most_common():
        print(f"    {mode:<30} : {cnt}")
    print()

    # Verdict
    resolution = m["occupation_resolution_rate"]
    family_acc = m["role_family_accuracy"]
    false_pos = m["false_positive_rate"]
    inferred_avg = m["inferred_skills_avg"]
    fr_resolution = metrics_fr["occupation_resolution_rate"]

    print("  VERDICT:")
    if resolution >= 0.70 and family_acc >= 0.60 and false_pos <= 0.15:
        verdict = "GO WITH CONSTRAINTS"
    elif resolution >= 0.55 and family_acc >= 0.45:
        verdict = "GO WITH CONSTRAINTS (marginal)"
    else:
        verdict = "NO-GO"
    print(f"  → {verdict}")

    if inferred_avg == 0.0:
        print("  ⚠  inferred_skills_avg=0.00 — enrichment layer is INOPERATIVE (only 8 canonical mappings in DB)")
    elif inferred_avg >= 4.5:
        print("  ⚠  inferred_skills_avg=5.0 — mechanical fill at MAX_ADDED_SKILLS cap, not intelligent enrichment")

    if fr_resolution < resolution * 0.7:
        print("  ⚠  FR resolution significantly below EN — FR→EN translation pipeline needs work")

    print("═" * 65)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
