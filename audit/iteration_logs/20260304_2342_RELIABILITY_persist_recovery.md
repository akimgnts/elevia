# RELIABILITY — Persist Analyze Recovery

Context
- Introduced SQLite cache for recovery results.

Checks
- Schema creation handled per-connection in analyze_recovery_cache.
- Cache writes are guarded by a lock (single process) and use WAL.
- No external calls in tests (LLM mocked).

Files reviewed
- apps/api/src/api/utils/analyze_recovery_cache.py
- apps/api/src/api/routes/analyze_recovery.py
- apps/api/src/compass/analyze_skill_recovery.py

STATUS: ok
SCOPE: Reliability - analyze recovery cache
PLAN: none
PATCH: none
TESTS: none (covered by QA)
RISKS: none
