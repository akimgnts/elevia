# QA — Persist Analyze Recovery

Context
- Added caching + determinism for AI recovery results.

Tests run
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_analyze_skill_recovery.py apps/api/tests/test_cluster_signal_policy.py apps/api/tests/test_offer_domain_signal_policy.py apps/api/tests/test_analyze_recovery_cache.py`
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/web/tests/test_analyze_recovery_button.py apps/web/tests/test_analyze_error_mapping.py apps/web/tests/test_vite_proxy_analyze.py`

Results
- Backend: 27 passed
- Frontend: 14 passed

Notes
- Cache hit verified by test: second call returns identical recovered_skills and cache_hit=true.

STATUS: ok
SCOPE: Quality Assurance - analyze recovery caching
PLAN: none
PATCH: new cache tests + updated frontend static test
TESTS: pytest (commands above)
RISKS: none
