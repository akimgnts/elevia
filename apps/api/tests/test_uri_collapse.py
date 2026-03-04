import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from esco.uri_collapse import collapse_to_uris
from matching.extractors import extract_profile
from compass.offer_canonicalization import _normalize_offer_skills_via_esco


def test_collapse_to_uris_dedupes_and_prefers_label():
    items = [
        {"surface": "excel", "esco_uri": "uri:1", "label": "Excel", "source": "direct"},
        {
            "surface": "microsoft office excel",
            "esco_uri": "uri:1",
            "esco_label": "Utiliser un logiciel de tableur",
            "source": "alias",
        },
        {"surface": "sql", "esco_uri": "uri:2", "esco_label": "SQL", "source": "direct"},
    ]

    collapsed = collapse_to_uris(items)
    assert collapsed["uris"] == ["uri:1", "uri:2"]
    assert collapsed["collapsed_dupes"] == 1
    assert collapsed["display"][0]["label"] == "Utiliser un logiciel de tableur"


def test_offer_uri_collapse_dedupes_surface_variants():
    offer = {
        "id": "o1",
        "title": "Test",
        "description": "",
        "skills": ["utiliser un logiciel de tableur", "microsoft office excel"],
    }
    normalized = _normalize_offer_skills_via_esco(offer)
    assert normalized["skills_uri_count"] == 1
    assert normalized["skills_uri_collapsed_dupes"] >= 1


def test_profile_uri_collapse_dedupes_surface_variants():
    profile = {
        "id": "p1",
        "skills": ["excel"],
        "languages": ["français"],
        "education": "bac+3",
    }
    extracted = extract_profile(profile)
    assert extracted.skills_uri_count == 1
    assert extracted.skills_uri_collapsed_dupes >= 1
