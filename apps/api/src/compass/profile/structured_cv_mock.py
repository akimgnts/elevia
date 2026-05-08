"""
structured_cv_mock.py — Mock extraction for testing integration without API quota.

IMPORTANT: Never enable in production. Use only for development/testing.
"""
from typing import Optional
from .structured_cv_schemas import (
    StructuredCV,
    StructuredExperience,
    StructuredProject,
    StructuredEducation,
)


def get_mock_structured_cv() -> StructuredCV:
    """
    Return realistic mock StructuredCV based on Akim Guentas Data Engineer CV.

    This is used when ELEVIA_STRUCTURED_CV_MOCK=1 (development only).
    Never use in production.
    """
    return StructuredCV(
        experiences=[
            StructuredExperience(
                title="Data & Business Analyst",
                company="Sidel",
                start_date="2023-01",
                end_date="2025-01",
                duration_months=24,
                responsibilities=[
                    "Designed and implemented multi-stage ETL pipelines to process manufacturing data",
                    "Built data warehouses using PostgreSQL and optimized SQL queries for analytics",
                    "Developed Power BI dashboards for real-time monitoring of production metrics",
                    "Mentored junior analysts on data modeling and best practices",
                ],
                tools=["PostgreSQL", "SQL", "Python", "Power BI", "Elasticsearch"],
                skills=["Data engineering", "ETL pipeline design", "SQL optimization", "Analytics"],
            ),
            StructuredExperience(
                title="Business Developer",
                company="Vassard OMB Mobilier",
                start_date="2022-01",
                end_date="2023-01",
                duration_months=12,
                responsibilities=[
                    "Structured CRM and commercial data to improve visibility on prospects and clients",
                    "Implemented performance tracking processes to support sales decisions",
                    "Analyzed customer and sales data to identify priorities for follow-up",
                    "Developed understanding of business processes and operational requirements",
                ],
                tools=["Salesforce", "Excel", "Power BI"],
                skills=["Business development", "CRM", "Commercial analysis", "Data interpretation"],
            ),
            StructuredExperience(
                title="Freelance Developer",
                company="Various clients",
                start_date="2020-01",
                end_date="2024-01",
                duration_months=48,
                responsibilities=[
                    "Developed web applications and data solutions for various clients",
                    "Implemented backend systems using Python and FastAPI",
                    "Designed databases and optimized queries for performance",
                ],
                tools=["Python", "FastAPI", "PostgreSQL", "JavaScript"],
                skills=["Backend development", "System design", "Database design"],
            ),
        ],
        projects=[
            StructuredProject(
                name="Elevia — Data Platform & AI Matching System",
                description="Designed a multi-stage data pipeline to process job market data from raw sources into cleaned and enriched datasets. Built search and matching algorithms using machine learning.",
                tools=["PostgreSQL", "Elasticsearch", "SQL", "Python", "FastAPI"],
                skills=["Data engineering", "System design", "Backend development", "Machine learning"],
                dates="2020-2024",
            ),
            StructuredProject(
                name="Personal project — CV ↔ job offer matching platform",
                description="AI-powered platform to match CVs with job opportunities. Implemented REST API, database schema, and matching algorithms.",
                tools=["FastAPI", "PostgreSQL", "Python", "React"],
                skills=["System design", "Backend development", "Frontend development"],
                dates="2021-2024",
            ),
        ],
        education=[
            StructuredEducation(
                degree="Apprenticeship",
                field="Commercial business / Sales",
                institution="Vassard OMB Mobilier",
                graduation_date="2023-01",
            ),
        ],
        certifications=[],
    )


def extract_structured_cv_mock(cv_text: str) -> Optional[StructuredCV]:
    """
    Mock extraction. Returns pre-built StructuredCV.

    Args:
        cv_text: CV text (ignored in mock)

    Returns:
        Realistic StructuredCV or None if mock disabled
    """
    import os

    mock_enabled = os.getenv("ELEVIA_STRUCTURED_CV_MOCK", "0") == "1"
    if not mock_enabled:
        return None

    return get_mock_structured_cv()
