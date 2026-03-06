# FEAT — Analyze Signal Recovery (Design)

Decisions
- Add deterministic `cluster_signal_policy` module to pre-filter recovery candidates and offer domain tokens.
- Keep API additive: new stats fields only; no breaking changes.

Proposed module
- Path: `apps/api/src/compass/cluster_signal_policy.py`
- Functions:
  - `normalize_token(token: str) -> str`
  - `build_candidates_for_ai(cluster, ignored_tokens, noise_tokens, validated_esco_labels, max_candidates=60) -> {candidates, dropped, stats}`
  - `filter_offer_domain_tokens(cluster, tokens) -> {kept, dropped, stats}`
- Deterministic allow/block lists per cluster (seeded for DATA_IT, MARKETING_SALES, FINANCE_LEGAL) + generic heuristics.

API impact (additive)
- `/analyze/recover-skills` response to include:
  - `raw_count`, `candidate_count`, `dropped_count`, `noise_ratio`, `tech_density`, `dropped_reasons` (optional counts)
- No scoring core changes.

Files targeted
- `apps/api/src/compass/cluster_signal_policy.py` (new)
- `apps/api/src/api/routes/analyze_recovery.py` (integrate candidates + stats)
- `apps/api/src/compass/analyze_skill_recovery.py` (accept candidates for AI only)
- `apps/api/src/compass/offer_canonicalization.py` (apply filter to domain tokens)
- `apps/web/src/pages/AnalyzePage.tsx` (DEV panel metrics + IA pills)

Action Plan
- Implement deterministic filtering and add tests.
- Ensure “DEPRECATED enrich_llm=1” banner is only shown when legacy toggle is ON.

STATUS: ok
SCOPE: Feature & Contract - design only
PLAN: implement deterministic prefilter + additive response stats
PATCH: none (design)
TESTS: add unit tests for cluster policy + offer symmetry
RISKS: none (additive fields)
