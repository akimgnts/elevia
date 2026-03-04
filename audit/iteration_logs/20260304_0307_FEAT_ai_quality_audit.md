# FEAT — AI Quality Audit

## Objective
Add a DEV-only AI quality audit module and endpoint to measure recovery impact without touching scoring core.

## Actions
- Added `analysis/ai_quality_audit.py` with `audit_ai_quality()`.
- Added DEV-only endpoint `POST /analyze/audit-ai-quality`.
- Added frontend API client + DEV-only UI panel to display metrics.

## Files touched
- apps/api/src/analysis/ai_quality_audit.py
- apps/api/src/api/routes/analyze_ai_quality.py
- apps/api/src/api/main.py
- apps/web/src/lib/api.ts
- apps/web/src/pages/AnalyzePage.tsx

## Risks
- Low. No matching/scoring changes; endpoint is DEV-only.

## Result
STATUS: ok
SCOPE: Feature & Contract - analysis module + analyze audit endpoint + UI panel
PLAN: none
PATCH: add ai_quality_audit + endpoint + UI button/panel
TESTS: /tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_ai_quality_audit.py
RISKS: none

## Next
- If audit metrics are used for decisions, document thresholds.
