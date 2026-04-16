from compass.understanding import CVUnderstandingAgent


def test_agent_returns_document_understanding_root():
    result = CVUnderstandingAgent().run(
        {
            "cv_text": "Jean Dupont\nData Analyst\njean@example.com",
            "source_name": "cv.txt",
            "raw_profile": {},
        }
    )

    assert "document_understanding" in result
    doc = result["document_understanding"]
    assert "identity" in doc
    assert "summary" in doc
    assert "skills_block" in doc
    assert "experience_blocks" in doc
    assert "education_blocks" in doc
    assert "project_blocks" in doc
    assert "other_blocks" in doc
    assert "confidence" in doc
    assert "parsing_diagnostics" in doc
    assert "comparison_metrics" in doc["parsing_diagnostics"]


def test_agent_is_deterministic():
    payload = {
        "cv_text": "Jean Dupont\nData Analyst\njean@example.com",
        "source_name": "cv.txt",
        "raw_profile": {},
    }

    first = CVUnderstandingAgent().run(payload)
    second = CVUnderstandingAgent().run(payload)

    assert first == second


def test_extracts_basic_identity():
    text = """Jean Dupont
Data Analyst
jean.dupont@example.com
+33 6 12 34 56 78
linkedin.com/in/jeandupont
Paris
"""
    doc = CVUnderstandingAgent().run(
        {"cv_text": text, "source_name": "cv.txt", "raw_profile": {}}
    )["document_understanding"]

    assert doc["identity"]["full_name"] == "Jean Dupont"
    assert doc["identity"]["email"] == "jean.dupont@example.com"
    assert "linkedin.com/in/jeandupont" in doc["identity"]["linkedin"]
    assert doc["identity"]["location"] == "Paris"


def test_separates_summary_from_experience_section():
    text = """Jane Doe
PROFILE
Full-stack engineer with 4 years of experience building web applications.

WORK EXPERIENCE
Full Stack Developer - Acme
2022 - Present
Built internal tools in React and Node.js.
"""
    doc = CVUnderstandingAgent().run(
        {"cv_text": text, "source_name": "cv.txt", "raw_profile": {}}
    )["document_understanding"]

    assert "4 years of experience" in doc["summary"]["text"]
    assert len(doc["experience_blocks"]) == 1
    assert doc["experience_blocks"][0]["company"] == "Acme"
    assert "4 years of experience" not in " ".join(
        doc["experience_blocks"][0]["description_lines"]
    )


def test_separates_education_from_experience():
    text = """WORK EXPERIENCE
Data Analyst - Acme
2022 - Present
Built dashboards.

EDUCATION
Master in Data Science - Université Paris-Dauphine
2020 - 2022
"""
    doc = CVUnderstandingAgent().run(
        {"cv_text": text, "source_name": "cv.txt", "raw_profile": {}}
    )["document_understanding"]

    assert len(doc["experience_blocks"]) == 1
    assert len(doc["education_blocks"]) == 1
    assert doc["education_blocks"][0]["institution"] == "Université Paris-Dauphine"


def test_does_not_promote_pre_section_summary_to_identity_headline_or_location():
    text = """Jean Dupont
Full-stack engineer focused on product delivery and quality.
Open to remote opportunities.

PROFILE
Summary line should stay in summary.
"""
    doc = CVUnderstandingAgent().run(
        {"cv_text": text, "source_name": "cv.txt", "raw_profile": {}}
    )["document_understanding"]

    assert doc["identity"]["full_name"] == "Jean Dupont"
    assert doc["identity"]["headline"] == ""
    assert doc["identity"]["location"] == ""
    assert "Full-stack engineer focused on product delivery and quality." in doc["summary"]["text"]


def test_recognizes_inline_summary_and_skills_headers():
    text = """Jean Dupont
PROFILE: Seasoned data analyst with a focus on reporting and automation.
SKILLS: Python, SQL, Looker
"""
    doc = CVUnderstandingAgent().run(
        {"cv_text": text, "source_name": "cv.txt", "raw_profile": {}}
    )["document_understanding"]

    assert doc["summary"]["text"] == "Seasoned data analyst with a focus on reporting and automation."
    assert doc["skills_block"]["raw_lines"] == ["Python, SQL, Looker"]


def test_detects_multiple_experience_blocks_with_deterministic_ownership():
    text = """WORK EXPERIENCE
Data Analyst - Acme
2022 - Present
Built dashboards.

Backend Developer - Beta
2020 - 2022
Built APIs.
"""
    doc = CVUnderstandingAgent().run(
        {"cv_text": text, "source_name": "cv.txt", "raw_profile": {}}
    )["document_understanding"]

    assert len(doc["experience_blocks"]) == 2
    assert doc["experience_blocks"][0]["company"] == "Acme"
    assert doc["experience_blocks"][1]["company"] == "Beta"


def test_detects_projects_as_separate_blocks():
    text = """PROJECTS
Dynamic Website Development - Le Havre Est A Vous
2023
Built a showcase website.

Open Data Portal - City of Paris
2021
Designed a public data portal.
"""
    doc = CVUnderstandingAgent().run(
        {"cv_text": text, "source_name": "cv.txt", "raw_profile": {}}
    )["document_understanding"]

    assert len(doc["project_blocks"]) == 2
    assert doc["project_blocks"][0]["title"] == "Dynamic Website Development"
    assert doc["project_blocks"][1]["organization"] == "City of Paris"


def test_does_not_treat_summary_sentence_as_company_when_segmenting_experience():
    text = """WORK EXPERIENCE
Engineer focused on product quality and collaboration.
Data Analyst - Acme
2022 - Present
Built dashboards.
"""
    doc = CVUnderstandingAgent().run(
        {"cv_text": text, "source_name": "cv.txt", "raw_profile": {}}
    )["document_understanding"]

    assert len(doc["experience_blocks"]) == 1
    assert doc["experience_blocks"][0]["company"] == "Acme"
    assert doc["experience_blocks"][0]["title"] == "Data Analyst"
    assert "Engineer focused on product quality and collaboration." not in doc["experience_blocks"][0]["company"]


def test_experience_blocks_expose_expected_fields_and_parse_date_ranges():
    text = """WORK EXPERIENCE
Data Analyst - Acme
Paris
2022 - Present
Built dashboards.

Backend Developer - Beta
Lyon
2020 - 2022
Built APIs.
"""
    doc = CVUnderstandingAgent().run(
        {"cv_text": text, "source_name": "cv.txt", "raw_profile": {}}
    )["document_understanding"]

    first = doc["experience_blocks"][0]
    second = doc["experience_blocks"][1]

    assert set(["title", "company", "location", "start_date", "end_date", "description_lines", "header_raw", "confidence"]).issubset(first)
    assert first["title"] == "Data Analyst"
    assert first["company"] == "Acme"
    assert first["location"] == "Paris"
    assert first["start_date"] == "2022"
    assert first["end_date"] == "Present"
    assert first["description_lines"] == ["Built dashboards."]
    assert first["header_raw"] == "Data Analyst - Acme"

    assert second["title"] == "Backend Developer"
    assert second["company"] == "Beta"
    assert second["location"] == "Lyon"
    assert second["start_date"] == "2020"
    assert second["end_date"] == "2022"
    assert second["description_lines"] == ["Built APIs."]


def test_education_and_project_blocks_use_the_same_block_contract_with_defaults():
    text = """EDUCATION
Master in Data Science - Université Paris-Dauphine
2020

PROJECTS
Dynamic Website Development - Le Havre Est A Vous
Built a showcase website.
"""
    doc = CVUnderstandingAgent().run(
        {"cv_text": text, "source_name": "cv.txt", "raw_profile": {}}
    )["document_understanding"]

    education = doc["education_blocks"][0]
    project = doc["project_blocks"][0]

    assert set(["title", "institution", "start_date", "end_date", "description_lines", "header_raw", "confidence"]).issubset(education)
    assert education["title"] == "Master in Data Science"
    assert education["institution"] == "Université Paris-Dauphine"
    assert education["start_date"] == "2020"
    assert education["end_date"] == ""
    assert education["description_lines"] == []
    assert education["header_raw"] == "Master in Data Science - Université Paris-Dauphine"

    assert set(["title", "organization", "start_date", "end_date", "description_lines", "header_raw", "confidence"]).issubset(project)
    assert project["title"] == "Dynamic Website Development"
    assert project["organization"] == "Le Havre Est A Vous"
    assert project["start_date"] == ""
    assert project["end_date"] == ""
    assert project["description_lines"] == ["Built a showcase website."]
    assert project["header_raw"] == "Dynamic Website Development - Le Havre Est A Vous"


def test_parsing_diagnostics_capture_ambiguous_merges_and_orphans():
    text = """Jane Doe
PROFILE
Some summary.

WORK EXPERIENCE
Engineer focused on delivery.
Lead Developer - Acme - 2021 - Present
Built platform.

EDUCATION
Master in CS - University X - 2020 - 2022
"""
    doc = CVUnderstandingAgent().run(
        {
            "cv_text": text,
            "source_name": "cv.txt",
            "raw_profile": {
                "experiences": [{}, {}],
                "education": [{}],
            },
        }
    )["document_understanding"]
    diagnostics = doc["parsing_diagnostics"]

    assert diagnostics["sections_detected"]
    assert diagnostics["orphan_lines"]
    assert diagnostics["suspicious_merges"]
    assert diagnostics["warnings"]
    assert diagnostics["comparison_metrics"]["identity_detected"] is True
    assert diagnostics["comparison_metrics"]["experience_blocks_count"] == 0
    assert diagnostics["comparison_metrics"]["education_blocks_count"] == 0
    assert diagnostics["comparison_metrics"]["project_blocks_count"] == 0
    assert diagnostics["comparison_metrics"]["suspicious_merges_count"] >= 1
    assert diagnostics["comparison_metrics"]["legacy_experiences_count"] == 2
    assert diagnostics["comparison_metrics"]["legacy_education_count"] == 1
    assert diagnostics["comparison_metrics"]["experience_count_delta_vs_legacy"] == -2
    assert diagnostics["comparison_metrics"]["education_count_delta_vs_legacy"] == -1


def test_diagnostics_warn_about_merged_headers_in_ambiguous_sections():
    text = """Jane Doe
PROFILE
Some summary.

WORK EXPERIENCE
Lead Developer - Acme - 2021 - Present
Built platform.

EDUCATION
Master in CS - University X - 2020 - 2022
"""
    diagnostics = CVUnderstandingAgent().run(
        {"cv_text": text, "source_name": "cv.txt", "raw_profile": {}}
    )["document_understanding"]["parsing_diagnostics"]

    assert any("merge" in warning.lower() for warning in diagnostics["warnings"])
    assert any("Lead Developer - Acme - 2021 - Present" in merge["header_raw"] for merge in diagnostics["suspicious_merges"])


def test_diagnostics_do_not_flag_plain_date_ranges_as_merged_headers():
    text = """Jane Doe
PROFILE
Some summary.

WORK EXPERIENCE
Data Analyst - Acme
2022 - Present
Built dashboards.
"""
    diagnostics = CVUnderstandingAgent().run(
        {"cv_text": text, "source_name": "cv.txt", "raw_profile": {}}
    )["document_understanding"]["parsing_diagnostics"]

    assert diagnostics["suspicious_merges"] == []
    assert diagnostics["comparison_metrics"]["suspicious_merges_count"] == 0
    assert all("merge" not in warning.lower() for warning in diagnostics["warnings"])


def test_identity_detected_counts_contact_only_signals():
    phone_only = CVUnderstandingAgent().run(
        {
            "cv_text": """+33 6 12 34 56 78
""",
            "source_name": "cv.txt",
            "raw_profile": {},
        }
    )["document_understanding"]["parsing_diagnostics"]["comparison_metrics"]

    linkedin_only = CVUnderstandingAgent().run(
        {
            "cv_text": """linkedin.com/in/jeandupont
""",
            "source_name": "cv.txt",
            "raw_profile": {},
        }
    )["document_understanding"]["parsing_diagnostics"]["comparison_metrics"]

    location_only = CVUnderstandingAgent().run(
        {
            "cv_text": """Paris
""",
            "source_name": "cv.txt",
            "raw_profile": {},
        }
    )["document_understanding"]["parsing_diagnostics"]["comparison_metrics"]

    assert phone_only["identity_detected"] is True
    assert linkedin_only["identity_detected"] is True
    assert location_only["identity_detected"] is True


def test_comparison_metrics_include_block1_understanding_fields():
    text = """Jean Dupont
PROFILE
Data analyst focused on reporting.

WORK EXPERIENCE
Data Analyst - Acme
2022 - Present
Built dashboards.

PROJECTS
Open Data Portal - City of Paris
2021
Built a public portal.
"""
    metrics = CVUnderstandingAgent().run(
        {"cv_text": text, "source_name": "cv.txt", "raw_profile": {}}
    )["document_understanding"]["parsing_diagnostics"]["comparison_metrics"]

    assert "identity_detected_understanding" in metrics
    assert "experience_count_understanding" in metrics
    assert "project_count_understanding" in metrics
    assert "suspicious_merges_count" in metrics
    assert "orphan_lines_count" in metrics
    assert "invalid_experience_headers_count" in metrics


def test_invalid_experience_headers_count_flags_polluted_headers():
    text = """WORK EXPERIENCE
Engineer - ISEN Lille and I am actively seeking an opportunity.
2022 - Present
Built platform features.
"""
    metrics = CVUnderstandingAgent().run(
        {"cv_text": text, "source_name": "cv.txt", "raw_profile": {}}
    )["document_understanding"]["parsing_diagnostics"]["comparison_metrics"]

    assert metrics["invalid_experience_headers_count"] >= 1
