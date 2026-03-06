# MASTER — ESCO Promotion Mapping (Step 2)

What changed
- Added strict ESCO promotion module with alias pack and deterministic normalization.
- Integrated promotion at parse-file and parse-baseline to populate `skills_uri_promoted` when flag ON.
- Added tests for mapping, dedup, cap, and determinism.

Commands run + results
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_esco_promotion_mapping.py apps/api/tests/test_esco_promotion_scaffold.py`
  - Result: 25 passed

Proof (determinism)
- `test_deterministic_ordering` asserts identical output + sorted order for same input.

Files changed
- apps/api/src/compass/promotion/aliases.py
- apps/api/src/compass/promotion/esco_promotion.py
- apps/api/src/api/routes/profile_file.py
- apps/api/src/api/routes/profile_baseline.py
- apps/api/tests/test_esco_promotion_mapping.py

Scoring core untouched
- matching_v1.py, idf.py, weights_* unchanged.

Next action for Akim
- Set `ELEVIA_PROMOTE_ESCO=1` in local env and re-parse a CV to see `skills_uri_promoted` in profile payload.
