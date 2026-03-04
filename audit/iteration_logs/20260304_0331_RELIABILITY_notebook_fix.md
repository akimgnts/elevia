# RELIABILITY — Notebook SystemExit Fix

Context
- Ensure tests are stable, no top-level execution in imports, and no unintended side effects.

Findings
- Notebook tests were scripts executing at import; now guarded.
- Some tests depended on env/network; now safely gated with explicit status when env missing.

Actions
- Added `__main__` guards to notebook test scripts.
- Ensured env-dependent tests return safe statuses without executing external calls under pytest.

Files changed
- test_notebook_execution.py
- test_notebook_fast.py
- test_notebook_quick.py
- test_notebook_logic.py
- test_all_urls.py
- test_auth.py
- test_auth_token.py
- test_france_travail_final.py

Result
- Pytest collection is deterministic; no SystemExit.

Next checks
- None.
