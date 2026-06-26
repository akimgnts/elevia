# Elevia Offers API V1 Design

Date: 2026-06-26
Status: approved for implementation

## Goal

Expose the online Elevia Business France data through a clean HTTP API in this repo, with PostgreSQL as the source of truth for offer reads.

This V1 is intentionally small. It gives external clients a stable way to:
- verify service freshness
- fetch the most recent offers
- fetch a single offer by id

## Scope

In scope:
- PostgreSQL-backed read path for `clean_offers`
- PostgreSQL-backed read path for `ingestion_runs`
- new read-only endpoints:
  - `GET /offers/recent`
  - `GET /offers/{id}`
  - `GET /ingestion/latest`
- lightweight PostgreSQL health signal in `GET /health`
- tests for repository and route behavior

Out of scope:
- replacing the entire historical `GET /offers/catalog` implementation
- SQL access for external projects
- auth / rate limiting
- search endpoint
- matching endpoint refactor

## Source Of Truth

Primary tables:
- `clean_offers` for Business France offer catalog
- `ingestion_runs` for pipeline freshness and status
- `offer_domain_enrichment` for additive offer intelligence on detail responses

V1 reads only active Business France offers unless explicitly asking for ingestion state.

## API Contract

### `GET /health`

Adds a PostgreSQL dependency summary without removing existing fields.

Response shape:
- `status`
- `service`
- `version`
- `request_id`
- `postgres`
  - `status`: `ok` or `error`
  - `latest_ingestion_at`: timestamp or null

Failure behavior:
- route still returns 200 if API is alive
- `postgres.status=error` when DB query fails

### `GET /offers/recent`

Returns the latest active Business France offers from `clean_offers`.

Query params:
- `limit` default 20, max 100
- `country` optional
- `source` default `business_france`

Sort order:
- `last_seen_at DESC`
- `publication_date DESC`
- `id DESC`

Response shape:
- `items`: list of `OfferSummary`
- `count`: number returned
- `source`: `business_france`
- `latest_last_seen_at`: max value in returned set or null

### `GET /offers/{id}`

Returns one Business France offer from `clean_offers` by numeric row id.

Response shape:
- base fields from `OfferSummary`
- long text fields (`description`, `payload_json` optional trimmed pass-through not required)
- additive intelligence when available:
  - `job_family`
  - `primary_function`
  - `purity_score`
  - `hybrid_score`
  - `needs_review`

Failure behavior:
- 404 when offer does not exist

### `GET /ingestion/latest`

Returns the latest Business France ingestion run.

Response shape:
- `source`
- `status`
- `started_at`
- `finished_at`
- `fetched_count`
- `persisted_count_raw`
- `attempted_count_clean`
- `persisted_count_clean`
- `new_count`
- `existing_count`
- `missing_count`
- `active_total`
- `error`

Failure behavior:
- 404 when no ingestion run exists

## Internal Design

### Repository layer

Add a small PostgreSQL repository module under `apps/api/src/api/repositories/`.

Responsibilities:
- open PostgreSQL connection from `DATABASE_URL`
- query latest ingestion
- query recent offers
- query single offer detail

No write behavior in V1.

### Schemas

Add a small schema module for these API responses instead of reusing the heavy inbox schemas.

Models:
- `OfferSummary`
- `OfferDetail`
- `RecentOffersResponse`
- `IngestionLatestResponse`
- `PostgresHealth`

### Routing

Keep current route organization.

- extend existing `offers` router for `recent` and `{id}`
- add a small `ingestion` router
- extend `health` router only enough to include Postgres dependency status

## Error Handling

- repository exceptions are logged and surfaced as 500 at route level
- missing offer or missing ingestion run return 404
- `GET /health` is fail-open and reports dependency degradation in payload instead of failing hard

## Testing

Minimum coverage:
- repository methods with mocked psycopg connection or route-level monkeypatching
- `GET /offers/recent` happy path
- `GET /offers/{id}` happy path and 404
- `GET /ingestion/latest` happy path and 404
- `GET /health` includes postgres block

## Rollout

1. add V1 endpoints without touching existing clients
2. verify locally with targeted pytest
3. deploy
4. point external project to these endpoints
