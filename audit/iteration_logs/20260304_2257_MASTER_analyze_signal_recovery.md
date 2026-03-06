# MASTER — Analyze Signal Recovery (Signal-first)

Summary
- Added deterministic cluster signal policy and wired it into AI recovery and offer domain token pipeline.
- Analyze recovery now prefilters candidates and returns stats for DEV panel.
- Offer domain tokens are filtered deterministically before URIs and Top-K.

Root cause
- Recovery inputs were raw ignored/noise tokens without deterministic prefilter or cluster signal policy, so important signals could be drowned by noise and offers lacked symmetric filtering.

Patch
- New module: `apps/api/src/compass/cluster_signal_policy.py`
- Recovery route uses candidates_for_ai and returns stats fields.
- Offer canonicalization applies the same filter before domain URIs.
- Analyze UI shows DEV-only recovery metrics panel.

Tests
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/api/tests/test_analyze_skill_recovery.py apps/api/tests/test_cluster_signal_policy.py apps/api/tests/test_offer_domain_signal_policy.py`
- `/tmp/elevia_smoke_venv/bin/python -m pytest apps/web/tests/test_analyze_recovery_button.py apps/web/tests/test_analyze_error_mapping.py apps/web/tests/test_vite_proxy_analyze.py`

Manual verification
- DEV: `/analyze` → click “Récupérer des compétences (IA)” → metrics panel shows raw/candidates/recovered/noise/tech.
- Ensure “DEPRECATED enrich_llm=1 …” banner only shows when legacy toggle is ON.

Next actions
- None required for this phase.
