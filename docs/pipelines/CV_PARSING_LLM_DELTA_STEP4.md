# CV Parsing LLM Delta (Step 4)

## Purpose
Compare A vs A+B for the same CV input.
- A = deterministic parsing pipeline (existing).
- A+B = the same pipeline plus an optional LLM enrichment step.

We compare A vs A+B (not A vs B) to keep the deterministic baseline intact and measure incremental value.

## How To Run
Deterministic (A only):
- `./.venv/bin/python apps/api/scripts/cv_parsing_delta_report.py --text apps/api/fixtures/cv_samples/sample_delta.txt`

With LLM (A+B):
- `./.venv/bin/python apps/api/scripts/cv_parsing_delta_report.py --text apps/api/fixtures/cv_samples/sample_delta.txt --with-llm --llm-provider openai --llm-model gpt-4o-mini`

Run tests:
- `./.venv/bin/python -m pytest apps/api/tests/test_cv_parsing_delta_report.py -q`

## Interpretation
- `added_skills` should contain relevant skills that were missed by deterministic parsing.
- `removed_skills` should be empty or near-zero (B should only add).
- `added_esco` shows new ESCO mappings unlocked by LLM-added skills.

## Tradeoffs
- LLM adds recall but may introduce noise; use the delta report to validate signal.
- A remains the deterministic baseline, and A+B is an optional enhancement.

## Caching + Determinism
- Cache key is `sha256(normalized_text + provider + model + max_skills + prompt_version)`.
- Cached results are stored under `apps/api/.cache/llm_delta/`.
- A remains deterministic. A+B is practically deterministic with temperature=0 and caching.

## Notes
- `OPENAI_API_KEY` is required only when running with `--with-llm`.
- Matching/scoring core is frozen and unaffected by this step.
