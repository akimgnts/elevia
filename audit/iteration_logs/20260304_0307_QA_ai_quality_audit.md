# QA — AI Quality Audit

## Objective
Add tests for AI quality audit metrics and DEV-only UI wiring.

## Actions
- Added backend tests for empty/coherent/noise/mixed cases and cluster filter.
- Added frontend static test for DEV-only "Audit qualité IA" button.

## Files touched
- apps/api/tests/test_ai_quality_audit.py
- apps/web/tests/test_analyze_recovery_button.py

## Tests run
- /tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_ai_quality_audit.py
- /tmp/elevia_smoke_venv/bin/python -m pytest apps/web/tests/test_analyze_recovery_button.py apps/web/tests/test_vite_proxy_analyze.py apps/web/tests/test_analyze_error_mapping.py
- /tmp/elevia_smoke_venv/bin/python -m pytest  (FAILED: test_notebook_execution.py SystemExit)

## Result
STATUS: warn
SCOPE: Quality Assurance - audit metrics tests + UI static checks
PLAN: isolate full-suite failure in test_notebook_execution.py
PATCH: new test_ai_quality_audit.py + update analyze recovery tests
TESTS: see above
RISKS: full suite still fails due to SystemExit in notebook test

## Next
- Decide whether to exclude notebook execution tests from CI or mark as xfail.
