# OBS — Analyze Signal Recovery (Preflight)

Decisions
- Proceed with deterministic signal policy and recovery gating after confirming repo context and target files.

Commands run + outputs
- `pwd` → `/Users/akimguentas/Dev/elevia-compass`
- `git status -sb` → `## main...origin/main [ahead 17]`
- `rg -n "AnalyzePage" apps/web/src/pages/AnalyzePage.tsx` → found AnalyzePage with recovery UI sections.
- `rg -n "recover" apps/web/src/pages/AnalyzePage.tsx` → recovery UI + DEV panel references.
- `rg -n "recover" apps/web/src/lib/api.ts` → `fetch /analyze/recover-skills`.
- `rg -n "recover-skills|analyze_recovery" apps/api/src/api/routes` → `apps/api/src/api/routes/analyze_recovery.py`.
- `rg -n "analyze_skill_recovery" apps/api/src/compass` → `apps/api/src/compass/analyze_skill_recovery.py`.
- `rg -n "offer_canonicalization" apps/api/src/compass/offer_canonicalization.py` → canonical offer normalization present.

Findings
- Frontend calls `POST /analyze/recover-skills` via `apps/web/src/lib/api.ts`.
- Backend route exists at `apps/api/src/api/routes/analyze_recovery.py` and uses `compass/analyze_skill_recovery.py`.
- Offer normalization lives in `apps/api/src/compass/offer_canonicalization.py`.

Action Plan
- Implement deterministic `cluster_signal_policy` and integrate into recover-skills + offer canonicalization.
- Ensure DEV-only metrics surfaced in Analyze UI.
- Add tests for deterministic candidate filtering and offer symmetry.

STATUS: ok
SCOPE: Observability - preflight discovery only
PLAN: add deterministic counters + structured stats in recover-skills response (DEV-only)
PATCH: none (preflight)
TESTS: none (preflight)
RISKS: none (preflight)
