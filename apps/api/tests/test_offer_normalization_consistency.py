from __future__ import annotations

import copy
from unittest.mock import Mock


def test_ingest_runtime_skills_uri_consistent():
    """
    The ingest pipeline and inbox runtime must produce identical skills_uri
    for the same offer payload (canonical normalization).
    """
    from compass.offer_canonicalization import normalize_offers_to_uris
    from api.utils import inbox_catalog

    base_offer = {
        "id": "T-123",
        "title": "Data Analyst / BI",
        "description": "Power BI dashboards, SQL, Python, and Excel reporting.",
        "skills": ["Power BI", "SQL", "Excel"],
        "company": "ACME",
        "city": "Paris",
        "country": "France",
    }

    ingest_offer = copy.deepcopy(base_offer)
    normalize_offers_to_uris([ingest_offer], include_domain_uris=True)
    ingest_uris = ingest_offer.get("skills_uri") or []

    runtime_offer = copy.deepcopy(base_offer)
    inbox_catalog._apply_esco_normalization([runtime_offer])  # runtime path
    runtime_uris = runtime_offer.get("skills_uri") or []

    assert ingest_uris == runtime_uris, (
        "Ingest vs runtime skills_uri mismatch.\n"
        f"ingest={ingest_uris}\n"
        f"runtime={runtime_uris}"
    )


def test_runtime_catalog_skips_full_normalization_when_db_skills_are_precomputed(monkeypatch):
    from api.utils import inbox_catalog

    normalize_mock = Mock(side_effect=AssertionError("full ESCO normalization should be skipped"))
    monkeypatch.setattr(inbox_catalog, "normalize_offers_to_uris", normalize_mock)

    runtime_offer = {
        "id": "T-FAST",
        "title": "Data Analyst / BI",
        "description": "Power BI dashboards, SQL, Python, and Excel reporting.",
        "skills": ["Power BI", "SQL", "Excel"],
        "skills_uri": ["uri:power-bi", "uri:sql", "uri:excel"],
        "company": "ACME",
        "city": "Paris",
        "country": "France",
    }

    offers = inbox_catalog._apply_esco_normalization([runtime_offer])

    assert normalize_mock.call_count == 0
    assert offers[0]["skills_uri"] == ["uri:power-bi", "uri:sql", "uri:excel"]
    assert offers[0]["skills_uri_count"] == 3
    assert offers[0]["skills_display"] == [
        {"label": "Power BI", "source": "precomputed"},
        {"label": "SQL", "source": "precomputed"},
        {"label": "Excel", "source": "precomputed"},
    ]
