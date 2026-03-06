# FEAT — Analyze Signal Recovery (Implementation)

Decisions
- Implement deterministic `cluster_signal_policy` and integrate it into AI recovery + offer domain tokens.
- Keep API contract additive (new optional stats fields only).

Actions
- Added `cluster_signal_policy.py` with deterministic normalization, allow/block lists, and prefilter functions.
- Integrated `build_candidates_for_ai()` into `/analyze/recover-skills` route; AI receives only candidates.
- Added recovery stats to response payload (raw_count, candidate_count, dropped_count, noise_ratio, tech_density, dropped_reasons).
- Applied `filter_offer_domain_tokens()` before domain URIs are applied in offer canonicalization.
- Added DEV-only recovery metrics panel in Analyze UI.

Files changed
- apps/api/src/compass/cluster_signal_policy.py (new)
- apps/api/src/api/routes/analyze_recovery.py
- apps/api/src/compass/offer_canonicalization.py
- apps/web/src/pages/AnalyzePage.tsx
- apps/web/src/lib/api.ts
- apps/api/tests/test_cluster_signal_policy.py (new)
- apps/api/tests/test_offer_domain_signal_policy.py (new)
- apps/api/tests/test_analyze_skill_recovery.py

Commands run
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_analyze_skill_recovery.py apps/api/tests/test_cluster_signal_policy.py apps/api/tests/test_offer_domain_signal_policy.py`
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/web/tests/test_analyze_recovery_button.py apps/web/tests/test_analyze_error_mapping.py apps/web/tests/test_vite_proxy_analyze.py`

Outputs
- API tests: 24 passed
- Web tests: 13 passed

Action Plan
- Run manual check: /analyze recovery button → metrics panel shows counts; machine learning stays in candidates for DATA_IT.

STATUS: ok
SCOPE: Feature & Contract - analyze recovery + offer symmetry
PLAN: none
PATCH: implemented deterministic prefilter + offer symmetry
TESTS: pytest (see commands)
RISKS: none (additive fields only)
