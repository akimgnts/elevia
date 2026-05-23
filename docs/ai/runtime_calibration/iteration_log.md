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

### 2026-05-11 — sentinel baseline replay — no patch
- Verdict before:
  - `nawel`: pending
  - `ania`: pending
  - `dia`: pending
  - `akim_audit`: pending
  - `mouissetheo`: pending
- Main false positives:
  - to be filled after human reading of `latest_sentinel_replay.md`
- Dominant cause hypothesis:
  - baseline observation only
- Patch scope:
  - none
- Replay result after:
  - baseline only
- Regressions on other sentinels:
  - not applicable
- Decision:
  - establish benchmark baseline

### 2026-05-19 — ania — finance -> policy/privacy/data
- Verdict before:
  - `ania`: `mauvais`
- Main false positives:
  - `VIE - Quality Engineer - Zalaegerszeg`
  - `VIE - Global Digital Policy - Brussels`
  - `Analyste SOC`
- Dominant cause hypothesis:
  - `skill:compliance` promoted two transverse runtime ESCO URIs and amplified non-finance overlap on top of the existing DATA_IT halo.
- Patch scope:
  - narrow `skill:compliance` bridge from two runtime ESCO URIs to one
- Replay result after:
  - `ania`: `discutable`
  - `Quality Engineer` remains top 1, but its overlap drops from 2 compliance URIs to 1
  - finance offers remain dominant across ranks `2`, `3`, `4`, `7`, `8`, `9`, `10`
  - `Global Digital Policy` and `Analyste SOC` still appear, but behind a denser finance block
- Regressions on other sentinels:
  - none observed
- Active sentinel replay matrix:
  - `nawel`: `stable`
  - `ania`: `pass`
  - `dia`: `stable`
  - `akim_audit`: `stable`
  - `mouissetheo`: `stable`
- Decision:
  - keep patch; residual drift is now primarily the DATA_IT halo, not the compliance bridge alone

### 2026-05-19 — ania — finance -> policy/privacy/data (DATA_IT halo)
- Verdict before:
  - `ania`: `discutable`
- Main false positives:
  - `VIE - Quality Engineer - Zalaegerszeg`
  - `VIE - Global Digital Policy - Brussels`
  - `Analyste SOC`
- Dominant cause hypothesis:
  - profile-side `domain_library_uri` for `DATA_IT` admitted four transverse generic tokens (`analyse`, `analyste`, `coordination`, `relations`) that amplified non-finance overlap into policy/SOC.
- Patch scope:
  - in `build_domain_uris_for_text()`, block only those four tokens when `cluster == DATA_IT`
- Replay result after:
  - `ania`: `discutable`
  - `Global Digital Policy` and `Analyste SOC` leave the top 10
  - finance offers now occupy ranks `2` through `9`
  - residual false positives remain: `Quality Engineer` top 1 and `DATA SCIENTIST` rank 10
- Regressions on other sentinels:
  - none observed
- Active sentinel replay matrix:
  - `nawel`: `stable`
  - `ania`: `pass`
  - `dia`: `stable`
  - `akim_audit`: `stable`
  - `mouissetheo`: `stable`
- Decision:
  - keep patch; next drift is no longer policy/SOC for `ania`, but residual transverse quality/data noise
