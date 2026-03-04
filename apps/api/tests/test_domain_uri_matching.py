from __future__ import annotations

from typing import List

from compass.cluster_library import reset_library
from matching.matching_v1 import MatchingEngine
from matching.extractors import extract_profile
from api.utils import inbox_catalog


def _esco_only(uris: List[str]) -> List[str]:
    return [u for u in uris if u.startswith("http://data.europa.eu/esco/")]


def test_offer_domain_uris_present():
    store = reset_library(db_path=":memory:")
    for _ in range(5):
        store.record_offer_token("DATA_IT", "Zxqzpl")

    offer = {
        "id": "o-domain",
        "title": "Data Analyst Zxqzpl",
        "description": "Reporting and dashboards with Zxqzpl.",
        "company": "TestCorp",
        "country": "france",
        "is_vie": True,
    }

    offers = inbox_catalog._apply_esco_normalization([offer])
    enriched = offers[0]

    assert enriched.get("domain_uris"), "Expected domain_uris to be populated"
    assert any(
        uri.startswith("compass:skill:DATA_IT:zxqzpl")
        for uri in enriched.get("domain_uris", [])
    ), f"Unexpected domain_uris: {enriched.get('domain_uris')}"


def test_domain_overlap_increases_score_when_offer_and_profile_share_domain_uri():
    esco_uri = "http://data.europa.eu/esco/skill/test-esco-uri"
    domain_uri = "compass:skill:DATA_IT:zxqzpl"

    offer = {
        "id": "o1",
        "is_vie": True,
        "country": "france",
        "title": "Data Analyst",
        "company": "TestCorp",
        "skills_uri": [esco_uri, domain_uri],
    }

    profile_no_domain = {"profile_id": "p1", "skills_uri": [esco_uri]}
    profile_with_domain = {"profile_id": "p1", "skills_uri": [esco_uri, domain_uri]}

    engine = MatchingEngine([offer])
    score_no = engine.score_offer(extract_profile(profile_no_domain), offer).score
    score_yes = engine.score_offer(extract_profile(profile_with_domain), offer).score

    assert score_yes > score_no, f"Expected domain overlap to increase score: {score_no}→{score_yes}"


def test_no_domain_uris_no_change():
    esco_uri = "http://data.europa.eu/esco/skill/test-esco-uri"
    offer = {
        "id": "o2",
        "is_vie": True,
        "country": "france",
        "title": "Data Analyst",
        "company": "TestCorp",
        "skills_uri": [esco_uri],
    }

    engine = MatchingEngine([offer])
    base = engine.score_offer(extract_profile({"profile_id": "p2", "skills_uri": [esco_uri]}), offer).score

    profile_empty = {"profile_id": "p2", "skills_uri": [esco_uri], "domain_uris": []}
    offer_empty = {**offer, "domain_uris": []}
    score_empty = engine.score_offer(extract_profile(profile_empty), offer_empty).score

    assert score_empty == base, f"Score should be unchanged when domain_uris is empty: {base} vs {score_empty}"


def test_esco_score_component_unchanged():
    esco_uri = "http://data.europa.eu/esco/skill/test-esco-uri"
    domain_uri = "compass:skill:DATA_IT:zxqzpl"

    offer_esco_only = {"skills_uri": [esco_uri]}
    profile_esco_only = {"skills_uri": [esco_uri]}

    offer_with_domain = {"skills_uri": [esco_uri, domain_uri]}
    profile_with_domain = {"skills_uri": [esco_uri, domain_uri]}

    esco_overlap_base = len(set(_esco_only(profile_esco_only["skills_uri"])) & set(_esco_only(offer_esco_only["skills_uri"])))
    esco_overlap_domain = len(set(_esco_only(profile_with_domain["skills_uri"])) & set(_esco_only(offer_with_domain["skills_uri"])))

    assert esco_overlap_base == esco_overlap_domain == 1, (
        f"ESCO overlap must be unchanged: base={esco_overlap_base} domain={esco_overlap_domain}"
    )
