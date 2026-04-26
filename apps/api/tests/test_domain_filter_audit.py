import importlib.util
from pathlib import Path


def _load_script_module():
    script_path = Path("scripts/run_domain_filter_audit.py").resolve()
    spec = importlib.util.spec_from_file_location("run_domain_filter_audit", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_filter_catalog_by_offer_ids_keeps_only_requested_business_france_offers():
    mod = _load_script_module()

    catalog = [
        {"id": "BF-1", "source": "business_france", "title": "A"},
        {"id": "BF-2", "source": "business_france", "title": "B"},
        {"id": "FT-1", "source": "france_travail", "title": "C"},
    ]

    filtered = mod.filter_catalog_by_offer_ids(catalog, {"BF-2"})

    assert filtered == [{"id": "BF-2", "source": "business_france", "title": "B"}]


def test_build_domain_distribution_counts_tags_from_top_items():
    mod = _load_script_module()

    items = [
        {"offer_id": "1", "domain_tag": "data"},
        {"offer_id": "2", "domain_tag": "data"},
        {"offer_id": "3", "domain_tag": "sales"},
        {"offer_id": "4", "domain_tag": None},
    ]

    distribution = mod.build_domain_distribution(items)

    assert distribution == {"data": 2, "sales": 1, "unknown": 1}
