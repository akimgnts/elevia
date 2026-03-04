# QA — Analyze AI Recovery Fix

## Objective
Ensure tests cover error mapping and backend invalid request handling.

## Actions
- Added backend test for INVALID_REQUEST on bad payload.
- Added frontend static test to prevent 'undefined' and enforce fallback error mapping.
- Updated UI static tests for new error codes.

## Files touched
- apps/api/tests/test_analyze_skill_recovery.py
- apps/web/tests/test_analyze_recovery_button.py
- apps/web/tests/test_analyze_error_mapping.py

## Tests run
- /tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_analyze_skill_recovery.py
- /tmp/elevia_smoke_venv/bin/python -m pytest apps/web/tests/test_analyze_recovery_button.py apps/web/tests/test_vite_proxy_analyze.py apps/web/tests/test_analyze_error_mapping.py

## Result
STATUS: ok
SCOPE: Quality Assurance - apps/api/tests/test_analyze_skill_recovery.py, apps/web/tests/test_analyze_recovery_button.py, apps/web/tests/test_analyze_error_mapping.py
PLAN: none
PATCH: new/updated tests
TESTS: pytest apps/api/tests/test_analyze_skill_recovery.py -v ; pytest apps/web/tests/test_analyze_recovery_button.py -v apps/web/tests/test_vite_proxy_analyze.py -v apps/web/tests/test_analyze_error_mapping.py -v
RISKS: none

## Next
- Expand static tests if new error codes are introduced.
