import json


def test_normalize_business_france_offer_maps_search_payload_to_raw_shape():
    from api.utils.business_france_raw_scraper import normalize_business_france_offer

    payload = {
        "id": 242553,
        "missionTitle": "Coordinateur Opérations Industrielles (H/F)",
        "organizationName": "REVALOREM",
        "cityName": "LANCASTER  -PA-",
        "countryName": "ETATS-UNIS",
        "missionType": "VIE",
        "creationDate": "2026-04-23T14:34:38Z",
        "missionStartDate": "2026-09-01T00:00:00",
        "missionDescription": "Industrial coordination",
        "reference": "VIE242553",
    }

    row = normalize_business_france_offer(payload)

    assert row["id"] == 242553
    assert row["title"] == "Coordinateur Opérations Industrielles (H/F)"
    assert row["company"] == "REVALOREM"
    assert row["city"] == "LANCASTER  -PA-"
    assert row["cityName"] == "LANCASTER  -PA-"
    assert row["country"] == "ETATS-UNIS"
    assert row["countryName"] == "ETATS-UNIS"
    assert row["missionType"] == "VIE"
    assert row["publicationDate"] == "2026-04-23T14:34:38Z"
    assert row["startDate"] == "2026-09-01T00:00:00"
    assert row["description"] == "Industrial coordination"
    assert row["offerUrl"] == "https://mon-vie-via.businessfrance.fr/offres/242553"
    assert row["is_vie"] is True
    assert row["bf_source"] == "BF_AZURE_SEARCH"


def test_scrape_business_france_raw_offers_fetches_pages_and_persists(monkeypatch):
    from api.utils import business_france_raw_scraper as scraper

    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeSession:
        def post(self, url, json=None, timeout=None):
            calls.append({"url": url, "json": dict(json or {}), "timeout": timeout})
            skip = int((json or {}).get("skip") or 0)
            limit = int((json or {}).get("limit") or 0)
            items = []
            if skip == 0:
                items = [
                    {
                        "id": 242553,
                        "missionTitle": "Offer 1",
                        "organizationName": "Org 1",
                        "cityName": "PARIS",
                        "countryName": "FRANCE",
                        "missionType": "VIE",
                        "creationDate": "2026-04-23T14:34:38Z",
                        "missionStartDate": "2026-09-01T00:00:00",
                    },
                    {
                        "id": 242552,
                        "missionTitle": "Offer 2",
                        "organizationName": "Org 2",
                        "cityName": "MADRID",
                        "countryName": "ESPAGNE",
                        "missionType": "VIA",
                        "creationDate": "2026-04-23T14:20:00Z",
                        "missionStartDate": "2026-10-01T00:00:00",
                    },
                ][:limit]
            elif skip == 2:
                items = [
                    {
                        "id": 242551,
                        "missionTitle": "Offer 3",
                        "organizationName": "Org 3",
                        "cityName": "BERLIN",
                        "countryName": "ALLEMAGNE",
                        "missionType": "VIE",
                        "creationDate": "2026-04-23T14:10:00Z",
                        "missionStartDate": "2026-11-01T00:00:00",
                    }
                ][:limit]
            return FakeResponse({"count": 3, "result": items})

    persisted = {}

    def fake_persist_raw_offers(source, offers, scraped_at, database_url=None):
        persisted["source"] = source
        persisted["offers"] = [dict(offer) for offer in offers]
        persisted["scraped_at"] = scraped_at
        persisted["database_url"] = database_url
        return scraper.PersistResult(attempted=len(persisted["offers"]), persisted=len(persisted["offers"]))

    monkeypatch.setattr(scraper, "persist_raw_offers", fake_persist_raw_offers)

    result = scraper.scrape_business_france_raw_offers(
        session=FakeSession(),
        limit=3,
        batch_size=2,
        timeout=15,
        database_url="postgresql://example",
    )

    assert result.fetched == 3
    assert result.persisted == 3
    assert result.total_count == 3
    assert persisted["source"] == "business_france"
    assert len(persisted["offers"]) == 3
    assert persisted["offers"][0]["offerUrl"] == "https://mon-vie-via.businessfrance.fr/offres/242553"
    assert persisted["offers"][1]["is_vie"] is False
    assert calls == [
        {
            "url": "https://civiweb-api-prd.azurewebsites.net/api/Offers/search",
            "json": {"skip": 0, "limit": 2},
            "timeout": 15,
        },
        {
            "url": "https://civiweb-api-prd.azurewebsites.net/api/Offers/search",
            "json": {"skip": 2, "limit": 1},
            "timeout": 15,
        },
    ]
