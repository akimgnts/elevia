"""
test_canonical_aliases_data.py — ensure new aliases resolve to canonical IDs.
"""
from compass.canonical.canonical_mapper import map_to_canonical
from compass.canonical.canonical_store import get_canonical_store, reset_canonical_store


def _map(label: str) -> str:
    reset_canonical_store()
    store = get_canonical_store()
    res = map_to_canonical([label], store=store)
    if not res.mappings:
        return ""
    return res.mappings[0].canonical_id


def test_alias_api_maps():
    assert _map("API") == "skill:software_api"
    assert _map("APIs") == "skill:software_api"


def test_alias_rest_maps():
    assert _map("REST") == "skill:web_service_api"
    assert _map("REST API") == "skill:web_service_api"


def test_alias_dashboards_maps():
    assert _map("dashboards") == "skill:data_visualization"


def test_alias_r_maps():
    assert _map("R") == "skill:statistical_programming"


def test_alias_bi_ml_dataiku_maps():
    assert _map("BI") == "skill:business_intelligence"
    assert _map("ML") == "skill:machine_learning"
    assert _map("dataiku") == "skill:data_science_platform"
