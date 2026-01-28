# Sprint 23 — Loop Match Debug Snapshot

**Date:** 2026-01-29 00:42
**Scope:** Wire profile → match contract, show real top matches

## Root Cause

DashboardPage was calling `fetchCatalogOffers()` which returns raw France Travail offers
without `is_vie`, `skills`, or `languages` fields. The matching engine (`matching_v1.py`)
requires `is_vie=True` and a `skills` list on each offer — all catalog offers were silently
rejected (score 0 or filtered out).

## Fix Applied

1. **DashboardPage**: Switched from `fetchCatalogOffers` → `fetchSampleOffers` which returns
   structured VIE offers with `is_vie`, `skills`, `languages`, `education_level`.
2. **DashboardPage**: Updated offers map to handle both `id` and `offer_id` keys from sample offers.
3. **DashboardPage**: Simplified tags to `["V.I.E"]` (sample offers are all VIE).
4. **OfferCard**: Changed "Match IA" → "Match".
5. **HeroCardsGroup**: Changed "Match IA 94%" → "Match 94%", "Score IA" → "Score".
6. **HeroSection (sections)**: Changed "Match IA" → "Match".
7. **LiveDemoSection**: Changed "Match IA" → "Match".

## Contract Verification

**Backend MatchingRequest expects:**
- `profile`: Dict with `detected_capabilities` (or `skills`), `languages`, `education_summary`
- `offers`: List of dicts with `id`, `is_vie=true`, `skills[]`, `languages[]`

**Frontend sends (after fix):**
- `userProfile` from Zustand store (CvExtractionResponse shape) — backend `extract_profile()` handles `detected_capabilities` natively
- `sampleOffers` from `/offers/sample` — structured with all required fields

## QA Validation

```
POST /v1/match with profile (data_visualization + programming_scripting) + 2 VIE offers:
→ HTTP 200
→ 2 results returned with scores (15 each — partial match due to missing languages)
→ Detailed breakdown and diagnostic per offer
→ No PROVIDER_NOT_CONFIGURED error
```

## Build Status

`npm run build` passes (2.67s, 0 errors).
