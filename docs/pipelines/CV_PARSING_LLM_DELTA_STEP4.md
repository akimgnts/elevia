# CV Parsing LLM Delta Step 4

## Purpose
Compare A vs A+B for the same CV input.
- A is the deterministic parsing pipeline.
- A+B is the same pipeline plus an optional LLM enrichment step.

## Why A vs A+B Matters
A remains the deterministic baseline used for stability.
A+B shows incremental signal without changing the baseline behavior.

## How To Run
From repo root:
```
source .venv/bin/activate
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q apps/api/tests/test_cv_parsing_delta_report.py -vv
python apps/api/scripts/cv_parsing_delta_report.py --text apps/api/fixtures/cv_samples/sample_delta.txt
python apps/api/scripts/cv_parsing_delta_report.py --text apps/api/fixtures/cv_samples/sample_delta.txt --with-llm --llm-provider openai --llm-model gpt-4o-mini
```

From apps/api:
```
cd apps/api
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_cv_parsing_delta_report.py -vv
python scripts/cv_parsing_delta_report.py --text fixtures/cv_samples/sample_delta.txt
python scripts/cv_parsing_delta_report.py --text fixtures/cv_samples/sample_delta.txt --with-llm --llm-provider openai --llm-model gpt-4o-mini
```

Repo root test note:
If you run pytest from repo root and hit import issues, either cd apps/api or use
```
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -c apps/api/pytest.ini apps/api/tests/test_cv_parsing_delta_report.py -vv
```

## Interpretation
- added_skills should contain relevant skills that were missed by deterministic parsing.
- removed_skills should be empty or near zero because A+B only adds.
- added_esco shows new ESCO mappings unlocked by LLM added skills.

## Tradeoffs
- LLM adds recall but may introduce noise, use the delta report to validate signal.
- A remains the deterministic baseline, and A+B is an optional enhancement.

## Caching and Determinism
- Cache key is sha256 of normalized_text + provider + model + max_skills + prompt_version.
- Cached results are stored under apps/api/.cache/llm_delta.
- A remains deterministic, A+B is practically deterministic with temperature 0 and caching.

## Troubleshooting
- If pytest says file not found, run pwd, inspect pytest rootdir, and use the correct path.
- If pytest import hangs, follow docs/infra/PYTEST_IMPORT_HANG_FIX.md and move the repo out of iCloud.
- If LLM is enabled without OPENAI_API_KEY, the script prints a warning and runs A only.

## Notes
- OPENAI_API_KEY is required only when running with --with-llm.
- Matching and scoring core is frozen and unaffected by this step.
