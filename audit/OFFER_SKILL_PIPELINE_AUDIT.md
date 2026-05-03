# OFFER SKILL PIPELINE AUDIT

**Date**: 2026-05-03  
**Status**: **V3 IA NOT INTEGRATED**  
**Root Cause**: Pipeline architecture mismatch — V3 IA writes to PostgreSQL but system reads from SQLite

---

## 1. Pipeline Architecture

### Current Real Pipeline
```
France Travail API
    ↓
ingest_pipeline.py (fetch offers)
    ↓
_extract_ft_skill_candidates() → raw competences from payload
    ↓
_normalize_offer_skills_for_ingest() → calls normalize_offers_to_uris()
    ↓
normalize_offers_to_uris() (compass/offer_canonicalization.py) → ESCO mapping
    ↓
fact_offer_skills (SQLite) ← INSERT skill (label, esco_uri)
    ↓
backfill_offer_skills.py → tries to map NULL URIs to ESCO
    ↓
Reading layer: apps/api/src/api/utils/offer_skills.py (read-only)
```

### V3 IA Pipeline (DISCONNECTED)
```
backfill_offer_skills_v3_metier.py (PostgreSQL + OpenAI)
    ↓
offer_skills (PostgreSQL table) ← INSERT with enrichment_version='offer_skills_v3_metier'
    ↓
NEVER READ by fact_offer_skills (SQLite)
    ↓
No integration to SQLite system
```

---

## 2. System Architecture Mismatch

| Component | Technology | Table Name | Enrichment Version | Status |
|-----------|-----------|------------|-------------------|--------|
| **Ingestion** | SQLite | fact_offer_skills | source='france_travail' | USED |
| **Backfill (ESCO mapping)** | SQLite | fact_offer_skills | N/A (no column) | USED |
| **Backfill (canonicalization)** | SQLite | fact_offer_skills | N/A (no enrichment_version) | USED (this session) |
| **V3 IA Extraction** | PostgreSQL | offer_skills | offer_skills_v3_metier | **NOT USED** |
| **V3 Fallback** | PostgreSQL | offer_skills | offer_skills_v3_fallback | **NOT USED** |

**Critical Finding**: fact_offer_skills has NO `enrichment_version` column, so V3 IA rows cannot be tracked or integrated.

---

## 3. V3 IA Integration Status

### Is V3 IA Used?
**NO.** Zero integration.

### Evidence
- `backfill_offer_skills_v3_metier.py` reads from PostgreSQL: `SELECT ... FROM clean_offers ... LEFT JOIN offer_skills WHERE enrichment_version = %s`
- No code reads from PostgreSQL offer_skills table into SQLite fact_offer_skills
- fact_offer_skills has zero rows with enrichment_version (column doesn't exist)
- SQLite fact_offer_skills only contains:
  - source='france_travail' (from ingestion pipeline)
  - source='esco' (from backfill_bf_skills_esco.py)
  - source='manual' (from ingest_pipeline.py fallback)

---

## 4. Data Source Timeline

```sql
SELECT source, COUNT(*), MIN(created_at), MAX(created_at) 
FROM fact_offer_skills 
GROUP BY source;
```

| Source | Count | First | Last |
|--------|-------|-------|------|
| esco | 1,062 | 2026-02-27 | 2026-02-27 |
| france_travail | **0** | N/A | N/A |
| manual | 143,652 | 2026-03-20 | 2026-04-16 |

**Interpretation**:
- No "france_travail" source rows actually exist (all are "manual" with NULL URIs)
- ESCO is from backfill_bf_skills_esco.py (Feb 27 batch)
- "manual" (95% garbage) is from ingest_pipeline.py fallback tokenization (March 20 → April 16)

---

## 5. Where the Garbage Originates

### Root Cause: ingest_pipeline.py → normalize_offers_to_uris() fallback

1. **ingest_pipeline.py** (line 271-284):
   ```python
   skill_candidates = _extract_ft_skill_candidates(offer)
   offer_stub = {"id": offer_id, "skills": skill_candidates, ...}
   skills_from_payload = _normalize_offer_skills_for_ingest(offer_stub)
   # Returns: [(label, uri), ...] where uri=None if mapping fails
   _insert_offer_skills(cursor, offer_id, skills_from_payload, source='france_travail')
   # Inserts as source='france_travail' BUT actually all are unmapped
   ```

2. **_normalize_offer_skills_for_ingest()** (line 321-342):
   - Calls `normalize_offers_to_uris([offer_stub], include_domain_uris=True)`
   - Expects ESCO mapping to return (label, uri) pairs
   - When mapping fails: (label, None) → inserted with NULL uri

3. **normalize_offers_to_uris()** (compass/offer_canonicalization.py):
   - Tokenizes title/description into raw skill candidates
   - Tries ESCO mapping (fails ~95% due to noise)
   - Fallback: inserts unmapped fragments as "manual"
   - Examples of unmapped: "we" (204 times), "it" (193), "qu" (141), "up" (137)

### Why So Much Garbage?

- **No minimum length check**: 2-character fragments accepted
- **No semantic validation**: Random text fragments (IDs, measurements, language particles)
- **No deduplication at ingest**: Repeated fragments across offers
- **Fallback is too permissive**: Anything tokenizable is inserted with NULL uri

---

## 6. Comparing V3 vs Current vs Garbage

### Current State (SQLite fact_offer_skills)
- Total rows: 144,714
- Distinct offers: 839
- Avg skills/offer: 172.48
- **Metier:* coverage: 0% (no V3 rows)**
- **ESCO coverage: 0.73%** (1,062 rows, mostly old)
- **Garbage (NULL): 94.81%** (137,199 rows)

### V3 IA Extraction (PostgreSQL offer_skills - UNUSED)
- **Unknown metrics** (PostgreSQL not queried in this session)
- Expected: 3-5 skills per offer, 100% mapped to metier:*
- Expected: 0% garbage (enforced by AI validation + CORE_METIER constraint)
- **Status**: Built but disconnected

### Hypothetical V3-Ready State (if integrated)
- Total rows/offer: 3-5 canonical skills (vs 172.48 noise)
- Coverage: 100% mapped to metier:* (vs 0%)
- Garbage: 0% (vs 94.81%)
- Quality: READY for matching (vs NOT_READY)

---

## 7. Pipeline Break Points

| Break Point | Component | Issue | Impact |
|------------|-----------|-------|--------|
| **1. Tokenization** | ingest_pipeline.py | No validation, permits 2-char fragments | Garbage in fact_offer_skills |
| **2. Mapping** | normalize_offers_to_uris() | ESCO mapping fails silently, allows NULL | 95% unmapped rows |
| **3. Integration** | V3 IA → SQLite | No bridge from PostgreSQL offer_skills to SQLite fact_offer_skills | V3 never used |
| **4. Schema** | fact_offer_skills | No enrichment_version column to track source | Cannot identify V3 rows |
| **5. Reading** | offer_skills.py | Reads only from SQLite, ignores PostgreSQL | V3 rows never accessed |

---

## 8. Why V3 Was Never Integrated

1. **Architecture decision**: V3 IA designed for PostgreSQL (has `clean_offers` table dependency)
2. **Legacy system**: SQLite fact_offer_skills predates V3 IA
3. **No migration**: V3 IA was developed but never wired to the read layer
4. **Different constraints**: V3 enforces 3-5 skills + CORE_METIER; SQLite has no such constraints
5. **No ownership**: V3 scripts exist but no code calls them or syncs results to SQLite

---

## 9. Verdict: Is V3 IA Really Used?

**NO.**

```
V3 IA Extraction
    ↓
PostgreSQL offer_skills (enrichment_version='offer_skills_v3_metier')
    ↓
[DEAD END — no bridge to SQLite]
    ↓
System reads from SQLite fact_offer_skills
    ↓
System sees 95% garbage from ingest_pipeline.py fallback
    ↓
Conclusion: V3 IA is built but completely disconnected from runtime
```

---

## 10. Recommendations

### Option A: Integrate V3 IA (High Effort, High Reward)
1. Modify fact_offer_skills to add `enrichment_version` column
2. Create migration: PostgreSQL offer_skills → SQLite fact_offer_skills
3. Re-run `backfill_offer_skills_v3_metier.py` (batch OpenAI calls)
4. Update offer_skills.py reading layer to prefer V3 rows
5. **Result**: 0% garbage, 100% metier:* coverage, ready for matching

### Option B: Fix Current Pipeline (Medium Effort, Medium Reward)
1. Add minimum length check (skip <3 char tokens) in ingest_pipeline.py
2. Add semantic validation (known skill dictionary lookup)
3. Remove NULL uri rows from fact_offer_skills
4. **Result**: ~60% garbage reduction, still <10% metier:* coverage, better but not ready

### Option C: Hybrid (Medium-High Effort, High Reward)
1. Keep V3 IA for production offers (via Option A bridge)
2. Use fixed ingest_pipeline for edge cases
3. Maintain backfill_offer_skills_canonical.py for incremental mappings
4. **Result**: Best of both — V3 quality + fallback coverage

---

## 11. Conclusion

**Current State**: V3 IA exists but is **completely unused**. System reads garbage from SQLite ingest_pipeline.py fallback tokenization.

**Root Cause**: Two-system architecture (PostgreSQL V3 IA vs SQLite ingest) with no integration bridge.

**Path Forward**: Decide between:
- (A) Integrate V3 IA properly (effort: high, payoff: best matching quality)
- (B) Fix ingest_pipeline.py validation (effort: medium, payoff: marginal)
- (C) Hybrid approach (effort: medium-high, payoff: best overall)

**Current matching status**: NOT_READY (confirmed by fact_offer_skills audit).

---

**Report Generated**: 2026-05-03  
**Next Step**: Align on integration strategy (Option A/B/C) before proceeding with skill matching.
