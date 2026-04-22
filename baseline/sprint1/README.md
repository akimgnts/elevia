# Sprint 1 — Local Matching Baseline

Frozen, reproducible baseline of the current product pipeline. Produced by
`run_baseline.py` against the fixed inputs under `inputs/`. Outputs under
`outputs/`. No scoring-core modification. No business-logic tuning.

## How to reproduce

```bash
python3 baseline/sprint1/run_baseline.py
```

The script is deterministic given the frozen `inputs/`.

## Entrypoints

| Role | Path |
|---|---|
| Profile extraction | `apps/api/src/matching/extractors.py::extract_profile` |
| Scoring engine (strict, threshold-filtered) | `apps/api/src/matching/matching_v1.py::MatchingEngine.match` |
| Scoring engine (unfiltered per-offer) | `apps/api/src/matching/matching_v1.py::MatchingEngine.score_offer` |
| Product catalog loader (not used locally — DB unreachable) | `apps/api/src/api/utils/inbox_catalog.py::load_catalog_offers` |

Both scoring paths invoked are live product code; `match()` mirrors the
`/v1/match` behavior (threshold 80), `score_offer()` mirrors the `/inbox`
unranked pass.

## Profile panel (frozen)

Source: `apps/api/fixtures/golden/profiles/profile_0{1..5}.json`, copied verbatim
to `inputs/profiles/`.

| File | Profile ID | Type | Notes |
|---|---|---|---|
| profile_01_data_analyst.json | golden_01 | data | python, sql, data_visualization, excel, powerbi |
| profile_02_developer.json | golden_02 | engineering | python, js, react, nodejs, sql, git |
| profile_03_marketing.json | golden_03 | business / marketing | marketing_digital, seo, ga, crm, excel |
| profile_04_finance.json | golden_04 | finance | excel, financial_modeling, accounting, sap, bloomberg |
| profile_05_commercial.json | golden_05 | business / sales | sales, negotiation, crm, prospection, presentation |

Gaps vs brief: no HR/ops profile in the repo, no explicit business+data hybrid.
Documented, not fabricated.

## Offer set (frozen, 35 offers)

| Source | Count | Path |
|---|---|---|
| Golden synthetic (VIE-001..020, `source=business_france`) | 20 | `apps/api/fixtures/golden/offers/offers.json` |
| VIE catalog fixtures (`vie_fixture_001..015`, `source=business_france`) | 15 | `apps/api/fixtures/offers/vie_catalog.json` |

Both files are in-repo, committed, and use `source=business_france`. The real
Business France corpus (PostgreSQL `clean_offers`) was **not reachable** from
this environment — see "Hypotheses & Limits". The two fixture files are merged
and shape-normalized (`skills_required` → `skills`, `languages_required` →
`languages`) into the frozen combined file `inputs/offers.json`. IDs are
disjoint, no duplicates.

## Baseline results

| Profile | Strict threshold ≥80 | Unthresholded top-1 | Unthresholded top-10 floor |
|---|---:|---:|---:|
| profile_01_data_analyst | 0 | 75 | — |
| profile_02_developer | 0 | 75 | — |
| profile_03_marketing | 0 | 75 | — |
| profile_04_finance | 0 | 75 | — |
| profile_05_commercial | 0 | 26 | — |

(Full top-10 scores per profile are in `outputs/*.json`.)

## Early observations (fact-based, no remedies)

1. **Zero profiles cross the 80 threshold** on this fixture set. The ceiling at
   75 for 4/5 profiles is explained below.
2. **`languages_score = 0.0` on all top hits.** The fixture offers carry
   language data but the product's language scoring returns 0 against the
   profile inputs — suggests a shape/match gap between profile `languages` and
   offer `languages` fields. Worth auditing in Sprint 2.
3. **`education_score = 0.0` on all top hits.** The offer fixtures rarely
   declare explicit education requirements, so this may be expected. Needs
   confirmation against real BF data.
4. **Country match = 1.0 everywhere**, because neither fixture set enforces a
   country filter that contradicts the profile nationalities.
5. **Generic-skill dominance visible in the raw ranking.**
   `vie_fixture_006 "Business Analyst VIE - Operations"` (only skill:
   `utiliser un logiciel de tableur`) is **top-3** for *data, marketing, and
   finance profiles simultaneously* — a direct illustration of the pattern the
   `ELEVIA_FILTER_GENERIC_URIS` filter was designed to address (flag is OFF in
   this run, per default).
6. **Profile extraction expands labels aggressively via ESCO aliases**
   (10–11 `skills` out of 5–6 input), but only 5 map to concrete ESCO URIs —
   confirming label-vs-URI coverage gap.
7. **profile_05_commercial is a weak outlier** (top-1 = 26). Its input skills
   (`sales`, `negotiation`, `prospection`, `presentation`) map poorly to ESCO
   aliases; only `crm` produced a useful URI in the top ranking.

## Hypotheses & limits

- **DB unreachable.** `apps/api/.env` contains a `DATABASE_URL` whose host
  component fails DNS resolution (contains a stray `@`). The production path
  `load_catalog_offers()` cannot execute here. Not repaired in this sprint —
  documented only. Consequence: baseline uses in-repo fixtures, not real BF.
- **No ESCO URI pre-computation on the fixtures.** The engine falls back to
  `_map_offer_skills_to_uris` at score time — this is the existing fallback
  code path, not a workaround.
- **Threshold-gated output is faithfully empty.** The strict path (`match()`)
  returns 0 results for every profile on this fixture set. The unthresholded
  path is provided alongside for comparison use in later sprints.
- **Profile gaps.** No HR/ops profile, no business+data hybrid available in the
  repo's frozen profile assets. Not fabricated.

## Artifacts

| Path | Purpose |
|---|---|
| `manifest.json` | global run manifest (date, git commit, env, summaries) |
| `inputs/profiles/*.json` | 5 frozen profile JSONs |
| `inputs/offers.json` | 35 frozen BF-shape offers |
| `outputs/profile_XX_*.json` | per-profile full record (extracted profile, both top-10s, matched/missing skills, per-offer breakdown) |
| `run_baseline.py` | the runner itself |
