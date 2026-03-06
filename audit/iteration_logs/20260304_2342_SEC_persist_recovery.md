# SEC — Persist Analyze Recovery

Context
- Cache stores hashes + recovered skills only.

Checks
- No raw CV text stored in cache.
- DEV gate preserved on /analyze/recover-skills.
- No secrets logged or returned.

Files reviewed
- apps/api/src/api/utils/analyze_recovery_cache.py
- apps/api/src/api/routes/analyze_recovery.py

STATUS: ok
SCOPE: Security - analyze recovery cache
PLAN: none
PATCH: none
TESTS: none
RISKS: none
