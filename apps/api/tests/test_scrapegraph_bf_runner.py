import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT / "scripts"))

import scrapegraph_bf_runner as runner  # noqa: E402


def test_extract_external_id_prefers_explicit_id_fields():
    assert runner._extract_external_id({"external_id": "242553"}) == "242553"
    assert runner._extract_external_id({"id": 242553}) == "242553"
    assert runner._extract_external_id({"reference": "VIE242553"}) == "VIE242553"


def test_extract_external_id_falls_back_to_url_tail():
    item = {"offer_url": "https://mon-vie-via.businessfrance.fr/offres/242999"}
    assert runner._extract_external_id(item) == "242999"


def test_extract_external_id_returns_none_when_nothing_usable():
    assert runner._extract_external_id({"title": "Offre sans identifiant"}) is None


def test_normalize_result_drops_items_without_id_never_invents_one():
    raw = {
        "offers": [
            {"title": "Offer with id", "external_id": "111"},
            {"title": "Offer without any id or url"},
        ]
    }
    cleaned = runner._normalize_result(raw, limit=10)

    assert len(cleaned) == 1
    assert cleaned[0]["external_id"] == "111"


def test_normalize_result_handles_bare_list_result():
    raw = [{"external_id": "1"}, {"external_id": "2"}]
    cleaned = runner._normalize_result(raw, limit=10)
    assert [o["external_id"] for o in cleaned] == ["1", "2"]


def test_normalize_result_respects_limit():
    raw = {"offers": [{"external_id": str(i)} for i in range(20)]}
    cleaned = runner._normalize_result(raw, limit=5)
    assert len(cleaned) == 5
