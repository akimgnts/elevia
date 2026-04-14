from __future__ import annotations

from pathlib import Path

import pytest

from agent_demo.data_loader import (
    OFFERS_DB_PATH,
    OfferDataUnavailable,
    format_offer_for_prompt,
    get_latest_offer,
    list_offers,
    load_candidate_text,
    resolve_offer,
)


def test_list_offers_reads_real_repo_data() -> None:
    offers = list_offers(limit=3)
    assert OFFERS_DB_PATH.exists()
    assert len(offers) >= 1
    assert offers[0].id.startswith("BF-")
    assert offers[0].title
    assert offers[0].description


def test_format_offer_for_prompt_contains_core_fields() -> None:
    offer = get_latest_offer()
    assert offer is not None
    rendered = format_offer_for_prompt(offer)
    assert offer.id in rendered
    assert offer.title in rendered
    assert offer.company in rendered
    assert "Mission description:" in rendered or "Description:" in rendered


def test_resolve_offer_raises_cleanly_when_db_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from agent_demo import data_loader

    monkeypatch.setattr(data_loader, "OFFERS_DB_PATH", tmp_path / "missing.db")
    with pytest.raises(OfferDataUnavailable):
        data_loader.resolve_offer()


def test_load_candidate_text_rejects_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.txt"
    path.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_candidate_text(path)
