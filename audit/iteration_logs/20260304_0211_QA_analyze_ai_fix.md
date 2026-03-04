# Analyze AI Fix — QA Agent

## Context
Need tests to lock: DEV gate behavior, stable error codes, and frontend wiring/proxy.

## Findings
- Backend tests existed for DEV gate; needed updates for new error_code/ai_error fields.
- Frontend static tests needed updates for IA merge + error mapping + debug badge.

## Actions
- Updated backend tests to assert OPENAI_KEY_MISSING and DEV_TOOLS_DISABLED error codes.
- Updated frontend static tests to check error code mapping + debug badge fields.
- Added static test to assert Vite proxy includes /analyze.

## Files changed
- `apps/api/tests/test_analyze_skill_recovery.py`
- `apps/web/tests/test_analyze_recovery_button.py`
- `apps/web/tests/test_vite_proxy_analyze.py`

## Tests run
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_analyze_skill_recovery.py`
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/web/tests/test_analyze_recovery_button.py apps/web/tests/test_vite_proxy_analyze.py`

## Result
All targeted tests pass; behavior locked for gating + error mapping + proxy.

## Next checks
- None.
