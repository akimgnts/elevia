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
export ELEVIA_DEV_TOOLS=1
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q apps/api/tests/test_cv_parsing_delta_report.py -vv
python apps/api/scripts/cv_parsing_delta_report.py --text apps/api/fixtures/cv_samples/sample_delta.txt
python apps/api/scripts/cv_parsing_delta_report.py --text apps/api/fixtures/cv_samples/sample_delta.txt --with-llm --llm-provider openai --llm-model gpt-4o-mini
```

From apps/api:
```
cd apps/api
export ELEVIA_DEV_TOOLS=1
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_cv_parsing_delta_report.py -vv
python scripts/cv_parsing_delta_report.py --text fixtures/cv_samples/sample_delta.txt
python scripts/cv_parsing_delta_report.py --text fixtures/cv_samples/sample_delta.txt --with-llm --llm-provider openai --llm-model gpt-4o-mini
```

Repo root test note:
If you run pytest from repo root and hit import issues, either cd apps/api or use
```
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -c apps/api/pytest.ini apps/api/tests/test_cv_parsing_delta_report.py -vv
```

## Dev UI
From apps/web:
```
cd apps/web
npm install
npm run dev
```
Open the dev page at /dev/cv-delta

## API curl
TXT sample:
```
export ELEVIA_DEV_TOOLS=1
curl -X POST http://localhost:8000/dev/cv-delta \
  -F file=@apps/api/fixtures/cv_samples/sample_delta.txt \
  -F with_llm=false
```

PDF sample:
```
curl -X POST http://localhost:8000/dev/cv-delta \
  -F file=@/path/to/cv.pdf \
  -F with_llm=true \
  -F llm_provider=openai \
  -F llm_model=gpt-4o-mini
```

## PDF Error Codes (API)
When PDF parsing fails, the API returns 4xx with a structured error:
```
{ "error": { "code": "...", "message": "...", "hint": "...", "request_id": "..." } }
```
Common codes:
- PDF_PARSER_UNAVAILABLE: pypdf missing in API environment
- PDF_PARSE_FAILED: invalid or encrypted PDF
- PDF_TEXT_EMPTY: no extractable text found
- FILE_TOO_LARGE: >5MB
- UNSUPPORTED_FILETYPE: not PDF/TXT

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
- If PDF upload fails, check the error code and request_id in the response and inspect API logs.
- If `uvicorn api.main:app` fails with `ModuleNotFoundError: api` from `apps/api`, run from repo root (`make api`) or set `PYTHONPATH=apps/api/src`.

## Notes
- OPENAI_API_KEY is required only when running with --with-llm.
- Matching and scoring core is frozen and unaffected by this step.
