from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient

from api.main import app
from api.routes import inbox as inbox_routes
from api.routes import offers as offers_routes
from compass.scoring.scoring_v2 import build_scoring_v2


def _profile(**overrides):
    payload = {
        "dominant_role_block": "finance_ops",
        "secondary_role_blocks": ["business_analysis"],
        "dominant_domains": ["finance", "data"],
        "top_profile_signals": ["reporting", "audit", "analyse financiere", "sql"],
    }
    payload.update(overrides)
    return payload


def _offer(**overrides):
    payload = {
        "dominant_role_block": "finance_ops",
        "secondary_role_blocks": ["business_analysis"],
        "dominant_domains": ["finance"],
        "top_offer_signals": ["reporting", "audit", "budget"],
        "required_skills": ["reporting", "audit", "vba", "modelisation financiere"],
    }
    payload.update(overrides)
    return payload


def _semantic(**overrides):
    payload = {
        "role_alignment": {
            "profile_role": "finance_ops",
            "offer_role": "finance_ops",
            "alignment": "high",
        },
        "domain_alignment": {
            "shared_domains": ["finance"],
            "profile_only_domains": ["data"],
            "offer_only_domains": [],
        },
        "signal_alignment": {
            "matched_signals": ["reporting", "audit"],
            "missing_core_signals": [],
        },
        "alignment_summary": "Ton profil et ce poste sont alignes sur la finance.",
    }
    payload.update(overrides)
    return payload


def test_same_role_and_same_domain_yields_high_score():
    result = build_scoring_v2(
        profile_intelligence=_profile(),
        offer_intelligence=_offer(),
        semantic_explainability=_semantic(),
        matching_score=82,
    )

    assert result is not None
    assert result["components"]["role_alignment"] == 1.0
    assert result["components"]["domain_alignment"] == 1.0
    assert result["score"] >= 0.84
    assert result["score_pct"] >= 84


def test_same_role_and_domain_mismatch_yields_medium_score():
    result = build_scoring_v2(
        profile_intelligence=_profile(dominant_domains=["finance"]),
        offer_intelligence=_offer(dominant_domains=["marketing"]),
        semantic_explainability=_semantic(
            domain_alignment={
                "shared_domains": [],
                "profile_only_domains": ["finance"],
                "offer_only_domains": ["marketing"],
            }
        ),
        matching_score=82,
    )

    assert result is not None
    assert result["components"]["role_alignment"] == 1.0
    assert result["components"]["domain_alignment"] == 0.1
    assert 0.55 <= result["score"] <= 0.7


def test_different_role_yields_low_score():
    result = build_scoring_v2(
        profile_intelligence=_profile(
            dominant_role_block="supply_chain_ops",
            secondary_role_blocks=["project_ops"],
            dominant_domains=["supply_chain"],
        ),
        offer_intelligence=_offer(
            dominant_role_block="finance_ops",
            secondary_role_blocks=["business_analysis"],
            dominant_domains=["finance"],
        ),
        semantic_explainability=_semantic(
            role_alignment={
                "profile_role": "supply_chain_ops",
                "offer_role": "finance_ops",
                "alignment": "low",
            },
            domain_alignment={
                "shared_domains": [],
                "profile_only_domains": ["supply_chain"],
                "offer_only_domains": ["finance"],
            },
        ),
        matching_score=82,
    )

    assert result is not None
    assert result["components"]["role_alignment"] == 0.2
    assert result["components"]["domain_alignment"] == 0.1
    assert result["score"] < 0.4


def test_strong_gaps_reduce_score_even_with_high_matching_base():
    no_gap = build_scoring_v2(
        profile_intelligence=_profile(),
        offer_intelligence=_offer(),
        semantic_explainability=_semantic(),
        matching_score=95,
    )
    with_gap = build_scoring_v2(
        profile_intelligence=_profile(),
        offer_intelligence=_offer(),
        semantic_explainability=_semantic(
            signal_alignment={
                "matched_signals": ["reporting"],
                "missing_core_signals": ["audit", "vba", "modelisation financiere"],
            }
        ),
        matching_score=95,
    )

    assert no_gap is not None and with_gap is not None
    assert with_gap["components"]["gap_penalty"] > 0.0
    assert with_gap["score"] < no_gap["score"]


def test_payloads_remain_backward_compatible_and_expose_scoring_v2(monkeypatch, tmp_path):
    client = TestClient(app)
    offer = {
        "title": "VIE - Finance - LVMH Allemagne",
        "description": """
        Missions principales :
        - Produire des analyses et reportings réguliers
        Profil recherché :
        - Compétences : comptabilité, audit, Excel, modélisation financière
        """,
        "skills": ["comptabilité", "audit", "Excel", "modélisation financière", "reporting"],
        "skills_display": [{"label": "comptabilité"}, {"label": "audit"}, {"label": "Excel"}],
        "id": "offer-finance-1",
        "source": "business_france",
        "company": "LVMH",
        "country": "Allemagne",
        "city": "Frankfurt",
        "publication_date": "2026-03-20",
    }
    monkeypatch.setattr(inbox_routes, "load_catalog_offers", lambda: [offer])
    monkeypatch.setattr(inbox_routes, "load_catalog_offers_filtered", lambda **kwargs: [offer])
    monkeypatch.setattr(inbox_routes, "count_catalog_offers_filtered", lambda **kwargs: 1)

    inbox_resp = client.post(
        "/inbox",
        json={
            "profile_id": "scoring-v2",
            "profile": {
                "skills": ["audit", "excel", "reporting"],
                "profile_intelligence": {
                    "dominant_role_block": "finance_ops",
                    "secondary_role_blocks": ["business_analysis"],
                    "dominant_domains": ["finance"],
                    "top_profile_signals": ["audit", "reporting", "excel"],
                    "profile_summary": "Profil orienté finance opérationnelle.",
                },
            },
            "min_score": 0,
            "limit": 1,
        },
    )

    assert inbox_resp.status_code == 200
    item = inbox_resp.json()["items"][0]
    assert item["score"] >= 0
    assert item["explanation"]["summary_reason"]
    assert item["semantic_explainability"]["role_alignment"]["alignment"] == "high"
    assert item["scoring_v2"]["score_pct"] >= 0
    assert item["scoring_v2"]["components"]["matching_base"] == item["score"] / 100.0

    db_path = tmp_path / "offers.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE fact_offers (
            id TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            description TEXT,
            company TEXT,
            city TEXT,
            country TEXT,
            publication_date TEXT,
            contract_duration INTEGER,
            start_date TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE fact_offer_skills (
            offer_id TEXT NOT NULL,
            skill TEXT NOT NULL,
            skill_uri TEXT,
            source TEXT NOT NULL,
            confidence REAL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (offer_id, skill)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO fact_offers (id, source, title, description, company, city, country, publication_date, contract_duration, start_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "offer-finance-1",
            "business_france",
            "VIE - Finance - LVMH Allemagne",
            "Produire des analyses et reportings réguliers. Compétences : comptabilité, audit, Excel, modélisation financière.",
            "LVMH",
            "Frankfurt",
            "Allemagne",
            "2026-03-20",
            12,
            "2026-04-01",
        ),
    )
    conn.executemany(
        """
        INSERT INTO fact_offer_skills (offer_id, skill, skill_uri, source, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            ("offer-finance-1", "audit", None, "esco", 1.0, "2026-03-20T00:00:00Z"),
            ("offer-finance-1", "reporting", None, "esco", 1.0, "2026-03-20T00:00:00Z"),
            ("offer-finance-1", "Excel", None, "esco", 1.0, "2026-03-20T00:00:00Z"),
        ],
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(offers_routes, "DB_PATH", db_path)
    detail_resp = client.get(
        "/offers/offer-finance-1/detail",
        params=[
            ("profile_role_block", "finance_ops"),
            ("profile_secondary_role_blocks", "business_analysis"),
            ("profile_domains", "finance"),
            ("profile_signals", "audit"),
            ("profile_signals", "reporting"),
            ("profile_summary", "Profil orienté finance opérationnelle."),
            ("matching_score", "84"),
        ],
    )

    assert detail_resp.status_code == 200
    body = detail_resp.json()
    assert body["offer_intelligence"]["dominant_role_block"] == "finance_ops"
    assert body["semantic_explainability"]["role_alignment"]["alignment"] == "high"
    assert body["scoring_v2"]["score_pct"] >= 0
    assert "description_structured" in body
