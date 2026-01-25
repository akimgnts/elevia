# OfferNormalized (API Contract)

Sprint 15 - Data Quality & Source Filter
Sprint 15.1 - Hardened Contract + Error Semantics

## Response Envelope

All `/offers/catalog` responses are wrapped in:

```json
{
  "offers": [OfferNormalized, ...],
  "meta": {
    "total_available": number,
    "returned": number,
    "data_source": "live-db" | "static-fallback",
    "fallback_reason": string | null
  }
}
```

## OfferNormalized Keys

### Required keys (always present)

| Key | Type | Description |
|-----|------|-------------|
| `id` | `string` | Unique offer identifier |
| `source` | `"france_travail" \| "business_france" \| "unknown"` | Data source |
| `title` | `string` | Job title (cleaned text, may be empty) |
| `description` | `string` | Full description (cleaned text) |
| `display_description` | `string` | Truncated description for UI (max 800 chars) |
| `publication_date` | `string \| null` | ISO date string or null |

### Optional keys (nullable/empty allowed)

| Key | Type | Description |
|-----|------|-------------|
| `company` | `string \| null` | Company name |
| `city` | `string \| null` | City/location |
| `country` | `string \| null` | Country |
| `contract_duration` | `number \| null` | Duration in months |
| `start_date` | `string \| null` | Contract start date |

## Meta Fields

| Key | Type | Description |
|-----|------|-------------|
| `total_available` | `number` | Total offers matching filter in source |
| `returned` | `number` | Number of offers in this response |
| `data_source` | `string` | `"live-db"` or `"static-fallback"` |
| `fallback_reason` | `string \| null` | Why fallback occurred (null if live-db) |

### fallback_reason values

| Value | Meaning |
|-------|---------|
| `null` | No fallback - serving from live DB |
| `EMPTY_DB` | DB exists but query returned 0 rows |
| `DB_LOCKED` | SQLite database is locked |
| `DB_MISSING` | Database file not found |
| `DB_ERROR` | Other database error |

## Rules

1. **No fabricated values.** If unknown → `null` or empty string `""`.
2. **title/description** must be cleaned text:
   - No literal `\\n` sequences
   - Real newlines `\n` preserved if present
3. **display_description** is truncated/cleaned for UI (max 800 chars, ends with `…` if truncated).
4. **description** remains full cleaned text (not truncated).
5. **payload_json** is NOT returned by default in catalog endpoint.

## Source Filtering

Query param `source` accepts (via Enum validation):
- `all` (default) - returns all sources
- `france_travail` - FT offers only
- `business_france` - BF offers only

Invalid source → HTTP 422 (FastAPI Enum validation error)

## Headers

- `X-Data-Source: live-db` - serving from SQLite (mirrors `meta.data_source`)
- `X-Data-Source: static-fallback` - serving from sample JSON
