# COMPASS vs ELEVIA — Audit Findings

**Date:** 2026-03-02
**Status:** RESOLVED (mitigations applied)

---

## Finding 1 — Compass E isolated from main CV pipeline (CRITICAL → RESOLVED)

**Severity:** Critical (before fix) → Resolved

**Description:**
`enrich_cv()` from `compass/cv_enricher.py` was implemented but never called by the main CV parse routes (`/profile/parse-file`, `/profile/parse-baseline`). Compass E enrichment was only accessible via the admin endpoint `POST /cluster/library/enrich/cv`, which is not called by the UI or the matching hot path.

**Grep proof:**
```
# Before fix: enrich_cv() was only called in:
apps/api/src/api/routes/cluster_library_api.py:    enrichment = enrich_cv(...)

# After fix: also called in:
apps/api/src/api/routes/profile_file.py:    enrichment = enrich_cv(...)
apps/api/src/api/routes/profile_baseline.py:    enrichment = enrich_cv(...)
```

**Code path before fix:**
```
POST /profile/parse-file
  → run_baseline()
  → detect_profile_cluster()
  → [no enrich_cv()]
  → response (no domain_skills_active)
```

**Code path after fix:**
```
POST /profile/parse-file
  → run_baseline()
  → detect_profile_cluster()
  → [enrich_cv() if ELEVIA_ENABLE_COMPASS_E=1]
  → response with domain_skills_active, pipeline_used tag
```

**Product risk:**
- Users could never see domain skill enrichment in the CV analysis UI despite Compass E being built
- cluster_library was never populated from real CV parse calls

**Mitigation:**
- Added `is_compass_e_enabled()` + `enrich_cv()` block to both parse routes
- Guarded by `ELEVIA_ENABLE_COMPASS_E` flag (default off) — zero impact on existing deployments
- Added `pipeline_used`, `compass_e_enabled`, `domain_skills_active`, `domain_skills_pending_count`, `llm_fired` fields to both response models

---

## Finding 2 — Two parallel LLM pipelines with overlapping purposes (MEDIUM → DOCUMENTED)

**Severity:** Medium (design ambiguity, not a bug)

**Description:**
Two separate LLM-based skill enrichment paths exist with different purposes but similar names:

| Path | Function | Location | Purpose | Output |
|------|----------|----------|---------|--------|
| Legacy | `suggest_skills_from_cv()` | `profile/llm_skill_suggester.py` | Adds ESCO-compatible token strings | Merged back into ESCO baseline tokens |
| Compass E | `call_llm_for_skills()` | `compass/llm_enricher.py` | Adds non-ESCO domain skills | `domain_skills_active` (display only) |

These serve **different purposes** and are **not** duplicates:
- Legacy path: expands the ESCO skill set (higher match coverage)
- Compass E path: surfaces non-ESCO signals (domain intelligence)

**Grep proof:**
```
# Legacy path invocations:
apps/api/src/api/routes/profile_file.py:    llm = suggest_skills_from_cv(cv_text)  [enrich_llm=1]
apps/api/src/api/routes/apply_pack.py:    suggest_skills_from_cv(...)             [enrich_llm=1]
apps/api/src/compass/canonical_pipeline.py: run_baseline_from_tokens(...)         [enrich_llm_legacy=True]

# Compass E path invocations:
apps/api/src/compass/cv_enricher.py:    call_llm_for_skills(...)                  [ELEVIA_ENABLE_COMPASS_E=1]
```

**Product risk:**
- Developer confusion: unclear which LLM path to use for new features
- Both can fire simultaneously if `ELEVIA_ENABLE_COMPASS_E=1` AND `enrich_llm=1` are both set

**Mitigation:**
- `enrich_llm=1` on `parse-file` now logs deprecation warning
- `canonical_pipeline.py` documents both paths and their distinct roles
- Long-term: remove `enrich_llm=1` path when Compass E is fully stable

---

## Finding 3 — pipeline_used field missing from parse responses (MEDIUM → RESOLVED)

**Severity:** Medium (observability gap)

**Description:**
Before this audit, `/profile/parse-file` and `/profile/parse-baseline` responses did not include a `pipeline_used` field. This made it impossible to determine from the API response which processing path was taken.

**Mitigation:**
- Added `pipeline_used: str` field to `ParseFileResponse` and `ParseBaselineResponse`
- Values: `"baseline"` | `"baseline+llm_legacy"` | `"baseline+compass_e"` | `"baseline+compass_e+llm"`

---

## Finding 4 — apply_pack.py uses legacy LLM path without deprecation warning (LOW → NOTED)

**Severity:** Low

**Description:**
`POST /apply-pack` calls `suggest_skills_from_cv()` directly without routing through `canonical_pipeline.py`. It does not log a deprecation warning.

**Product risk:**
- Low: `/apply-pack` is a separate use case (CV tailoring), not the main inbox flow
- No scoring impact

**Recommendation:**
Migrate `/apply-pack` to use `run_cv_pipeline(enrich_llm_legacy=True)` in a future sprint for consistency. No immediate action required.

---

## Finding 5 — No `pipeline_used` in inbox/analyze responses (LOW → NOTED)

**Severity:** Low (observability gap)

**Description:**
`POST /inbox` and the analyze view do not surface which CV parse pipeline was used. The profile's `pipeline_used` value from parse time is not persisted in the profile store.

**Product risk:**
- Ops cannot trace which pipeline version was used for a given inbox score
- Not critical while Compass E domain_skills_active is display-only

**Recommendation:**
Persist `pipeline_used` in the profile store as a metadata field in a future sprint.

---

## Score Invariance Audit

| Route | Reads score_core? | Writes score_core? | Modifies profile.skills before match? | Verdict |
|-------|------------------|-------------------|--------------------------------------|---------|
| /profile/parse-file | No | No | No | ✓ INVARIANT |
| /profile/parse-baseline | No | No | No | ✓ INVARIANT |
| /cluster/library/enrich/cv | No | No | No | ✓ INVARIANT |
| /v1/match | No | Produces score | N/A (is the scorer) | ✓ FROZEN |
| /inbox | No | No | No | ✓ INVARIANT |

**Conclusion:** `domain_skills_active` never enters the scoring path. Score invariance maintained across all findings.

---

## Summary

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | Compass E isolated from CV parse routes | Critical | RESOLVED |
| 2 | Two parallel LLM pipelines | Medium | DOCUMENTED |
| 3 | pipeline_used field missing | Medium | RESOLVED |
| 4 | apply_pack.py uses legacy path silently | Low | NOTED |
| 5 | pipeline_used not persisted in profile store | Low | NOTED |
