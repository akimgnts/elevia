# REPO_AUDIT_MASTER

## TL;DR

- `run_cv_pipeline()` is now the single entrypoint for `/profile/parse-file` and `/profile/parse-baseline`.
- Legacy Elevia LLM extraction (`/profile/ingest_cv`) is DEV-only and gated.
- Offer ingest and runtime use the same canonical normalization (`compass.offer_canonicalization.normalize_offers_to_uris`).

## Executive Summary

- **Canonical (Compass-first)**: `/profile/parse-file`, `/profile/parse-baseline`, `/profile/structured`, `/profile/summary`, `/inbox`, `/v1/match`, `/offers/catalog`.
- **Parallel (non-Compass pipelines)**: `/documents/*`, `/apply-pack`, `/context/*`, `/cluster/library/*`, `/metrics/*`, `/applications/*`, debug/dev endpoints.
- **Legacy (DEV-only)**: `/profile/ingest_cv` (LLM extraction), `enrich_llm=1` in `/profile/parse-file`.

## Architecture Map

```
CV Parse (runtime)

  file/text -> baseline_parser (ESCO) -> profile_cluster

  -> profile_structurer (Compass D+) -> profile_summary cache

  -> Compass E (cluster_library) [flag-gated]

  -> DOMAIN URIs -> profile payload


Offer Runtime (Inbox)

  catalog load -> ESCO normalize -> DOMAIN URIs -> offer_cluster

  -> MatchingEngine (matching_v1) -> Compass signal layer

```

## Pipeline Diagrams

### CV Parse

```

parse-file -> extract_text_from_pdf -> run_cv_pipeline()

  -> baseline ESCO parse + profile cluster

  -> structure_profile_text_v1 -> profile_summary cache

  -> Compass E (auto-on in dev if unset) -> domain enrichment

  -> build_domain_uris_for_text -> profile payload

```

### Offer Ingest (Offline)

```

ingest_pipeline.py -> normalize_offers_to_uris (canonical)

  -> fact_offer_skills (offers.db) + payload_json

```

### Inbox Runtime

```

load_catalog_offers -> normalize_offers_to_uris (canonical)

  -> MatchingEngine -> signal_layer

```

### Matching API

```

/v1/match -> extract_profile -> MatchingEngine -> MatchResult

```

## Pipeline A→F Map (Compass Layers)

| Layer | Purpose | Source of Truth |
|---|---|---|
| A | ESCO extraction baseline | `profile/baseline_parser.run_baseline` + `esco.extract` |
| B | Profile cluster detection | `profile/profile_cluster.detect_profile_cluster` |
| C | Offer cluster detection | `offer/offer_cluster.detect_offer_cluster` |
| D | Structuring (profile/offer) | `compass.profile_structurer` / `compass.text_structurer` |
| E | Domain enrichment | `compass.cv_enricher` + `compass.cluster_library` |
| F | Compass signal | `compass.signal_layer.build_explain_payload_v1` |

## Source of Truth (By Stage)

| Stage | File:Function | Notes |
|---|---|---|
| CV text extraction | `api.utils.pdf_text.extract_text_from_pdf` | parse-file only |
| ESCO mapping (profile) | `profile.baseline_parser.run_baseline` | deterministic ESCO |
| ESCO mapping (offer) | `compass.offer_canonicalization.normalize_offers_to_uris` | runtime + ingest |
| Domain library | `compass.cluster_library.ClusterLibraryStore` | context.db |
| Domain URIs | `compass.domain_uris.build_domain_uris_for_text` | profile + offer |
| Matching | `matching.matching_v1.MatchingEngine` | scoring core |
| Explain | `compass.signal_layer.build_explain_payload_v1` | display-only |

## Endpoint Mapping Table

| Method | Path | File |
|---|---|---|
| GET | /applications | `apps/api/src/api/routes/applications.py` |
| GET | /applications/{offer_id} | `apps/api/src/api/routes/applications.py` |
| POST | /applications | `apps/api/src/api/routes/applications.py` |
| PATCH | /applications/{offer_id} | `apps/api/src/api/routes/applications.py` |
| DELETE | /applications/{offer_id} | `apps/api/src/api/routes/applications.py` |
| POST | /apply-pack | `apps/api/src/api/routes/apply_pack.py` |
| GET | /cluster/library/metrics | `apps/api/src/api/routes/cluster_library_api.py` |
| GET | /cluster/library/radar | `apps/api/src/api/routes/cluster_library_api.py` |
| GET | /cluster/library/skills | `apps/api/src/api/routes/cluster_library_api.py` |
| POST | /cluster/library/enrich/cv | `apps/api/src/api/routes/cluster_library_api.py` |
| POST | /offer | `apps/api/src/api/routes/context.py` |
| POST | /profile | `apps/api/src/api/routes/context.py` |
| POST | /fit | `apps/api/src/api/routes/context.py` |
| POST | /debug/match | `apps/api/src/api/routes/debug_match.py` |
| GET | /debug/status | `apps/api/src/api/routes/debug_match.py` |
| POST | /dev/cv-delta | `apps/api/src/api/routes/dev_tools.py` |
| POST | /dev/metrics | `apps/api/src/api/routes/dev_tools.py` |
| POST | /documents/cv | `apps/api/src/api/routes/documents.py` |
| POST | /documents/cv/for-offer | `apps/api/src/api/routes/documents.py` |
| POST | /documents/cv/html/for-offer | `apps/api/src/api/routes/documents.py` |
| POST | /documents/letter/for-offer | `apps/api/src/api/routes/documents.py` |
| GET | /documents/cv/status | `apps/api/src/api/routes/documents.py` |
| GET | /health | `apps/api/src/api/routes/health.py` |
| GET | /health/deps | `apps/api/src/api/routes/health.py` |
| POST | /inbox | `apps/api/src/api/routes/inbox.py` |
| POST | /offers/{offer_id}/decision | `apps/api/src/api/routes/inbox.py` |
| POST | /offers/{offer_id}/semantic | `apps/api/src/api/routes/inbox.py` |
| POST | /match | `apps/api/src/api/routes/matching.py` |
| POST | /correction | `apps/api/src/api/routes/metrics.py` |
| GET | /sample | `apps/api/src/api/routes/offers.py` |
| GET | /catalog | `apps/api/src/api/routes/offers.py` |
| GET | /{offer_id}/detail | `apps/api/src/api/routes/offers.py` |
| POST | /ingest_cv | `apps/api/src/api/routes/profile.py` |
| POST | /profile/parse-baseline | `apps/api/src/api/routes/profile_baseline.py` |
| POST | /profile/parse-file | `apps/api/src/api/routes/profile_file.py` |
| POST | /profile/key-skills | `apps/api/src/api/routes/profile_key_skills.py` |
| POST | /profile/structured | `apps/api/src/api/routes/profile_structured.py` |
| GET | /profile/structured | `apps/api/src/api/routes/profile_structured.py` |
| GET | /profile/summary | `apps/api/src/api/routes/profile_summary.py` |

## Flags Table (API)

| Name | File | Default |
|---|---|---|
| ELEVIA_DEBUG_MATCHING | `apps/api/src/matching/extractors.py` | `""` |
| ELEVIA_DEBUG_MATCHING | `apps/api/src/matching/match_trace.py` | `""` |
| ELEVIA_SCORE_USE_URIS | `apps/api/src/matching/match_trace.py` | `"1"` |
| ELEVIA_DEBUG_MATCHING | `apps/api/src/matching/matching_v1.py` | `""` |
| ELEVIA_SCORE_USE_URIS | `apps/api/src/matching/matching_v1.py` | `"1"` |
| LLM_PROVIDER | `apps/api/src/profile/llm_client.py` | `"mock"` |
| LLM_API_KEY | `apps/api/src/profile/llm_client.py` | `""` |
| LLM_MODEL | `apps/api/src/profile/llm_client.py` | `""` |
| OPENAI_MODEL | `apps/api/src/profile/llm_skill_suggester.py` | `` |
| LLM_MODEL | `apps/api/src/profile/llm_skill_suggester.py` | `` |
| ELEVIA_EMBEDDINGS_LOCAL | `apps/api/src/semantic/embeddings.py` | `""` |
| ELEVIA_DEV_TOOLS | `apps/api/src/api/main.py` | `""` |
| ELEVIA_CLUSTER_CV_MIN | `apps/api/src/compass/cluster_library.py` | `"2"` |
| ELEVIA_CLUSTER_OFFER_MIN | `apps/api/src/compass/cluster_library.py` | `"3"` |
| ELEVIA_CLUSTER_OFFER_ONLY_MIN | `apps/api/src/compass/cluster_library.py` | `"5"` |
| ELEVIA_CLUSTER_LIBRARY_DB | `apps/api/src/compass/cluster_library.py` | `str(_DEFAULT_DB` |
| ELEVIA_ENABLE_COMPASS_E | `apps/api/src/compass/canonical_pipeline.py` | `"0"` |
| ELEVIA_TRACE_PIPELINE_WIRING | `apps/api/src/compass/canonical_pipeline.py` | `"0"` |
| ELEVIA_CLUSTER_ESCO_MIN | `apps/api/src/compass/cv_enricher.py` | `"3"` |
| ELEVIA_CLUSTER_DENSITY_MIN | `apps/api/src/compass/cv_enricher.py` | `"0.02"` |
| ELEVIA_DEBUG_STRUCTURER | `apps/api/src/compass/text_structurer.py` | `""` |
| OPENAI_API_KEY | `apps/api/src/compass/llm_enricher.py` | `""` |
| ELEVIA_DEBUG_SIGNAL | `apps/api/src/compass/signal_layer.py` | `""` |
| ELEVIA_DEBUG_PROFILE_STRUCT | `apps/api/src/compass/profile_structurer.py` | `""` |
| OPENAI_API_KEY | `apps/api/src/api/utils/env.py` | `` |
| LLM_API_KEY | `apps/api/src/api/utils/env.py` | `` |
| ELEVIA_DEV_TOOLS | `apps/api/src/api/routes/dev_tools.py` | `""` |
| OPENAI_API_KEY | `apps/api/src/api/routes/dev_tools.py` | `` |
| ELEVIA_DEBUG_API_TIMING | `apps/api/src/api/routes/applications.py` | `""` |
| ELEVIA_DEBUG_PROFILE_SUMMARY | `apps/api/src/api/routes/profile.py` | `""` |
| ELEVIA_DEBUG_PROFILE_SUMMARY | `apps/api/src/api/routes/profile_summary.py` | `""` |
| ENV | `apps/api/src/api/routes/debug_match.py` | `""` |
| DEBUG | `apps/api/src/api/routes/debug_match.py` | `""` |
| ELEVIA_DEV | `apps/api/src/api/routes/debug_match.py` | `""` |
| ELEVIA_DEBUG_MATCHING | `apps/api/src/api/routes/debug_match.py` | `"not_set"` |
| ELEVIA_DEBUG_PROFILE_SUMMARY | `apps/api/src/api/routes/profile_baseline.py` | `""` |
| ELEVIA_DEBUG_MATCHING | `apps/api/src/api/routes/inbox.py` | `""` |
| ELEVIA_INBOX_PROFILE_FIXTURES | `apps/api/src/api/routes/inbox.py` | `""` |
| ELEVIA_PROFILE_FIXTURE | `apps/api/src/api/routes/inbox.py` | `""` |
| ELEVIA_PROFILE_FIXTURE_MIN_SKILLS | `apps/api/src/api/routes/inbox.py` | `"3"` |
| ELEVIA_PROFILE_FIXTURE_DEFAULT | `apps/api/src/api/routes/inbox.py` | `"akim_guentas_matching"` |
| ELEVIA_DEBUG_API_TIMING | `apps/api/src/api/routes/inbox.py` | `""` |
| ELEVIA_DEBUG_INBOX_FILTERS | `apps/api/src/api/routes/inbox.py` | `""` |
| ELEVIA_DEBUG_PROFILE_SUMMARY | `apps/api/src/api/routes/profile_file.py` | `""` |
| ELEVIA_DEBUG_CLUSTER | `apps/api/src/api/routes/cluster_library_api.py` | `""` |

## Flags Table (WEB)

| Name | File |
|---|---|
| DEV | `apps/web/src/components/DevStatusCard.tsx` |
| VITE_API_BASE_URL | `apps/web/src/components/DevStatusCard.tsx` |
| VITE_API_URL | `apps/web/src/components/DevStatusCard.tsx` |
| VITE_API_URL | `apps/web/src/lib/api.ts` |
| VITE_API_BASE_URL | `apps/web/src/lib/api.ts` |
| DEV | `apps/web/src/lib/profileMatching.ts` |
| VITE_API_BASE_URL | `apps/web/src/api/applications.ts` |
| VITE_API_URL | `apps/web/src/api/applications.ts` |
| DEV | `apps/web/src/pages/InboxPage.tsx` |
| DEV | `apps/web/src/pages/DashboardPage.tsx` |
| DEV | `apps/web/src/services/match.service.ts` |

## Callgraph Summary

- `/profile/parse-file` → `api.routes.profile_file.parse_file` → 7 calls
- `/profile/parse-baseline` → `api.routes.profile_baseline.parse_baseline` → 5 calls
- `/profile/ingest_cv` → `api.routes.profile.ingest_cv` → 3 calls
- `/profile/structured` → `api.routes.profile_structured.post_profile_structured` → 1 calls
- `/profile/summary` → `api.routes.profile_summary.get_profile_summary_route` → 1 calls
- `/inbox` → `api.routes.inbox.get_inbox` → 5 calls
- `/v1/match` → `api.routes.matching.match_profile` → 3 calls
- `/offers/catalog` → `api.routes.offers.get_catalog` → 4 calls
- `ingest_pipeline.py` → `apps/api/scripts/ingest_pipeline.py` → 3 calls

## Findings (Critical/High/Medium/Low)

**Critical**
- None (canonical wiring now enforced via `run_cv_pipeline()`).

**High**
1. `/offers/sample` still serves legacy static dataset; not aligned with DB catalog.
2. `/cluster/library/enrich/cv` runs enrichment outside canonical parse routes (debug path).

**Medium**
3. `/documents/*` and `/apply-pack` can call LLMs; separate pipeline from Compass.
4. `/context/*` uses semantic store; not part of scoring, can diverge from Compass signals.

**Low**
5. `matching_v1` uses offer `skills_uri` if present; `/v1/match` may receive raw offers without normalization.

## Next-Step Recommendations (No Code Changes)

1. Decide whether `/offers/sample` should be removed or flagged DEV-only.
2. Clarify ownership of `/cluster/library/enrich/cv` (debug-only vs admin).
3. Consolidate flags documentation with code truth table.

## Runtime Smoke Summary

- Runtime smoke succeeded (health + parse-file + inbox).
- Full output: `audit/runtime_smoke_results.json`
