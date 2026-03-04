# MASTER — Analyze AI Recovery Fix

## Root cause
- UI error mapping allowed `IA indisponible : undefined` when error_code was missing or fetch failed.
- Legacy deprecation warnings could surface in non-legacy flows if warnings were displayed unfiltered.
- Invalid request payloads returned generic FastAPI 422 shape (no stable error_code).

## Patch summary
- Frontend: robust error mapping (UNKNOWN_ERROR / NETWORK_ERROR / AI_DISABLED), and warnings filter to hide legacy deprecation unless legacy toggle is enabled.
- Backend: add targeted RequestValidationError handler for /analyze/recover-skills returning `INVALID_REQUEST`.
- Tests: backend invalid-request test + frontend static test preventing undefined and enforcing fallback codes.

## Tests
- /tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_analyze_skill_recovery.py
- /tmp/elevia_smoke_venv/bin/python -m pytest apps/web/tests/test_analyze_recovery_button.py apps/web/tests/test_vite_proxy_analyze.py apps/web/tests/test_analyze_error_mapping.py

## Checklist
- [x] No “IA indisponible : undefined”
- [x] Legacy banner only appears when legacy toggle enabled
- [x] Recovery uses cluster + ignored/noise tokens only
- [x] Stable error_code/error_message contract
- [x] No scoring core changes

