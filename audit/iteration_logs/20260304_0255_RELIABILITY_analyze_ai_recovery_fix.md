# RELIABILITY — Analyze AI Recovery Fix

## Objective
Validate error handling stability and ensure no impact on core endpoints.

## Actions
- Added FastAPI validation handler for /analyze/recover-skills invalid payloads.
- Confirmed no changes to /profile/parse-file, /inbox, /v1/match.
- Ensured network errors return a stable UI message.

## Files touched
- apps/api/src/api/main.py
- apps/web/src/lib/api.ts
- apps/web/src/pages/AnalyzePage.tsx

## Risks
- Low: localized exception handler for a single endpoint.

## Result
STATUS: ok
SCOPE: Reliability - apps/api/src/api/main.py, apps/web/src/lib/api.ts, apps/web/src/pages/AnalyzePage.tsx
PLAN: none
PATCH: invalid request handler + network error fallback
TESTS: /tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_analyze_skill_recovery.py
RISKS: none

## Next
- Monitor if other endpoints need similar validation handlers (avoid broad global changes).
