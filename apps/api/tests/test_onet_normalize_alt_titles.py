from integrations.onet.normalizers.normalize_alt_titles import normalize_alt_title_rows


def test_normalize_alt_titles_creates_normalized_key():
    rows = [{
        "onetsoc_code": "15-1252.00",
        "alternate_title": "Software Developer",
        "short_title": "Developer",
        "sources": "10",
    }]

    result = normalize_alt_title_rows(rows)

    assert len(result) == 1
    assert result[0]["alt_title_norm"] == "software developer"
    assert result[0]["short_title"] == "Developer"
