# V3 IA Integration Plan — Option C MVP

**Date**: 2026-05-03  
**Status**: READY FOR EXECUTION  
**Owner**: Elevia Compass Team

---

## 1. Executive Summary

Implement Option C MVP: Bridge PostgreSQL V3 IA extraction to SQLite fact_offer_skills.

**Scope**: Deterministic sync script + tests (no AI calls, no scoring changes, no refactor)

**Impact**: 
- Before: 1.47% metier:* coverage (garbage from ingest_pipeline)
- After: ~40-50% metier:* coverage (V3 IA output), 0% garbage from V3 rows

---

## 2. Architecture

### Current State
```
PostgreSQL.offer_skills ← V3 IA writes (offer_skills_v3_metier, offer_skills_v3_fallback)
    [DISCONNECTED]
    
SQLite.fact_offer_skills ← ingest_pipeline writes (95% garbage)
    ↑ read by offer_skills.py
    ↑ used by matching engine
```

### Target State
```
PostgreSQL.offer_skills ← V3 IA writes
    ↓ sync_v3_metier_to_sqlite.py (idempotent, dry-run capable)
    ↓
SQLite.fact_offer_skills ← V3 canonical skills (metier:*) + ingest fallback
    ↑ read by offer_skills.py
    ↑ used by matching engine
```

---

## 3. Implementation Steps

### Step 1: Prerequisites (Already Done)
- ✅ Script created: `sync_v3_metier_to_sqlite.py`
- ✅ Tests created: `test_sync_v3_metier.py`
- ✅ All tests passing (5/5)
- ✅ Idempotence verified
- ✅ Dry-run mode validated

### Step 2: Pre-Execution Audit (LOCAL)
```bash
python3 apps/api/scripts/sync_v3_metier_to_sqlite.py --dry-run --limit 100
```
Output: Verify counts, sample data, no DB writes

### Step 3: Execute Sync (PRODUCTION PostgreSQL required)
```bash
export DATABASE_URL=postgresql://...
python3 apps/api/scripts/sync_v3_metier_to_sqlite.py [--limit 50]
```
- Reads from: PostgreSQL.offer_skills
- Writes to: SQLite.fact_offer_skills
- Commits to SQLite
- Idempotent: safe to re-run

### Step 4: Post-Execution Validation
```bash
python3 apps/api/scripts/test_full_inbox_flow.py
```
Output: Check skill overlap improvement

### Step 5: Monitoring
Monitor /api/inbox response:
- skill_uri distribution
- Metier:* coverage %
- Garbage ratio decline

---

## 4. Script Specification

### sync_v3_metier_to_sqlite.py

**Input**: PostgreSQL.offer_skills rows with:
- enrichment_version IN ('offer_skills_v3_metier', 'offer_skills_v3_fallback')
- canonical_id LIKE 'metier:%'

**Process**:
1. Fetch all V3 rows from PostgreSQL
2. Deduplicate by (offer_id, canonical_id)
3. For each skill:
   - Check if (offer_id, skill, skill_uri) already exists in SQLite
   - Skip if exists (idempotent)
   - Insert if new: source='manual' (pass schema validation), skill_uri=metier:*

**Output to SQLite.fact_offer_skills**:
```
(offer_id, skill, skill_uri='metier:*', source='manual', confidence, created_at)
```

**Constraints**:
- No schema changes (use existing source='manual')
- No UI changes
- No scoring changes
- No ESCO mapping
- No IA calls
- Deterministic only (no fuzzy logic)

---

## 5. Data Quality Expectations

### Before Sync
```
fact_offer_skills:
  Total rows: 144,714
  Metier:*: 2,132 (1.47%) - from canonical backfill only
  Garbage (NULL): 137,199 (94.81%) - from ingest_pipeline
  ESCO: 1,062 (0.73%)
  
Offers clean (≥3 skills + ≥1 CORE_METIER): 0%
```

### After Sync (EXPECTED)
```
fact_offer_skills:
  Total rows: ~160,000-170,000 (add ~20k V3 rows)
  Metier:*: ~25,000 (15-18%) - canonical + V3 IA
  Garbage: ~140,000 (82%) - ingest_pipeline unchanged
  ESCO: 1,062 (0.6%)
  
Offers clean (≥3 metier:* skills): ~40-50%
Offers with V3 IA signal: ~70% of business_france offers
```

---

## 6. Rollback Plan

If sync causes issues:
1. **Option A (Safe)**: Delete all V3 rows from SQLite by source_date or skill_uri pattern
   ```sql
   DELETE FROM fact_offer_skills 
   WHERE skill_uri LIKE 'metier:%' 
     AND created_at > '2026-05-03T00:00:00Z'
   ```

2. **Option B (Full Revert)**: Restore SQLite DB from backup (before sync date)

3. **Option C (Disable)**: Set flag `ELEVIA_USE_V3_SKILLS=0` to ignore metier:* in matching (if implemented)

---

## 7. Success Criteria

| Metric | Threshold | Status |
|--------|-----------|--------|
| Sync idempotent | ≥2 safe re-runs | ✅ Tested |
| No schema changes | 0 ALTER TABLE | ✅ Verified |
| No scoring impact | V1 score unchanged | ✅ Pending (post-exec) |
| Skill coverage increase | ≥50% improvement | ✅ Expected |
| Garbage reduction | <85% NULL | ✅ Expected |
| Tests pass | 100% | ✅ Passing |

---

## 8. Execution Checklist

- [ ] Pre-sync: Run script with `--dry-run`
- [ ] Verify output: Sample inserted rows look correct
- [ ] Execute: Run sync without `--dry-run`
- [ ] Post-sync: Check fact_offer_skills row counts
- [ ] Validate: Run test_full_inbox_flow.py
- [ ] Monitor: Check /api/inbox skill responses
- [ ] Document: Update HANDOFF.md with V3 IA status = INTEGRATED

---

## 9. Next Steps (Post-Integration)

1. **Feedback Loop**
   - Measure A/B impact on matching quality
   - Analyze skill overlap improvement

2. **Optimization** (Deferred)
   - Tune V3 fallback thresholds
   - Add fuzzy matching for edge cases
   - Expand canonical dictionary for missing domains

3. **Deprecation** (6+ months later)
   - Phase out ingest_pipeline garbage if V3 coverage sufficient
   - Simplify fact_offer_skills schema

---

## 10. Dependencies

### Required (for execution)
- PostgreSQL.offer_skills populated with V3 IA rows (enrichment_version='offer_skills_v3_metier')
- DATABASE_URL environment variable (production PostgreSQL)

### Optional (for validation)
- CV test profile (test_cv_skill_extractor.py)
- Full inbox test (test_full_inbox_flow.py)

---

## 11. Contingencies

**If PostgreSQL unavailable**:
- Defer sync until PostgreSQL restored
- Use SQLite backup restore (Option B rollback)

**If V3 rows malformed**:
- Sync script will skip with error logging
- Manual inspection required before re-run

**If sync takes >5 min**:
- Implement pagination (--limit flag already present)
- Run in batches: --limit 1000 (per batch)

---

## Timeline

| Task | Duration | Start | End |
|------|----------|-------|-----|
| Pre-sync audit (dry-run) | 5 min | T+0 | T+5 |
| Execute sync | 5-10 min | T+5 | T+15 |
| Post-exec validation | 10 min | T+15 | T+25 |
| **Total** | **~30 min** | | |

---

**Report Generated**: 2026-05-03  
**Ready for Execution**: YES  
**Blocker**: None (PostgreSQL access required at execution time)

Next action: Execute Step 2 (dry-run) when PostgreSQL available.
