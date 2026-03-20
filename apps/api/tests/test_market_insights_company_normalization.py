from api.routes.market_insights import _cluster_company_names, _normalize_company


def test_company_normalize_suffix_removal():
    assert _normalize_company("Capgemini SAS") == "capgemini"


def test_company_clustering_variants():
    mapping = _cluster_company_names(
        ["Capgemini", "CAP GEMINI", "Cap Gemini Engineering"]
    )
    assert mapping["Capgemini"] == mapping["CAP GEMINI"] == mapping["Cap Gemini Engineering"]
