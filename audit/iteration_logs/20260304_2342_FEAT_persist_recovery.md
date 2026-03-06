# FEAT — Persist Analyze Recovery (Implementation)

Decisions
- Cache on (profile_fingerprint, request_hash) in SQLite context.db.
- Deterministic ordering for recovered skills.
- Require profile_fingerprint or extracted_text_hash; otherwise INVALID_REQUEST.

Actions
- Added analyze_recovery_cache store with schema + upsert.
- Added extracted_text_hash + profile_fingerprint to parse-file response.
- Added caching logic + request_hash in /analyze/recover-skills.
- Added deterministic sort for recovered skills.
- Updated Analyze UI to pass fingerprint and show cache state; added DEV force button.
- Updated API types and frontend tests.

Files changed
- apps/api/src/api/utils/analyze_recovery_cache.py (new)
- apps/api/src/api/routes/analyze_recovery.py
- apps/api/src/compass/analyze_skill_recovery.py
- apps/api/src/api/routes/profile_file.py
- apps/web/src/lib/api.ts
- apps/web/src/pages/AnalyzePage.tsx
- apps/api/tests/test_analyze_recovery_cache.py (new)
- apps/api/tests/test_analyze_skill_recovery.py
- apps/web/tests/test_analyze_recovery_button.py

Commands run
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_analyze_skill_recovery.py apps/api/tests/test_cluster_signal_policy.py apps/api/tests/test_offer_domain_signal_policy.py apps/api/tests/test_analyze_recovery_cache.py`
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/web/tests/test_analyze_recovery_button.py apps/web/tests/test_analyze_error_mapping.py apps/web/tests/test_vite_proxy_analyze.py`

Outputs
- Backend: 27 passed
- Frontend: 14 passed

Action Plan
- Manual dev check: recovery button shows cached state and disables unless forced.

STATUS: ok
SCOPE: Feature & Contract - analyze recovery caching
PLAN: none
PATCH: implemented persistence + determinism
TESTS: pytest (see commands)
RISKS: none (additive fields only)
