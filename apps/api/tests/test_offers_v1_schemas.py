from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.schemas.offers_v1 import (
    IngestionLatestResponse,
    OfferDetailResponse,
    OfferSummaryResponse,
    RecentOffersResponse,
)


def test_recent_offers_response_serializes_expected_shape():
    payload = RecentOffersResponse(
        offers=[
            OfferSummaryResponse(
                id=42,
                source="business_france",
                external_id="BF-42",
                title="Data Analyst",
                company="Acme",
                location="Berlin",
                country="Germany",
                contract_type="VIE",
                publication_date="2026-06-21T00:00:00+00:00",
                start_date="2026-09-01",
                url="https://example.test/offers/42",
                last_seen_at="2026-06-25T09:30:00+00:00",
            )
        ]
    )

    data = payload.model_dump()

    assert data["offers"][0]["external_id"] == "BF-42"
    assert data["offers"][0]["country"] == "Germany"
    json.dumps(data)


def test_offer_detail_response_accepts_real_enrichment_fields():
    payload = OfferDetailResponse(
        id=42,
        source="business_france",
        external_id="BF-42",
        title="Data Analyst",
        company="Acme",
        location="Berlin",
        country="Germany",
        contract_type="VIE",
        description="Build dashboards",
        publication_date="2026-06-21T00:00:00+00:00",
        start_date="2026-09-01",
        salary="2500 EUR",
        url="https://example.test/offers/42",
        payload_json={"raw": True},
        first_seen_at="2026-06-20T09:30:00+00:00",
        last_seen_at="2026-06-25T09:30:00+00:00",
        domain_tag="data",
        confidence=0.91,
        method="rules",
        evidence=["sql", "dashboard"],
        needs_ai_review=False,
        job_family="Data",
        primary_function="Analytics",
        purity_score=0.82,
        hybrid_score=0.18,
    )

    data = payload.model_dump()

    assert data["domain_tag"] == "data"
    assert data["method"] == "rules"
    assert data["needs_ai_review"] is False
    assert data["payload_json"] == {"raw": True}


def test_offer_detail_response_defaults_evidence_to_empty_list_for_unenriched_offer():
    payload = OfferDetailResponse(
        id=43,
        source="business_france",
        external_id="BF-43",
        title="Generalist",
        evidence=[],
    )

    data = payload.model_dump()

    assert data["evidence"] == []


def test_schema_serializers_handle_real_date_and_datetime_objects():
    payload = RecentOffersResponse(
        offers=[
            OfferSummaryResponse(
                id=44,
                source="business_france",
                external_id="BF-44",
                publication_date=datetime(2026, 6, 21, 8, 30, tzinfo=timezone.utc),
                start_date=date(2026, 9, 1),
                last_seen_at=datetime(2026, 6, 25, 9, 30, tzinfo=timezone.utc),
            )
        ]
    )

    data = payload.model_dump()

    assert data["offers"][0]["publication_date"] == "2026-06-21T08:30:00+00:00"
    assert data["offers"][0]["start_date"] == "2026-09-01"
    assert data["offers"][0]["last_seen_at"] == "2026-06-25T09:30:00+00:00"


def test_ingestion_latest_response_serializes_counters_and_timestamps():
    payload = IngestionLatestResponse(
        id=7,
        source="business_france",
        started_at=datetime(2026, 6, 25, 8, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 6, 25, 8, 3, tzinfo=timezone.utc),
        status="success",
        fetched_count=10,
        persisted_count_raw=10,
        attempted_count_clean=10,
        persisted_count_clean=9,
        new_count=4,
        existing_count=5,
        missing_count=1,
        active_total=123,
        error=None,
    )

    data = payload.model_dump()

    assert data["status"] == "success"
    assert data["started_at"] == "2026-06-25T08:00:00+00:00"
    assert data["active_total"] == 123
    json.dumps(data)
