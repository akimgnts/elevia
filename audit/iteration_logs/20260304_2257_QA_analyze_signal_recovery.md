# QA — Analyze Signal Recovery

Context
- Added deterministic cluster signal policy + offer symmetry filtering.

Actions
- Executed targeted backend and frontend tests.

Commands run
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_analyze_skill_recovery.py apps/api/tests/test_cluster_signal_policy.py apps/api/tests/test_offer_domain_signal_policy.py`
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/web/tests/test_analyze_recovery_button.py apps/web/tests/test_analyze_error_mapping.py apps/web/tests/test_vite_proxy_analyze.py`

Results
- Backend: 24 passed
- Frontend: 13 passed

Action Plan
- No additional tests required for this change set.

STATUS: ok
SCOPE: Quality Assurance - analyze recovery + offer symmetry tests
PLAN: none
PATCH: new tests added + updated existing test
TESTS: pytest (commands above)
RISKS: none
