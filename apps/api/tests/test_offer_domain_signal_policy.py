"""Offer domain tokens are filtered by cluster signal policy before URIs applied."""
from __future__ import annotations

import sys
from pathlib import Path

# ── Path setup ─────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).parent.parent
API_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(API_SRC))

from compass import offer_canonicalization as oc


class _StubLibrary:
    def get_active_skills_with_rarity(self, cluster):
        return {}


def test_offer_domain_tokens_filtered_in_apply(monkeypatch):
    # Force cluster
    monkeypatch.setattr(oc, "detect_offer_cluster", lambda *args, **kwargs: ("DATA_IT", None, None))

    # Return tokens/uris (domain_tokens are already normalized)
    def _fake_build_domain_uris_for_text(*args, **kwargs):
        return (
            ["machine learning", "paris", "bi"],
            ["uri:ml", "uri:paris", "uri:bi"],
        )

    monkeypatch.setattr(oc, "build_domain_uris_for_text", _fake_build_domain_uris_for_text)

    offer = {
        "id": "o1",
        "title": "Data role",
        "description": "",
        "skills": [],
        "skills_uri": [],
        "skills_display": [],
    }

    oc._apply_domain_uris(offer, library=_StubLibrary())

    assert "uri:paris" not in offer.get("domain_uris", [])
    assert "uri:ml" in offer.get("domain_uris", [])
    assert "uri:bi" in offer.get("domain_uris", [])
