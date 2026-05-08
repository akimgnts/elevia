"""
test_structured_cv_mock.py — Tests for structured CV mock extraction.

Tests that mock extraction works correctly without API quota.
"""
import os
import pytest


@pytest.fixture(autouse=True)
def cleanup_env():
    """Cleanup mock and AI flags before each test."""
    os.environ.pop("ELEVIA_STRUCTURED_CV_MOCK", None)
    os.environ.pop("ELEVIA_STRUCTURED_CV_AI", None)
    yield
    os.environ.pop("ELEVIA_STRUCTURED_CV_MOCK", None)
    os.environ.pop("ELEVIA_STRUCTURED_CV_AI", None)


class TestStructuredCVMock:
    """Test mock extraction mode."""

    def test_mock_disabled_returns_none(self):
        """Mock disabled should return None."""
        from compass.profile.structured_cv_mock import extract_structured_cv_mock

        os.environ["ELEVIA_STRUCTURED_CV_MOCK"] = "0"
        result = extract_structured_cv_mock("any cv text")
        assert result is None

    def test_mock_enabled_returns_structured_cv(self):
        """Mock enabled should return realistic StructuredCV."""
        from compass.profile.structured_cv_mock import extract_structured_cv_mock

        os.environ["ELEVIA_STRUCTURED_CV_MOCK"] = "1"
        result = extract_structured_cv_mock("any cv text")

        assert result is not None
        assert len(result.experiences) == 3
        assert len(result.projects) == 2
        assert len(result.education) == 1

    def test_mock_contains_elevia_project(self):
        """Mock should contain Elevia project."""
        from compass.profile.structured_cv_mock import extract_structured_cv_mock

        os.environ["ELEVIA_STRUCTURED_CV_MOCK"] = "1"
        result = extract_structured_cv_mock("any cv text")

        projects = result.projects
        elevia = next((p for p in projects if "Elevia" in p.name), None)

        assert elevia is not None
        assert "Elevia" in elevia.name
        assert "PostgreSQL" in elevia.tools
        assert "SQL" in elevia.tools
        assert "Python" in elevia.tools

    def test_mock_bd_clean(self):
        """Mock BD experience should be clean (no contamination)."""
        from compass.profile.structured_cv_mock import extract_structured_cv_mock

        os.environ["ELEVIA_STRUCTURED_CV_MOCK"] = "1"
        result = extract_structured_cv_mock("any cv text")

        bd = next((e for e in result.experiences if "Business Developer" in e.title), None)

        assert bd is not None
        # Responsibilities should not contain project names
        all_resp = " ".join(bd.responsibilities)
        assert "Elevia" not in all_resp
        assert "Personal project" not in all_resp

        # BD should have CRM tools, not data tools
        assert "Salesforce" in bd.tools
        assert "PostgreSQL" not in bd.tools
        assert "SQL" not in bd.tools

    def test_mock_data_analyst_experience(self):
        """Mock should have clean Data & Business Analyst experience."""
        from compass.profile.structured_cv_mock import extract_structured_cv_mock

        os.environ["ELEVIA_STRUCTURED_CV_MOCK"] = "1"
        result = extract_structured_cv_mock("any cv text")

        data_analyst = next(
            (e for e in result.experiences if "Data & Business Analyst" in e.title), None
        )

        assert data_analyst is not None
        assert "PostgreSQL" in data_analyst.tools
        assert "SQL" in data_analyst.tools
        assert "Python" in data_analyst.tools

    def test_mock_integration_with_extractor(self):
        """Mock should integrate with main extractor when flag enabled."""
        from compass.profile.structured_cv_extractor import extract_structured_cv

        os.environ["ELEVIA_STRUCTURED_CV_MOCK"] = "1"
        os.environ["ELEVIA_STRUCTURED_CV_AI"] = "1"

        result = extract_structured_cv("any cv text")

        assert result is not None
        assert len(result.projects) == 2
        assert len(result.experiences) == 3

    def test_mock_extraction_source_in_integration(self):
        """Mock extraction should set extraction_source = 'structured_mock'."""
        from compass.profile.structured_cv_integration import attempt_structured_cv_extraction

        os.environ["ELEVIA_STRUCTURED_CV_MOCK"] = "1"
        os.environ["ELEVIA_STRUCTURED_CV_AI"] = "1"

        cv, metadata = attempt_structured_cv_extraction("any cv text")

        assert cv is not None
        assert metadata["extraction_source"] == "structured_mock"
        assert metadata["structured_cv_success"] is True
        assert metadata["fallback_reason"] is None

    def test_mock_requires_ai_flag(self):
        """Mock should not run if ELEVIA_STRUCTURED_CV_AI is OFF."""
        from compass.profile.structured_cv_integration import attempt_structured_cv_extraction

        os.environ["ELEVIA_STRUCTURED_CV_MOCK"] = "1"
        os.environ["ELEVIA_STRUCTURED_CV_AI"] = "0"

        cv, metadata = attempt_structured_cv_extraction("any cv text")

        assert cv is None
        assert metadata["extraction_source"] == "legacy_parser"
        assert metadata["fallback_reason"] == "feature_flag_off"

    def test_mock_education_apprenticeship(self):
        """Mock should have apprenticeship in education (not in experience)."""
        from compass.profile.structured_cv_mock import extract_structured_cv_mock

        os.environ["ELEVIA_STRUCTURED_CV_MOCK"] = "1"
        result = extract_structured_cv_mock("any cv text")

        education = result.education
        apprenticeship = next((e for e in education if "Apprenticeship" in e.degree), None)

        assert apprenticeship is not None
        assert apprenticeship.institution == "Vassard OMB Mobilier"

    def test_mock_cv_quality(self):
        """Mock should have good CV quality."""
        from compass.profile.structured_cv_adapter import structured_to_profile_v1

        from compass.profile.structured_cv_mock import get_mock_structured_cv

        mock_cv = get_mock_structured_cv()
        profile_v1 = structured_to_profile_v1(mock_cv)

        # Mock has good coverage
        assert profile_v1.cv_quality is not None
        # Should have tools, experiences, projects, education
        assert len(profile_v1.extracted_tools) > 0
        assert len(profile_v1.extracted_companies) > 0

    def test_mock_ignores_cv_text(self):
        """Mock should return same result regardless of CV text."""
        from compass.profile.structured_cv_mock import extract_structured_cv_mock

        os.environ["ELEVIA_STRUCTURED_CV_MOCK"] = "1"

        result1 = extract_structured_cv_mock("cv text 1")
        result2 = extract_structured_cv_mock("completely different cv text")

        # Should be identical
        assert len(result1.experiences) == len(result2.experiences)
        assert len(result1.projects) == len(result2.projects)
        assert result1.projects[0].name == result2.projects[0].name
