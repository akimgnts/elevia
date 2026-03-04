# Analyze Recover Skills — Wiring Fix — Iteration

## 1. Symptom (404) + reproduction steps
- Sur /analyze, clic "Récupérer des compétences (IA)" → API 404 {"detail":"Not Found"}.
- Repro supposée en dev local (Vite), bouton DEV-only.

## 2. Findings (Expected vs Actual URL table)

| Item | Expected | Actual (from code) | Evidence |
|---|---|---|---|
| Front endpoint | `/analyze/recover-skills` | `${API_BASE}/analyze/recover-skills` | `apps/web/src/lib/api.ts` uses `API_BASE` + `/analyze/recover-skills` |
| API_BASE default | relative paths in dev | `API_BASE = VITE_API_URL || VITE_API_BASE_URL || "/api"` | `apps/web/src/lib/api.ts` |
| Backend route | `/analyze/recover-skills` | `/analyze/recover-skills` (DEV-only, 400 if gate off) | `apps/api/src/api/routes/analyze_recovery.py` |
| Router mounted | `analyze_recovery_router` registered | `app.include_router(analyze_recovery_router)` | `apps/api/src/api/main.py` |
| Vite dev proxy | must proxy `/analyze` if API_BASE is relative | **missing before fix** | `apps/web/vite.config.ts` list had no `/analyze` |

Key refs from required artifacts:
- Iteration log (20260303_0200) confirms endpoint `POST /analyze/recover-skills` + DEV-only gate, and frontend wiring via `fetchRecoverSkills()`.
- COMPASS_CANONICAL_PIPELINE.md reiterates dev-only gates and no scoring changes.
- REPO_AUDIT_MASTER.md confirms canonical pipeline wiring and dev gates are present.
- runtime_smoke_results.json shows API is running and routes are mounted (health OK).

## 3. Root Cause (1 phrase)
Vite dev proxy did not forward `/analyze/*` to the API, so a relative call to `/analyze/recover-skills` returned 404 from the frontend server instead of hitting FastAPI.

## 4. Fix (exact change list)
- Add `/analyze` to Vite dev proxy so relative calls reach FastAPI.
- Add static test to prevent regression.

## 5. Tests (commands + résultats)
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_analyze_skill_recovery.py apps/web/tests/test_vite_proxy_analyze.py`
- Result: PASS (see test output in terminal).

## 6. Manual verification (curl)
With DEV gate OFF:
```
curl -sS -X POST http://localhost:8000/analyze/recover-skills \
  -H 'Content-Type: application/json' \
  -d '{"cluster":"DATA_IT","ignored_tokens":["python"],"noise_tokens":[],"validated_esco_labels":[]}'
```
Expected: `400` with `{ error: { code: "DEV_TOOLS_DISABLED" ... } }`

With DEV gate ON:
```
ELEVIA_DEV_TOOLS=1 curl -sS -X POST http://localhost:8000/analyze/recover-skills \
  -H 'Content-Type: application/json' \
  -d '{"cluster":"DATA_IT","ignored_tokens":["python"],"noise_tokens":[],"validated_esco_labels":[]}'
```
Expected: `200` with keys `recovered_skills`, `ai_available`, `error`, `request_id`.

## 7. Next steps
- If a 404 still occurs in prod/staging, verify reverse-proxy base path and `VITE_API_BASE_URL` value (avoid `/api` prefix unless the proxy rewrites it).
