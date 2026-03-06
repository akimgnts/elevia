# RELIABILITY — Analyze Signal Recovery

Context
- Deterministic prefilter added for recovery candidates and offer domain tokens.

Findings
- No new external calls introduced.
- AI recovery remains DEV-only and already handles missing key gracefully.
- Offer filtering is pure and deterministic.

Actions
- Reviewed `apps/api/src/api/routes/analyze_recovery.py`, `apps/api/src/compass/cluster_signal_policy.py`, `apps/api/src/compass/offer_canonicalization.py`.

Files changed
- apps/api/src/compass/cluster_signal_policy.py
- apps/api/src/api/routes/analyze_recovery.py
- apps/api/src/compass/offer_canonicalization.py

Action Plan
- None.

STATUS: ok
SCOPE: Reliability - analyze recovery + offer symmetry
PLAN: none
PATCH: none (review only)
TESTS: none (relies on QA runs)
RISKS: none
