# Analyze Recover Skills — Wiring Fix — Iteration

## FEAT

**Findings (Expected vs Actual URL table)**

| Item | Expected | Actual | Evidence |
|---|---|---|---|
| Front endpoint | `/analyze/recover-skills` | `${API_BASE}/analyze/recover-skills` | `apps/web/src/lib/api.ts` (`fetchRecoverSkills`) |
| API base | relative `/api` in dev | `API_BASE = VITE_API_URL || VITE_API_BASE_URL || "/api"` | `apps/web/src/lib/api.ts` |
| Backend route | `/analyze/recover-skills` | `/analyze/recover-skills` (DEV-only) | `apps/api/src/api/routes/analyze_recovery.py` |
| Router registration | `include_router(analyze_recovery_router)` | present | `apps/api/src/api/main.py` |
| Vite proxy | must include `/analyze` when API_BASE is relative | **missing before fix** | `apps/web/vite.config.ts` |

**Root cause (exact)**
- Vite dev proxy did not include `/analyze`, so the relative call hit the Vite server and returned 404 instead of reaching FastAPI.

**Diff minimal appliqué**
- Added `/analyze` proxy in `apps/web/vite.config.ts`.
- Added static test to lock proxy presence.

**Agent Output**
```
STATUS: ok
SCOPE: Feature & Contract - apps/api/src/api/routes/analyze_recovery.py, apps/api/src/api/main.py, apps/web/src/lib/api.ts, apps/web/vite.config.ts
PLAN: none
PATCH: apps/web/vite.config.ts (+"/analyze" proxy), apps/web/tests/test_vite_proxy_analyze.py
TESTS: /tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_analyze_skill_recovery.py apps/web/tests/test_vite_proxy_analyze.py
RISKS: none
```

---

## OBS

**Observability check**
- Existing endpoint already logs request + result (`RECOVER_SKILLS_REQUEST` / `RECOVER_SKILLS_RESULT`) and returns `request_id` in response.
- No additional logs required for this wiring fix.

**Agent Output**
```
STATUS: ok
SCOPE: Observability - apps/api/src/api/routes/analyze_recovery.py
PLAN: none
PATCH: none
TESTS: none
RISKS: none
```

---

## QA

**Tests ajoutés / adaptés**
- Backend DEV gate + endpoint existence already covered by `apps/api/tests/test_analyze_skill_recovery.py` (TestEndpointDevOnlyGate).
- Frontend static test added for proxy presence: `apps/web/tests/test_vite_proxy_analyze.py`.

**Tests exécutés**
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_analyze_skill_recovery.py`
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/web/tests/test_vite_proxy_analyze.py`

**Agent Output**
```
STATUS: ok
SCOPE: Quality Assurance - apps/api/tests/test_analyze_skill_recovery.py, apps/web/tests/test_vite_proxy_analyze.py
PLAN: none
PATCH: apps/web/tests/test_vite_proxy_analyze.py
TESTS: pytest apps/api/tests/test_analyze_skill_recovery.py -v ; pytest apps/web/tests/test_vite_proxy_analyze.py -v
RISKS: none
```

---

## RELIABILITY

**Checks**
- Fix is limited to Vite proxy config; no runtime code path changes in /profile/parse-file, /inbox, /v1/match.
- No double-prefix introduced: `/analyze` proxy is a direct passthrough to API target.

**Endpoints tested**
- Backend endpoints unchanged; relied on existing runtime smoke evidence + no code changes in those routes.

**Agent Output**
```
STATUS: ok
SCOPE: Reliability - apps/web/vite.config.ts
PLAN: none
PATCH: none
TESTS: none
RISKS: none
```

---

## SEC

**Security check**
- Endpoint remains DEV-only: `ELEVIA_DEV_TOOLS=1` gate in `analyze_recovery.py` returns 400 otherwise.
- No API keys exposed client-side; frontend only calls endpoint and handles error messages.
- Response contains recovered skills only; no sensitive data added.

**Agent Output**
```
STATUS: ok
SCOPE: Security - apps/api/src/api/routes/analyze_recovery.py, apps/web/src/lib/api.ts
PLAN: none
PATCH: none
TESTS: none
RISKS: none
```

---

# Checklist finale

- [x] Plus aucun 404 Vite sur /analyze/recover-skills (proxy ajouté)
- [x] DEV gate OFF → 400 clair (test backend existant)
- [x] DEV gate ON → 200 JSON stable (test backend existant)
- [x] Tests ajoutés passent
- [x] Aucun impact sur scoring
- [x] Log complet généré

BINARY CONCLUSION:
- FIXED
