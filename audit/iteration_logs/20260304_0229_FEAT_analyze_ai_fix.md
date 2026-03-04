# FEAT — Analyze AI Fix Iteration

## Context
Audit the Analyze recovery feature contract and UI wiring to remove legacy enrich_llm usage and stabilize error messaging.

## Findings
- Backend route exists: `POST /analyze/recover-skills` in `apps/api/src/api/routes/analyze_recovery.py` (DEV-gated).
- Frontend calls `fetchRecoverSkills` in `apps/web/src/lib/api.ts` and wires it in `apps/web/src/pages/AnalyzePage.tsx`.
- Legacy LLM path is DEV-only via `parseFileEnriched()` and a DEV toggle.
- Error code mapping exists in Analyze UI for `DEV_TOOLS_DISABLED`, `OPENAI_KEY_MISSING`, `MODEL_MISSING`, `LLM_CALL_FAILED`.

Contract spec (current):
- Request: `{ cluster, ignored_tokens, noise_tokens, validated_esco_labels, profile_text_excerpt? }`
- Response (stable): `{ recovered_skills[], ai_available, ai_error, error_code, error_message, request_id, counts }`

## Actions
- Verified contract alignment between frontend types and backend response shape.
- Verified legacy enrich_llm=1 is not used by default (DEV-only toggle).

## Files changed
- none

## Tests run
- /tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_analyze_skill_recovery.py
- /tmp/elevia_smoke_venv/bin/python -m pytest apps/web/tests/test_analyze_recovery_button.py apps/web/tests/test_vite_proxy_analyze.py

## Result
STATUS: ok
SCOPE: Feature & Contract - apps/api/src/api/routes/analyze_recovery.py, apps/web/src/lib/api.ts, apps/web/src/pages/AnalyzePage.tsx
PLAN: none
PATCH: none
TESTS: pytest apps/api/tests/test_analyze_skill_recovery.py -v ; pytest apps/web/tests/test_analyze_recovery_button.py -v apps/web/tests/test_vite_proxy_analyze.py -v
RISKS: none

## Next checks
- If future changes add new error codes, update UI mapping and tests.
