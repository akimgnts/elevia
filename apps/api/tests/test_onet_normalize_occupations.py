from integrations.onet.normalizers.normalize_occupations import normalize_occupation_rows


def test_normalize_occupation_rows_projects_expected_fields():
    rows = [{
        "onetsoc_code": "15-1252.00",
        "title": "Software Developers",
        "description": "Develop software.",
    }]

    result = normalize_occupation_rows(rows, source_db_version_name="O*NET 30.2")

    assert len(result) == 1
    assert result[0]["onetsoc_code"] == "15-1252.00"
    assert result[0]["title_norm"] == "software developers"
    assert result[0]["source_db_version_name"] == "O*NET 30.2"
    assert result[0]["status"] == "active"
