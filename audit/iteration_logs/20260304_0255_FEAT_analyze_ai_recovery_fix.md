# FEAT — Analyze AI Recovery Fix

## Objective
Verify API/UI contract and ensure legacy enrich_llm=1 is not used in normal Analyze flow.

## Actions
- Verified Analyze recovery endpoint `/analyze/recover-skills` and frontend wiring.
- Ensured UI warning banner only shows legacy deprecation when legacy toggle is enabled.
- Confirmed A+IA mode does not add `enrich_llm=1` (DEV-only toggle still available).

## Files touched
- apps/web/src/pages/AnalyzePage.tsx
- apps/web/src/lib/api.ts

## Risks
- Minimal: UI-only message handling and warning filtering.

## Result
STATUS: ok
SCOPE: Feature & Contract - apps/web/src/pages/AnalyzePage.tsx, apps/web/src/lib/api.ts
PLAN: none
PATCH: updated error mapping + warning filter
TESTS: /tmp/elevia_smoke_venv/bin/python -m pytest apps/web/tests/test_analyze_recovery_button.py apps/web/tests/test_vite_proxy_analyze.py apps/web/tests/test_analyze_error_mapping.py
RISKS: none

## Next
- If new error codes are added, update UI mapping + static tests.
