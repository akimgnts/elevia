import json

import pytest


def test_normalize_fallback_offer_maps_scrapegraph_fields_to_raw_shape():
    from api.utils.business_france_scrape_fallback import _normalize_fallback_offer

    item = {
        "external_id": "242553",
        "title": "Coordinateur Opérations Industrielles (H/F)",
        "company": "REVALOREM",
        "location": "New York, États-Unis",
        "description": "Industrial coordination mission.",
        "profile": "Bac+5 ingénieur",
        "publication_date": "2026-08-01",
        "offer_url": "https://mon-vie-via.businessfrance.fr/offres/242553",
    }

    row = _normalize_fallback_offer(item)

    assert row["id"] == "242553"
    assert row["title"] == "Coordinateur Opérations Industrielles (H/F)"
    assert row["company"] == "REVALOREM"
    assert row["city"] == "New York, États-Unis"
    assert row["description"] == "Industrial coordination mission."
    assert row["profile"] == "Bac+5 ingénieur"
    assert row["publicationDate"] == "2026-08-01"
    assert row["offerUrl"] == "https://mon-vie-via.businessfrance.fr/offres/242553"
    assert row["bf_source"] == "BF_SCRAPEGRAPH_FALLBACK"


def test_normalize_fallback_offer_derives_id_from_url_when_no_explicit_id():
    from api.utils.business_france_scrape_fallback import _normalize_fallback_offer

    item = {"title": "VIE Data Analyst", "offer_url": "https://mon-vie-via.businessfrance.fr/offres/242999"}
    row = _normalize_fallback_offer(item)

    assert row["id"] == "242999"


def test_normalize_fallback_offer_never_invents_an_id():
    from api.utils.business_france_scrape_fallback import _normalize_fallback_offer

    item = {"title": "Offre sans identifiant ni URL"}
    row = _normalize_fallback_offer(item)

    assert row["id"] is None


def test_is_fallback_available_false_when_venv_missing(monkeypatch, tmp_path):
    from api.utils import business_france_scrape_fallback as fb

    monkeypatch.setenv(fb.ENV_FALLBACK_VENV_PYTHON, str(tmp_path / "does-not-exist" / "python"))
    assert fb.is_fallback_available() is False


def test_scrape_business_france_offers_unavailable_when_venv_missing(monkeypatch, tmp_path):
    from api.utils import business_france_scrape_fallback as fb

    monkeypatch.setenv(fb.ENV_FALLBACK_VENV_PYTHON, str(tmp_path / "missing-python"))
    result = fb.scrape_business_france_offers(limit=5)

    assert result.status == "unavailable"
    assert result.offers == []


def test_scrape_business_france_offers_parses_runner_success(monkeypatch, tmp_path):
    from api.utils import business_france_scrape_fallback as fb

    fake_python = tmp_path / "python"
    fake_python.write_text("#!/bin/sh\n")
    fake_python.chmod(0o755)
    monkeypatch.setenv(fb.ENV_FALLBACK_VENV_PYTHON, str(fake_python))
    monkeypatch.setattr(fb, "RUNNER_SCRIPT", tmp_path / "runner.py")
    fb.RUNNER_SCRIPT.write_text("# fake runner\n")

    runner_output = {
        "status": "success",
        "engine": "scrapegraph",
        "page_used": "https://mon-vie-via.businessfrance.fr/offres",
        "offers": [
            {"external_id": "111", "title": "Offer A", "offer_url": "https://mon-vie-via.businessfrance.fr/offres/111"},
            {"external_id": "112", "title": "Offer B", "offer_url": "https://mon-vie-via.businessfrance.fr/offres/112"},
            {"title": "Offer without id"},  # must be dropped
        ],
        "offers_found": 3,
        "error": None,
    }

    class FakeCompleted:
        stdout = json.dumps(runner_output) + "\n"
        stderr = ""

    captured_cmd = {}

    def fake_run(cmd, **kwargs):
        captured_cmd["cmd"] = cmd
        return FakeCompleted()

    monkeypatch.setattr(fb.subprocess, "run", fake_run)

    result = fb.scrape_business_france_offers(limit=5)

    assert result.status == "success"
    assert result.offers_recovered == 2
    assert [o["id"] for o in result.offers] == ["111", "112"]
    assert all(o["bf_source"] == "BF_SCRAPEGRAPH_FALLBACK" for o in result.offers)
    assert str(fb.RUNNER_SCRIPT) in captured_cmd["cmd"]


def test_scrape_business_france_offers_dedupes_by_id(monkeypatch, tmp_path):
    from api.utils import business_france_scrape_fallback as fb

    fake_python = tmp_path / "python"
    fake_python.write_text("#!/bin/sh\n")
    fake_python.chmod(0o755)
    monkeypatch.setenv(fb.ENV_FALLBACK_VENV_PYTHON, str(fake_python))
    monkeypatch.setattr(fb, "RUNNER_SCRIPT", tmp_path / "runner.py")
    fb.RUNNER_SCRIPT.write_text("# fake runner\n")

    runner_output = {
        "status": "success",
        "offers": [
            {"external_id": "111", "title": "Offer A (page 1)"},
            {"external_id": "111", "title": "Offer A (duplicate)"},
        ],
        "page_used": "https://mon-vie-via.businessfrance.fr/offres",
        "error": None,
    }

    class FakeCompleted:
        stdout = json.dumps(runner_output) + "\n"
        stderr = ""

    monkeypatch.setattr(fb.subprocess, "run", lambda cmd, **kwargs: FakeCompleted())

    result = fb.scrape_business_france_offers(limit=5)

    assert result.offers_recovered == 1
    assert result.offers[0]["id"] == "111"


def test_scrape_business_france_offers_error_when_runner_fails(monkeypatch, tmp_path):
    from api.utils import business_france_scrape_fallback as fb

    fake_python = tmp_path / "python"
    fake_python.write_text("#!/bin/sh\n")
    fake_python.chmod(0o755)
    monkeypatch.setenv(fb.ENV_FALLBACK_VENV_PYTHON, str(fake_python))
    monkeypatch.setattr(fb, "RUNNER_SCRIPT", tmp_path / "runner.py")
    fb.RUNNER_SCRIPT.write_text("# fake runner\n")

    class FakeCompleted:
        stdout = ""
        stderr = "OPENAI_API_KEY is not set"

    monkeypatch.setattr(fb.subprocess, "run", lambda cmd, **kwargs: FakeCompleted())

    result = fb.scrape_business_france_offers(limit=5)

    assert result.status == "error"
    assert "OPENAI_API_KEY" in result.error
    assert result.offers == []
