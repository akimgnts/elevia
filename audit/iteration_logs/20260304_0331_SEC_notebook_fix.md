# SEC — Notebook SystemExit Fix

Context
- Ensure no risky execution or secrets exposure in test fixes.

Findings
- Previous tests could trigger external calls or exit on import.
- No secret values were introduced or logged.

Actions
- Ensured env-gated tests short-circuit when credentials are missing.
- Avoided adding any new external calls or dynamic imports.

Files changed
- test_all_urls.py
- test_auth.py
- test_auth_token.py
- test_france_travail_final.py

Result
- No secret leakage; no new risky execution paths.

Next checks
- None.
