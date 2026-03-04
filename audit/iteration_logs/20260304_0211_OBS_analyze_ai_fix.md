# Analyze AI Fix — OBS Agent

## Context
Need actionable error codes and request tracing for /analyze/recover-skills without noisy logs.

## Findings
- Existing logs: RECOVER_SKILLS_REQUEST and RECOVER_SKILLS_RESULT with request_id.
- DEV gate returned 400 but lacked explicit log line with reason.

## Actions
- Added a structured info log when DEV gate blocks (`RECOVER_SKILLS_BLOCKED` with request_id + reason).
- Response now includes ai_available + ai_error + error_code + error_message + request_id.

## Files changed
- `apps/api/src/api/routes/analyze_recovery.py`
- `apps/api/src/compass/analyze_skill_recovery.py`

## Tests run
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_analyze_skill_recovery.py`

## Result
Observability improved: gating reason is logged, responses carry stable error codes and request_id.

## Next checks
- Confirm no secrets are logged in recovery path (OPENAI_API_KEY not logged).
