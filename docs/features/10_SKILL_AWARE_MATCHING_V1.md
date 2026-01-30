# Skill-Aware Matching V1

## Why
Stop “fake confidence” scores caused by missing offer skills.  
If an offer has no skills available, scoring is marked partial and capped.

## Storage (additive)
New table: `fact_offer_skills`

Columns:
- `offer_id` (TEXT, PK part)
- `skill` (TEXT, normalized label, PK part)
- `source` (TEXT: `france_travail` | `rome` | `esco` | `manual`)
- `confidence` (REAL, optional)
- `created_at` (TEXT, UTC ISO)

Index:
- `idx_fact_offer_skills_offer_id`

## Ingestion / Backfill Flow
1) Ingestion (run_ingestion / ingest_pipeline / ingest_business_france):
   - Extract skills from payload:
     - FT: `competences` if present, else text fallback (title/description)
     - BF: text fallback (title/description)
   - Insert into `fact_offer_skills` (idempotent, `INSERT OR IGNORE`)
   - If ROME link exists, add up to 3 ROME competences as skills (`source=rome`)

2) Backfill (no network):
   - Script: `apps/api/scripts/backfill_offer_skills.py`
   - Reads `fact_offers` + `offer_rome_link` + ROME competences tables
   - Inserts missing skills into `fact_offer_skills`

## Matching Guardrail
If `offer.skills` is empty:
- `score_is_partial = true`
- score is capped to 30 (max of non-skill signals)
- reason includes “Compétences indisponibles pour cette offre”

## How to run backfill
```bash
cd apps/api
./.venv/bin/python scripts/backfill_offer_skills.py
```

## Acceptance Tests
- Offer skills table created
- Batch attach of skills to offers
- Partial scoring when offer skills missing
- Normal scoring when offer skills present
- Backfill is idempotent and does not alter `fact_offers`
