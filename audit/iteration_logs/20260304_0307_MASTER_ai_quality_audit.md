# MASTER — AI Quality Audit

## Root cause initial
We lacked measurable evidence of whether AI recovery reduces noise or improves cluster signal; no audit metrics existed.

## Hypothesis measured
Recovered AI skills that overlap with cluster offers indicate meaningful signal; non-overlapping skills suggest noise.

## Results observed
- Audit endpoint returns deterministic metrics: overlap count, coherence %, noise ratio.
- No changes to matching or scoring core.
- DEV-only visibility in Analyze UI.

## Recommendation
- Keep AI skills display-only until coherence is consistently > 70%.
- Prefer mapping AI suggestions to ESCO where possible.
- Reject or downrank AI output when noise_ratio_estimate > 0.5.

## Tests
- /tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_ai_quality_audit.py
- /tmp/elevia_smoke_venv/bin/python -m pytest apps/web/tests/test_analyze_recovery_button.py apps/web/tests/test_vite_proxy_analyze.py apps/web/tests/test_analyze_error_mapping.py
- /tmp/elevia_smoke_venv/bin/python -m pytest  (FAILED: test_notebook_execution.py SystemExit)
