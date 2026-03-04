# FEAT — Notebook SystemExit Fix

Context
- Full pytest failed during collection with `SystemExit: 0` from `test_notebook_execution.py`.

Findings
- `test_notebook_execution.py` (and related notebook test files) executed CLI-style code at import time and called `sys.exit(0)`.
- Pytest imports test modules during collection, so top-level `SystemExit` aborts collection.
- Several notebook-related test files were scripts rather than pytest tests.

Actions
- Refactored notebook test scripts to be proper pytest tests:
  - Moved execution into `run_*()` functions returning status code.
  - Added `test_*()` functions asserting return codes.
  - Added `if __name__ == "__main__": raise SystemExit(run_*())` guards.
- Aligned ancillary CLI-style tests to be safe in pytest by gating on env and dry-run when missing.

Files changed
- test_notebook_execution.py
- test_notebook_fast.py
- test_notebook_quick.py
- test_notebook_logic.py
- test_all_urls.py
- test_auth.py
- test_auth_token.py
- test_france_travail_final.py
- docs/archive/anotea/test_anotea_integration.py
- apps/api/src/compass/cluster_library.py
- apps/api/tests/test_parse_file_enriched.py

Result
- No `SystemExit` during collection; tests execute as pytest tests.

Next checks
- Full pytest run to confirm no regressions.
