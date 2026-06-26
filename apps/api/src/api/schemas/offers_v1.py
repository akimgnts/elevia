from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


DateLike = str | date | datetime | None


class _OffersV1BaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_serializer(
        "publication_date",
        "start_date",
        "first_seen_at",
        "last_seen_at",
        "started_at",
        "finished_at",
        when_used="always",
        check_fields=False,
    )
    def _serialize_date_like(self, value: DateLike) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)


class OfferSummaryResponse(_OffersV1BaseModel):
    id: int
    source: str
    external_id: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    country: str | None = None
    contract_type: str | None = None
    publication_date: DateLike = None
    start_date: DateLike = None
    url: str | None = None
    last_seen_at: DateLike = None


class RecentOffersResponse(_OffersV1BaseModel):
    offers: list[OfferSummaryResponse] = Field(default_factory=list)


class OfferDetailResponse(_OffersV1BaseModel):
    id: int
    source: str
    external_id: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    country: str | None = None
    contract_type: str | None = None
    description: str | None = None
    publication_date: DateLike = None
    start_date: DateLike = None
    salary: str | None = None
    url: str | None = None
    payload_json: dict[str, Any] = Field(default_factory=dict)
    first_seen_at: DateLike = None
    last_seen_at: DateLike = None
    is_active: bool = True
    domain_tag: str | None = None
    confidence: float | None = None
    method: str | None = None
    evidence: list[str] = Field(default_factory=list)
    needs_ai_review: bool | None = None
    job_family: str | None = None
    primary_function: str | None = None
    purity_score: float | None = None
    hybrid_score: float | None = None

    @field_validator("evidence", mode="before")
    @classmethod
    def _default_empty_evidence(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return value


class IngestionLatestResponse(_OffersV1BaseModel):
    id: int
    source: str
    started_at: DateLike = None
    finished_at: DateLike = None
    status: str
    fetched_count: int = 0
    persisted_count_raw: int = 0
    attempted_count_clean: int = 0
    persisted_count_clean: int = 0
    new_count: int = 0
    existing_count: int = 0
    missing_count: int = 0
    active_total: int = 0
    error: str | None = None
