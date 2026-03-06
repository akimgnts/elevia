# QA — ESCO Promotion Mapping (Step 2)

STATUS: ok
SCOPE: Quality Assurance - promotion mapping
PLAN: none
PATCH: new tests + existing scaffold
TESTS: pytest apps/api/tests/test_esco_promotion_mapping.py apps/api/tests/test_esco_promotion_scaffold.py
RISKS: none

Tests run
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_esco_promotion_mapping.py apps/api/tests/test_esco_promotion_scaffold.py`

Results
- 25 passed
