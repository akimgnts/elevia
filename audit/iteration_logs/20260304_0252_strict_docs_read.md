# STRICT DOCS READ

## audit/REPO_AUDIT_MASTER.md — READ OK
- run_cv_pipeline() is the canonical entrypoint for /profile/parse-file and /profile/parse-baseline.
- Legacy /profile/ingest_cv is DEV-only and gated; enrich_llm=1 is legacy.
- Offer normalization is unified via compass.offer_canonicalization for ingest + runtime.
- Compass E is flag-gated; scoring core remains untouched.

## docs/architecture/COMPASS_CANONICAL_PIPELINE.md — READ OK
- CV parse always runs baseline ESCO extraction + profile cluster detection.
- enrich_llm=1 is DEPRECATED and DEV-only; Compass E is canonical enrichment.
- Compass E defaults ON in local/dev if unset; OFF in prod unless enabled.
- Score invariance is guaranteed: matching_v1 is never modified by Compass layers.

## audit/iteration_logs/20260304_0159_analyze_recover_e2e.md — READ OK
- Root cause was missing Vite proxy for /analyze causing 404.
- Fix added /analyze proxy and static test to enforce it.
- DEV gate returns 400 when ELEVIA_DEV_TOOLS unset; endpoint returns JSON shape.

## audit/runtime_smoke_results.json — READ OK
- /health and /profile/parse-file smoke succeeded in prior run.
- parse-file used canonical_compass with compass_e_enabled=true in smoke payload.

