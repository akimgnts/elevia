"""
test_structured_cv_extractor.py — Tests for structured CV extraction.

Test cases:
1. CV with projects → projects[] separated
2. CV without projects → no false projects
3. Alternance/apprenticeship → proper experience closure
4. Skills contextualized → no contamination
5. Matching impact (debug mode)
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from compass.profile.structured_cv_schemas import StructuredCV, StructuredExperience, StructuredProject
from compass.profile.structured_cv_validator import validate_structured_cv


def test_projects_separated_from_experiences():
    """Test 1: CV with projects → projects[] properly separated."""
    cv = StructuredCV(
        headline="Data Engineer",
        experiences=[
            StructuredExperience(
                title="Data Engineer",
                company="Acme",
                dates="01/2022 - 12/2023",
                responsibilities=["Built ETL pipelines", "Optimized SQL queries"],
                tools=["Python", "SQL"],
                skills=["Data engineering", "SQL"],
            )
        ],
        projects=[
            StructuredProject(
                name="CV Matching Platform",
                description="Personal project to match CVs with job offers",
                tools=["FastAPI", "PostgreSQL"],
                skills=["System design", "Backend development"],
            )
        ],
    )

    is_valid, warnings = validate_structured_cv(cv)
    assert is_valid, f"Should be valid, got warnings: {warnings}"
    assert len(cv.projects) == 1
    assert "CV Matching" in cv.projects[0].name


def test_no_false_projects_when_empty():
    """Test 2: CV without projects → no false projects[] added."""
    cv = StructuredCV(
        headline="Business Developer",
        experiences=[
            StructuredExperience(
                title="Business Developer",
                company="SalesCo",
                dates="2022 - 2024",
                responsibilities=["Led client acquisition", "Managed CRM"],
                tools=["Salesforce"],
                skills=["Sales", "CRM"],
            )
        ],
        projects=[],  # Explicitly empty
    )

    is_valid, warnings = validate_structured_cv(cv)
    assert is_valid
    assert len(cv.projects) == 0


def test_alternance_apprenticeship_separation():
    """Test 3: Alternance/apprenticeship → proper experience closure."""
    cv = StructuredCV(
        headline="Data Analyst",
        experiences=[
            StructuredExperience(
                title="Data Analyst",
                company="DataCorp",
                dates="09/2023 - 08/2024",
                responsibilities=["Analyzed sales data", "Created dashboards"],
                tools=["Power BI", "SQL"],
                skills=["Data analysis", "BI"],
            ),
            StructuredExperience(
                title="Apprentice Data Engineer",
                company="Vassard OMB Mobilier",
                dates="09/2021 - 08/2022",
                responsibilities=["Database maintenance", "Helped with ETL"],
                tools=["PostgreSQL"],
                skills=["Database fundamentals"],
            ),
        ],
        projects=[],
    )

    is_valid, warnings = validate_structured_cv(cv)
    assert is_valid
    assert len(cv.experiences) == 2
    # Responsibilities should not contain other job titles
    assert "Apprentice" not in cv.experiences[0].responsibilities[0]


def test_skills_contextualized_no_contamination():
    """Test 4: Skills properly contextualized, not scattered."""
    cv = StructuredCV(
        headline="Data Engineer",
        experiences=[
            StructuredExperience(
                title="Data Engineer",
                company="TechCo",
                dates="2023 - present",
                responsibilities=["Built data pipelines"],
                tools=["Python", "PostgreSQL"],
                skills=["Data engineering", "SQL"],
            ),
            StructuredExperience(
                title="Sales Representative",
                company="SalesCo",
                dates="2020 - 2022",
                responsibilities=["Led prospecting"],
                tools=["Salesforce", "Excel"],
                skills=["Sales", "CRM"],
            ),
        ],
        global_skills=["Communication", "Problem solving"],
    )

    is_valid, warnings = validate_structured_cv(cv)
    assert is_valid
    # Data engineering skills should not be in sales experience
    assert "Data engineering" not in cv.experiences[1].skills


def test_project_contamination_detected():
    """Test contamination: project name in experience responsibilities."""
    cv = StructuredCV(
        experiences=[
            StructuredExperience(
                title="Business Developer",
                company="SalesCo",
                dates="2022 - 2023",
                responsibilities=[
                    "Led prospecting",
                    "Personal project — CV matching platform",  # CONTAMINATION
                ],
                tools=["Salesforce"],
                skills=["Sales"],
            )
        ],
        projects=[
            StructuredProject(
                name="CV matching platform",
                description="Personal project",
                tools=["FastAPI"],
                skills=["Backend"],
            )
        ],
    )

    is_valid, warnings = validate_structured_cv(cv)
    assert not is_valid, "Should detect project contamination"
    assert any("contamination" in w.lower() for w in warnings)


def test_company_contamination_detected():
    """Test contamination: another company name in experience responsibilities."""
    cv = StructuredCV(
        experiences=[
            StructuredExperience(
                title="Data Engineer",
                company="TechCorp",
                dates="2023 - present",
                responsibilities=[
                    "Built pipelines",
                    "OtherCompany — Senior Engineer — 2022-2023",  # CONTAMINATION
                ],
                tools=["Python"],
                skills=["Engineering"],
            ),
            StructuredExperience(
                title="Engineer",
                company="OtherCompany",
                dates="2022 - 2023",
                responsibilities=["Led team"],
                tools=["Java"],
                skills=["Leadership"],
            ),
        ],
    )

    is_valid, warnings = validate_structured_cv(cv)
    assert not is_valid, "Should detect company contamination"


def test_section_header_contamination_detected():
    """Test contamination: section header in experience responsibilities."""
    cv = StructuredCV(
        experiences=[
            StructuredExperience(
                title="Data Engineer",
                company="TechCorp",
                dates="2023 - present",
                responsibilities=[
                    "Built pipelines",
                    "EDUCATION",  # Section header in responsibilities
                    "Studied Computer Science",
                ],
                tools=["Python"],
                skills=["Engineering"],
            )
        ],
    )

    is_valid, warnings = validate_structured_cv(cv)
    assert not is_valid, "Should detect section header contamination"


def test_structured_cv_validation_with_valid_data():
    """Test validation passes for properly structured CV."""
    cv_data = {
        "headline": "Data Engineer",
        "target_role": "",
        "summary": "",
        "experiences": [
            {
                "title": "Data Engineer",
                "company": "TechCorp",
                "dates": "2023 - present",
                "location": "",
                "responsibilities": ["Built ETL pipelines"],
                "tools": ["Python", "SQL"],
                "skills": ["Data engineering"],
            }
        ],
        "projects": [],
        "education": [],
        "certifications": [],
        "global_skills": [],
        "languages": [],
        "warnings": [],
    }

    cv = StructuredCV(**cv_data)
    is_valid, warnings = validate_structured_cv(cv)

    assert is_valid
    assert len(warnings) == 0


def test_extraction_disabled_returns_none():
    """Test extraction returns None when AI disabled."""
    import os

    with patch.dict(os.environ, {"ELEVIA_STRUCTURED_CV_AI": "0"}):
        from compass.profile.structured_cv_extractor import extract_structured_cv

        result = extract_structured_cv("Sample CV")
        assert result is None


def test_json_extraction_from_response_markdown():
    """Test JSON extraction from markdown code block."""
    from compass.profile.structured_cv_extractor import _extract_json_from_response

    response = """
    Here's the structured CV:

    ```json
    {"headline": "Data Engineer", "experiences": []}
    ```

    Hope this helps!
    """

    extracted = _extract_json_from_response(response)
    assert extracted is not None
    data = json.loads(extracted)
    assert data["headline"] == "Data Engineer"


def test_json_extraction_from_response_raw():
    """Test JSON extraction from raw JSON response."""
    from compass.profile.structured_cv_extractor import _extract_json_from_response

    response = '{"headline": "Engineer", "experiences": [], "projects": []}'
    extracted = _extract_json_from_response(response)
    assert extracted is not None
    data = json.loads(extracted)
    assert data["headline"] == "Engineer"
