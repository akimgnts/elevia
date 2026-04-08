"""
Regression guard for heavy SQLite/CPU routes.

These endpoints must stay sync `def` so FastAPI runs them in the threadpool
instead of blocking the main event loop.
"""

from pathlib import Path


OFFERS = Path("apps/api/src/api/routes/offers.py").read_text(encoding="utf-8")
INBOX = Path("apps/api/src/api/routes/inbox.py").read_text(encoding="utf-8")


def test_offers_routes_use_threadpool_friendly_sync_defs():
    assert "def get_sample_offers(" in OFFERS
    assert "def get_catalog_offers(" in OFFERS
    assert "def get_offer_detail(" in OFFERS
    assert "async def get_catalog_offers(" not in OFFERS


def test_inbox_routes_use_threadpool_friendly_sync_defs():
    assert "def get_inbox(" in INBOX
    assert "def _get_inbox_filtered(" in INBOX
    assert "async def get_inbox(" not in INBOX
