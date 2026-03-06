# FEAT — ESCO Promotion Mapping (Step 2)

STATUS: ok
SCOPE: Feature & Contract - ESCO promotion mapping
PLAN: none
PATCH: new promotion module + integration in parse routes
TESTS: pytest apps/api/tests/test_esco_promotion_mapping.py apps/api/tests/test_esco_promotion_scaffold.py
RISKS: none (flag-gated)

Decisions
- Use strict ESCO mapping with alias-first + exact label lookup (no fuzzy).
- Integrate at parse-file and parse-baseline where candidate labels are available.
- Flag-gated via ELEVIA_PROMOTE_ESCO; when OFF, no profile changes.

Files changed
- apps/api/src/compass/promotion/aliases.py (new)
- apps/api/src/compass/promotion/esco_promotion.py (new)
- apps/api/src/api/routes/profile_file.py
- apps/api/src/api/routes/profile_baseline.py
- apps/api/tests/test_esco_promotion_mapping.py (new)

Commands run
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_esco_promotion_mapping.py apps/api/tests/test_esco_promotion_scaffold.py`

Action Plan
- None.
