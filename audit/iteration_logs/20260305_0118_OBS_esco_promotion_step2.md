# OBS — ESCO Promotion Mapping (Step 2)

STATUS: ok
SCOPE: Observability - debug logging only
PLAN: none
PATCH: logger.debug counts in promotion
TESTS: none
RISKS: none

Findings
- Promotion module logs candidate/promoted/rejected counts via logger.debug; no endpoint changes.

Files reviewed
- apps/api/src/compass/promotion/esco_promotion.py
