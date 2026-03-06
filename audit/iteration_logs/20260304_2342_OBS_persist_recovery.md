# OBS — Persist Analyze Recovery (Preflight)

Decisions
- Use profile_fingerprint from parse-file response and request_hash for cache key.
- Use context.db via new analyze_recovery_cache module.

Commands run
- `rg -n "profile_fingerprint|extracted_text" apps/api/src/api/routes/profile_file.py`
- `rg -n "recover-skills" apps/api/src/api/routes/analyze_recovery.py`
- `rg -n "ParseFileResponse" apps/web/src/lib/api.ts`

Outputs
- parse-file already extracts text and has access to cluster; safe to emit extracted_text_hash + profile_fingerprint.

Action Plan
- Add cache store + hash computation + response fields; expose in UI.

STATUS: ok
SCOPE: Observability - preflight inspection
PLAN: add deterministic fields to response for DEV panel
PATCH: none (preflight)
TESTS: none
RISKS: none
