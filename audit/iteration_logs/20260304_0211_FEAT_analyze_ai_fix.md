# Analyze AI Fix — FEAT Agent

## Context
Analyze “Récupérer des compétences (IA)” returned 404 and showed vague AI error. Goal: remove legacy enrich_llm=1 usage for A+IA, ensure recover endpoint is called correctly, and return stable error codes.

## Findings
- Front uses `${API_BASE}/analyze/recover-skills` (relative `/api` default).
- Backend route exists at `/analyze/recover-skills` and is registered in `api/main.py`.
- Vite proxy lacked `/analyze`, causing 404 from dev server.
- AnalyzePage still called legacy LLM only when explicit dev toggle; A+IA no longer uses enrich_llm=1 (OK).

## Actions
- Added `/analyze` to Vite proxy.
- Kept legacy LLM behind DEV-only toggle labeled “Legacy LLM (deprecated)”.
- Ensured recovery request uses `{ cluster, ignored_tokens, noise_tokens, validated_esco_labels }`.
- Merged recovered skills into “Compétences clés” list with IA tag (display-only).
- Added DEV-only debug badge for pipeline + AI status (ai_available/ai_error).

## Files changed
- `apps/web/vite.config.ts`
- `apps/web/src/pages/AnalyzePage.tsx`
- `apps/web/src/lib/api.ts`

## Tests run
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/web/tests/test_analyze_recovery_button.py apps/web/tests/test_vite_proxy_analyze.py`

## Result
Fixed Vite 404 and restored correct endpoint call in dev. A+IA no longer uses legacy enrich_llm=1; legacy path is explicit DEV-only.

## Next checks
- Verify live dev UI: /analyze → Recover Skills button reaches FastAPI and returns 200/400 as expected.
