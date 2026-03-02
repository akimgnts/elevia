from compass.profile_structurer import structure_profile_text_v1


def test_profile_structurer_debug_invariance() -> None:
    cv_text = """
    EXPERIENCE
    Data Analyst - 2020-2023
    Built dashboards and automated reports.
    SKILLS
    Python, SQL, Excel, Power BI
    EDUCATION
    MSc Data Science 2018-2020
    """
    base = structure_profile_text_v1(cv_text, debug=False)
    debug = structure_profile_text_v1(cv_text, debug=True)

    base_dump = base.model_dump()
    debug_dump = debug.model_dump()
    base_dump.pop("extracted_sections", None)
    debug_dump.pop("extracted_sections", None)

    assert base_dump == debug_dump
