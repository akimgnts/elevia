# ESCO → Canonical Skills Mapping Plan

**Date:** 2026-05-02  
**Goal:** Bridge CV (ESCO URIs) ↔ Offers (canonical_ids) for scoring V2  
**Status:** PLANNING

---

## Current State

### Profile (CV) Side
- **Skills format:** ESCO URIs (e.g., `http://data.europa.eu/esco/skill/123`)
- **Source:** ESCO extraction pipeline (extractors.py → skills_uri frozenset)
- **No mapping:** CV skills stay in ESCO namespace

### Offer Side
- **Skills format:** canonical_ids (e.g., `metier:python`, `metier:negotiation`)
- **Source:** canonical_skills table (1,968 skills with 4,385 aliases)
- **Mapping available:** fact_offer_skills(skill_uri) → canonical_aliases(alias) → canonical_skills(canonical_id)

### Matching Pipeline
- MatchingEngine compares profile.skills_uri ↔ offer.skills_uri
- Currently: ESCO vs metier:* — **NO OVERLAP** (different namespaces)
- Result: Matching fails, skills don't resolve

---

## Mapping Strategy

### Option A: ESCO → Canonical (Direct Label Mapping)
1. For each ESCO URI, extract skill label
2. Normalize ESCO label
3. Find match in canonical_aliases via fuzzy similarity
4. Map ESCO → canonical_id

**Pros:** Works with existing canonical_aliases table, no DB changes  
**Cons:** Fuzzy matching adds complexity, may miss semantic equivalences

### Option B: ESCO → Canonical (External ESCO Dictionary)
1. Load ESCO skill descriptions + definitions
2. Build semantic clustering (ESCO concepts → canonical roots)
3. Create explicit ESCO → canonical_id mapping table
4. Pre-compute at startup

**Pros:** Semantic accuracy, reusable mapping  
**Cons:** Need ESCO skill dump, heavier maintenance

### Option C: ESCO → Canonical (Hybrid with Aliases)
1. ESCO label → canonical_aliases lookup (exact match)
2. If no match, use fuzzy similarity + domain context
3. Fall back to ESCO concept root (e.g., "python" from ESCO → canonical "python")

**Pros:** Combines accuracy + coverage  
**Cons:** More logic

---

## Recommended: Option C (Hybrid)

### Phase 1: Audit
- [ ] Extract all ESCO URIs from fact_offer_skills (profile history or fixtures)
- [ ] Count unique ESCO skills
- [ ] Cluster by concept root (python, sql, data, etc.)
- [ ] Identify unmappable ESCO skills

### Phase 2: Implement Mapping
- [ ] Add ESCO → canonical_id lookup function
- [ ] Integrate into extract_profile() or matching pipeline
- [ ] Test: 1 CV with fixture ESCO skills vs sample offers

### Phase 3: Validation
- [ ] Compare ESCO→canonical mapping accuracy
- [ ] Measure coverage (% of ESCO skills mapped)
- [ ] Verify no false positives (wrong matches)

### Phase 4: Wire into Scoring V2
- [ ] Update MatchingEngine to use canonical skills
- [ ] Verify scoring V2 works with canonical_ids
- [ ] Test full inbox flow

---

## Deliverables

1. **esco_canonical_mapper.py** — ESCO → canonical_id lookup
2. **esco_canonical_mapping.json** (optional) — Pre-computed mapping
3. **Integration point** — Where to wire into extract_profile
4. **Test suite** — ESCO→canonical validation

---

## Timeline

- Phase 1 (audit): ~1h
- Phase 2 (implement): ~2h
- Phase 3 (validate): ~1h
- Phase 4 (integrate): ~30m

Total: ~4.5h

---

## Risk: ESCO Coverage

If ESCO doesn't have all skills in canonical_skills:
- Map what you can, leave unmappable ESCO as fallback
- Log unmappable skills for manual review
- Plan Phase 3 expansion if needed

**Not critical:** Matching works even with partial ESCO coverage. Better to be conservative than to force false mappings.
