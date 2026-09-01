import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT / "src"))
sys.path.insert(0, str(API_ROOT / "scripts"))

import scrape_business_france_azure as bf_azure  # noqa: E402
from api.utils.business_france_scrape_fallback import FallbackResult  # noqa: E402


def _fake_civiweb_offer(offer_id: int) -> dict:
    return {
        "id": offer_id,
        "missionTitle": f"Offer {offer_id}",
        "organizationName": "Org",
        "cityName": "Paris",
        "countryName": "France",
        "missionType": "VIE",
    }


def _run_main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["scrape_business_france_azure.py", *argv])
    with pytest.raises(SystemExit) as exc_info:
        bf_azure.main()
    return exc_info.value.code


def test_api_success_never_calls_fallback(monkeypatch):
    catalog = [_fake_civiweb_offer(i) for i in range(12)]
    monkeypatch.setattr(bf_azure, "fetch_catalog", lambda *a, **k: (catalog, 12))

    fallback_calls = []
    monkeypatch.setattr(bf_azure, "is_fallback_available", lambda: True)
    monkeypatch.setattr(
        bf_azure, "scrape_business_france_offers",
        lambda **kw: fallback_calls.append(kw) or FallbackResult(status="success", offers=[]),
    )

    code = _run_main(monkeypatch, ["--dry-run", "--skip-details"])

    assert code == 0
    assert fallback_calls == []  # fallback must never be invoked when the primary succeeds


def test_api_401_empty_catalog_triggers_fallback(monkeypatch):
    # fetch_catalog already swallows the HTTP 401 / non-JSON body internally
    # and returns an empty list — this is exactly the ingestion_runs id=144
    # production failure mode.
    monkeypatch.setattr(bf_azure, "fetch_catalog", lambda *a, **k: ([], 0))
    monkeypatch.setattr(bf_azure, "is_fallback_available", lambda: True)

    fallback_offers = [
        {"id": str(i), "title": f"Fallback offer {i}", "description": "", "company": "", "city": "",
         "country": "", "publicationDate": None, "offerUrl": None, "profile": "",
         "bf_source": "BF_SCRAPEGRAPH_FALLBACK"}
        for i in range(12)
    ]
    fallback_calls = []

    def fake_fallback(**kwargs):
        fallback_calls.append(kwargs)
        return FallbackResult(status="success", offers=fallback_offers, offers_recovered=len(fallback_offers))

    monkeypatch.setattr(bf_azure, "scrape_business_france_offers", fake_fallback)

    code = _run_main(monkeypatch, ["--dry-run", "--skip-details"])

    assert code == 0
    assert len(fallback_calls) == 1  # fallback triggered exactly once


def test_fallback_offers_reach_dry_run_unmutated_by_normalize_payload(monkeypatch):
    """bf_source must stay BF_SCRAPEGRAPH_FALLBACK — normalize_payload() must not run on fallback offers."""
    monkeypatch.setattr(bf_azure, "fetch_catalog", lambda *a, **k: ([], 0))
    monkeypatch.setattr(bf_azure, "is_fallback_available", lambda: True)

    fallback_offers = [
        {"id": str(i), "title": f"Offer {i}", "description": "", "company": "", "city": "",
         "country": "", "publicationDate": None, "offerUrl": None, "profile": "",
         "bf_source": "BF_SCRAPEGRAPH_FALLBACK"}
        for i in range(10)
    ]
    monkeypatch.setattr(
        bf_azure, "scrape_business_france_offers",
        lambda **kw: FallbackResult(status="success", offers=fallback_offers, offers_recovered=len(fallback_offers)),
    )

    captured = {}
    original_summary_log = bf_azure.StructuredLogger.log

    def capturing_log(self, step, status, **kwargs):
        if step == "dry_run":
            captured["offers_processed"] = kwargs.get("offers_processed")
        return original_summary_log(self, step, status, **kwargs)

    monkeypatch.setattr(bf_azure.StructuredLogger, "log", capturing_log)

    code = _run_main(monkeypatch, ["--dry-run", "--skip-details"])

    assert code == 0
    assert captured["offers_processed"] == 10


def test_api_and_fallback_both_fail_exits_cleanly(monkeypatch):
    monkeypatch.setattr(bf_azure, "fetch_catalog", lambda *a, **k: ([], 0))
    monkeypatch.setattr(bf_azure, "is_fallback_available", lambda: True)
    monkeypatch.setattr(
        bf_azure, "scrape_business_france_offers",
        lambda **kw: FallbackResult(status="error", offers=[], error="OPENAI_API_KEY is not set"),
    )

    persist_calls = []
    monkeypatch.setattr(bf_azure, "persist_raw_offers", lambda *a, **k: persist_calls.append(1))

    code = _run_main(monkeypatch, ["--dry-run", "--skip-details"])

    assert code == 1
    assert persist_calls == []  # never reaches persistence


def test_provider_api_never_triggers_fallback_even_on_empty_catalog(monkeypatch):
    monkeypatch.setattr(bf_azure, "fetch_catalog", lambda *a, **k: ([], 0))
    fallback_calls = []
    monkeypatch.setattr(
        bf_azure, "scrape_business_france_offers",
        lambda **kw: fallback_calls.append(kw) or FallbackResult(status="success", offers=[]),
    )

    code = _run_main(monkeypatch, ["--dry-run", "--skip-details", "--provider", "api"])

    assert code == 1
    assert fallback_calls == []
