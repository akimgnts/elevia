# Iteration Log

This file is append-only.

## Usage Rules
- One entry per calibration iteration.
- One triggering sentinel case per entry.
- One dominant drift family per entry.
- Every iteration must replay the triggering sentinel before and after the patch.
- Every iteration must replay all active sentinels for regression check.
- Regression checks must list every replayed active sentinel explicitly by id.
- Each replayed sentinel must record one status: `pass`, `stable`, or `regressed`.
- The triggering sentinel evidence must record both the before and after verdict explicitly.
- If diagnosis is incomplete, log that outcome explicitly instead of forcing a patch.

## Template

### YYYY-MM-DD — <sentinel id> — <drift family>
- Verdict before:
- Main false positives:
- Dominant cause hypothesis:
- Patch scope:
- Replay result after:
- Regressions on other sentinels:
- Active sentinel replay matrix:
  - `<sentinel id>`: `pass|stable|regressed`
- Decision:
