# ROME Offer Link (Read-Only Enrichment)

## Purpose

Links France Travail offers to their ROME métier classification.
This is a **read-only enrichment layer** — it does not modify offers, scoring, or matching.

## Tables used

| Table | Role |
|-------|------|
| `fact_offers` | **Read only** — source of FT offer payloads |
| `dim_rome_metier` | **Read only** — validates ROME codes (populated by `ingest_rome.py`) |
| `offer_rome_link` | **Write** — stores the offer → ROME link |

### offer_rome_link schema

| Column | Type | Description |
|--------|------|-------------|
| `offer_id` | TEXT PK | References fact_offers.id |
| `rome_code` | TEXT NULL | Extracted ROME code (e.g. `M1607`), NULL if not found |
| `rome_label` | TEXT NULL | Label from dim_rome_metier or payload fallback |
| `linked_at` | TEXT NOT NULL | ISO timestamp of last enrichment |

## How to run

```bash
cd apps/api
python3 scripts/enrich_offers_with_rome.py
```

No environment variables needed — this is a local DB-only job.

### Prerequisites

- `data/db/offers.db` must exist with `fact_offers` populated
- For validated labels, run `ingest_rome.py` first to populate `dim_rome_metier`
- If `dim_rome_metier` is empty, codes are still extracted but labels come from the payload

## Extraction logic

From each France Travail offer's `payload_json`:
1. Check `romeCode` key (primary), then `codeRome` (fallback)
2. Validate format: `^[A-Z]\d{4}$`
3. If valid and exists in `dim_rome_metier` → use label from referential
4. If valid but not in referential → use `romeLibelle` from payload
5. If not found or invalid → `rome_code = NULL`

Every FT offer gets a row in `offer_rome_link` (explicit NULL = processed but no code).

## What it does NOT do

- Does not modify `fact_offers`
- Does not change matching scores or inbox results
- Does not call any external API
- Does not process Business France offers (FT only)

## Inbox exposure (read-only)

`POST /inbox` now includes an optional `rome` field on each item:

```json
{
  "rome": {
    "rome_code": "M1607",
    "rome_label": "Conseiller en emploi"
  }
}
```

- Only populated for France Travail offers when a valid link exists in `offer_rome_link`
- `rome` is `null` for Business France offers or missing links
- This does not affect scoring or decision logic
