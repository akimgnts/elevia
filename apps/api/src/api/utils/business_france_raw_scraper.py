"""
Minimal Business France scraper path for raw_offers ingestion.

Scope:
- source = business_france
- fetches current public search dataset from Business France Azure API
- writes only to raw_offers via existing idempotent upsert layer
- no scoring, no matching, no clean_offers logic
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

import requests

from api.utils.raw_offers_pg import PersistResult, persist_raw_offers


BUSINESS_FRANCE_SOURCE = "business_france"
BUSINESS_FRANCE_API_BASE = "https://civiweb-api-prd.azurewebsites.net"
BUSINESS_FRANCE_SEARCH_PATH = "/api/Offers/search"
BUSINESS_FRANCE_SITE_BASE = "https://mon-vie-via.businessfrance.fr"


@dataclass
class BusinessFranceScrapeResult:
    fetched: int
    persisted: int
    total_count: int
    error: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_business_france_offer(payload: Mapping[str, Any]) -> dict[str, Any]:
    offer_id = payload.get("id")
    mission_type = (payload.get("missionType") or "").strip().upper()
    offer_url = (
        payload.get("offerUrl")
        or payload.get("contactURL")
        or (f"{BUSINESS_FRANCE_SITE_BASE}/offres/{offer_id}" if offer_id is not None else None)
    )

    normalized = dict(payload)
    normalized["bf_source"] = "BF_AZURE_SEARCH"
    normalized["title"] = payload.get("title") or payload.get("missionTitle")
    normalized["company"] = payload.get("company") or payload.get("organizationName")
    normalized["city"] = payload.get("city") or payload.get("cityName")
    normalized["cityName"] = payload.get("cityName") or payload.get("city")
    normalized["country"] = payload.get("country") or payload.get("countryName")
    normalized["countryName"] = payload.get("countryName") or payload.get("country")
    normalized["description"] = payload.get("description") or payload.get("missionDescription")
    normalized["publicationDate"] = (
        payload.get("publicationDate")
        or payload.get("creationDate")
        or payload.get("startBroadcastDate")
    )
    normalized["startDate"] = payload.get("startDate") or payload.get("missionStartDate")
    normalized["offerUrl"] = offer_url
    normalized["is_vie"] = payload.get("is_vie") if isinstance(payload.get("is_vie"), bool) else (mission_type == "VIE")
    return normalized


def fetch_business_france_search_page(
    *,
    skip: int,
    limit: int,
    session: requests.Session | Any | None = None,
    timeout: int = 30,
    api_base: str = BUSINESS_FRANCE_API_BASE,
) -> tuple[list[dict[str, Any]], int]:
    http = session or requests.Session()
    response = http.post(
        f"{api_base.rstrip('/')}{BUSINESS_FRANCE_SEARCH_PATH}",
        json={"skip": skip, "limit": limit},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get("result")
    total = payload.get("count")
    return [dict(item) for item in items or []], int(total or 0)


def scrape_business_france_raw_offers(
    *,
    limit: int | None = None,
    batch_size: int = 100,
    timeout: int = 30,
    session: requests.Session | Any | None = None,
    api_base: str = BUSINESS_FRANCE_API_BASE,
    database_url: str | None = None,
    dry_run: bool = False,
) -> BusinessFranceScrapeResult:
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")
    if limit is not None and limit < 0:
        raise ValueError("limit must be >= 0")

    fetched_rows: list[dict[str, Any]] = []
    skip = 0
    total_count = 0

    while True:
        remaining = None if limit is None else max(limit - len(fetched_rows), 0)
        if remaining == 0:
            break

        page_limit = batch_size if remaining is None else min(batch_size, remaining)
        page_items, total_count = fetch_business_france_search_page(
            skip=skip,
            limit=page_limit,
            session=session,
            timeout=timeout,
            api_base=api_base,
        )
        if not page_items:
            break

        fetched_rows.extend(normalize_business_france_offer(item) for item in page_items)
        skip += len(page_items)

        if len(page_items) < page_limit:
            break

    if dry_run:
        return BusinessFranceScrapeResult(
            fetched=len(fetched_rows),
            persisted=0,
            total_count=total_count,
            error=None,
        )

    persist_result = persist_raw_offers(
        BUSINESS_FRANCE_SOURCE,
        fetched_rows,
        _utc_now(),
        database_url=database_url,
    )
    return BusinessFranceScrapeResult(
        fetched=len(fetched_rows),
        persisted=persist_result.persisted,
        total_count=total_count,
        error=persist_result.error,
    )
