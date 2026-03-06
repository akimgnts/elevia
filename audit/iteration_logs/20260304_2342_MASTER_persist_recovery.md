# MASTER — Persist Analyze Recovery (Determinism + Cache)

What changed
- Added SQLite cache keyed by (profile_fingerprint, request_hash).
- Added extracted_text_hash + profile_fingerprint to parse-file response.
- Added request_hash + cache_hit + ai_fired to recover-skills response.
- Enforced deterministic ordering of recovered skills.
- Analyze UI now reuses cached results and disables recovery button unless forced (DEV).

Commands run + results
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_analyze_skill_recovery.py apps/api/tests/test_cluster_signal_policy.py apps/api/tests/test_offer_domain_signal_policy.py apps/api/tests/test_analyze_recovery_cache.py`
  - Result: 27 passed
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/web/tests/test_analyze_recovery_button.py apps/web/tests/test_analyze_error_mapping.py apps/web/tests/test_vite_proxy_analyze.py`
  - Result: 14 passed

Proof (determinism + cache)
- Test `test_cache_hit_on_second_call` asserts:
  - first call cache_hit=false, ai_fired=true
  - second call cache_hit=true, ai_fired=false
  - recovered_skills identical (diff empty)

Files changed
- apps/api/src/api/utils/analyze_recovery_cache.py
- apps/api/src/api/routes/analyze_recovery.py
- apps/api/src/compass/analyze_skill_recovery.py
- apps/api/src/api/routes/profile_file.py
- apps/web/src/lib/api.ts
- apps/web/src/pages/AnalyzePage.tsx
- apps/api/tests/test_analyze_recovery_cache.py
- apps/api/tests/test_analyze_skill_recovery.py
- apps/web/tests/test_analyze_recovery_button.py

Scoring core
- Untouched (matching_v1.py/idf.py/weights_* unchanged).

Next action for Akim
- In DEV, upload once, click recovery; refresh and confirm "Déjà récupéré" with cache_hit=true.
