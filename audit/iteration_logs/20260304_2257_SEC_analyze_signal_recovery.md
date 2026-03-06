# SEC — Analyze Signal Recovery

Context
- Added deterministic filtering and new response stats fields.

Findings
- No secrets logged or added.
- No new SQL/command execution.
- Input handling remains in FastAPI + deterministic filters.

Actions
- Reviewed `apps/api/src/api/routes/analyze_recovery.py` and `apps/api/src/compass/cluster_signal_policy.py` for validation/safety.

Files changed
- apps/api/src/compass/cluster_signal_policy.py
- apps/api/src/api/routes/analyze_recovery.py

Action Plan
- None.

STATUS: ok
SCOPE: Security - analyze recovery
PLAN: none
PATCH: none
TESTS: none
RISKS: none
