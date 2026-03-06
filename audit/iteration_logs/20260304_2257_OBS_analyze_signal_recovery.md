# OBS — Analyze Signal Recovery (Run & Verify)

Decisions
- Report test outcomes and provide manual verification steps.

Commands run + outputs
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_analyze_skill_recovery.py apps/api/tests/test_cluster_signal_policy.py apps/api/tests/test_offer_domain_signal_policy.py`
  - Result: 24 passed
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/web/tests/test_analyze_recovery_button.py apps/web/tests/test_analyze_error_mapping.py apps/web/tests/test_vite_proxy_analyze.py`
  - Result: 13 passed

Manual verification steps
- DEV: `/analyze` → click “Récupérer des compétences (IA)”
- Expect metrics panel with raw/candidates/recovered/noise/tech density
- Ensure legacy DEPRECATED banner only when legacy toggle ON

Action Plan
- None.

STATUS: ok
SCOPE: Observability - test outcomes + manual verification steps
PLAN: none
PATCH: none
TESTS: pytest (see commands)
RISKS: none
