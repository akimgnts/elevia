# V3 Extraction — Final Validation Report
**Date:** 2026-04-28  
**Status:** ✓ COMPLETE — READY FOR PRODUCTION

---

## Executive Summary

**V3 extraction (v3_metier + v3_fallback) is production-ready.** Delivers 99.67% offer coverage with 2.25× more skills per offer and dramatically higher quality (81% core domain skills vs 40% baseline).

---

## V1 vs V3 Comparison

| Metric | V1 (V2 Skills) | V3+Fallback | Improvement |
|--------|---|---|---|
| **Coverage** | 760/903 (84.2%) | 900/903 (99.7%) | **+15.5pp** |
| **Avg skills/offer** | 1.93 | 4.35 | **+125%** |
| **Offers ≥3 skills** | 190/903 (21.0%) | 858/903 (95.0%) | **+74pp** |
| **CORE_METIER %** | ~40% | 81% | **+41pp** |
| **NOISE %** | ~15% | 0.8% | **-14.2pp** |

---

## Coverage Breakdown

| Component | Offers | Skills | Avg/offer | Status |
|-----------|--------|--------|-----------|--------|
| v3_metier | 853 | 3,779 | 4.43 | ✓ Primary |
| v3_fallback | 47 | 136 | 2.89 | ✓ Safety net |
| **Total** | **900** | **3,915** | **4.35** | ✓ **99.67%** |
| Uncovered | 3 | 0 | 0 | Edge case |

---

## Quality Metrics

### V3 Skill Type Distribution
- **CORE_METIER:** 3,163 skills (81%) ✓ Domain expertise
- **TOOL:** 463 skills (12%) ✓ Practical competencies
- **CONTEXT:** 256 skills (7%) ✓ Business framing
- **NOISE:** 33 skills (0.8%) ✓ Minimal junk

### Richness Examples (Top Offers)
```
 1. BUSINESS ANALYST/MOA           : +4 skills (1→5)
 2. Chargé de HSE                  : +3 skills (2→5)
 3. INGÉNIEUR EMBARQUÉ LINUX       : +5 skills (0→5)
 4. D&IS Product Marketing          : +4 skills (1→5)
 5. Contrôleur de gestion          : +4 skills (1→5)
```

---

## Validation Checklist

### Data Integrity
- [x] No duplicate (offer_id, canonical_id, enrichment_version) rows
- [x] No null canonical_ids
- [x] All evidence grounded in offer text
- [x] All skill_types valid (CORE_METIER, TOOL, CONTEXT, NOISE only)

### Constraint Compliance
- [x] v3_metier: 3-5 skills per offer (94.46% coverage)
- [x] v3_fallback: 1-3 skills per offer (max constraint enforced)
- [x] Evidence mandatory on all 3,915 skills
- [x] CORE_METIER ≥70% (v3_metier: 80.76%) ✓
- [x] NOISE <2% (v3_fallback: 0%, v3_metier: 0.87%) ✓
- [x] No v3_metier modification (separate enrichment_version)
- [x] Fallback idempotent (skip if v3 exists)

### Coverage Goals
- [x] Base target (90%): **Exceeded at 99.67%**
- [x] Minimum ≥3 skills (80%): **Exceeded at 95.33%**
- [x] CORE_METIER dominated: **81% (target ≥70%)**

### Edge Cases
- [x] 3 uncovered offers = company-profile text (Vorwerk, STMicroelectronics, APMS)
- [x] Correct behavior to reject (avoid hallucination)
- [x] Acceptable edge cases

---

## Impact Assessment

### Matching Quality
- **V1:** Profile matches limited by sparse skills (avg 1.93/offer)
- **V3:** Rich skill sets enable better matching
  - 95% of offers now queryable on ≥3 candidate skills
  - Domain taxonomy (CORE_METIER) enables semantic matching
  - TOOL/CONTEXT add nuance (salary, tech stack, environment)

### Ranking Robustness
- **V1 risk:** Low scores due to skill sparsity, random-looking results
- **V3 benefit:** Consistent, rich signals. Better signal-to-noise ratio.

### Fallback Effectiveness
- **47 offers rescued** (5.2% additional coverage)
- **Avg 2.89 skills/offer** (reasonable for edge cases)
- **100% evidence validation** (no AI hallucination)

---

## Recommendation

**✓ DEPLOY TO PRODUCTION**

1. **Data Ready:** 99.67% coverage, 3,915 high-quality skills
2. **Quality Validated:** 81% CORE_METIER, 0.8% NOISE, 100% evidence grounded
3. **Constraints Met:** All v3_metier and v3_fallback rules enforced
4. **Backward Compatible:** Separate enrichment_version, no changes to matching_v1.py
5. **Scoring Impact:** Neutral (no scoring logic changed, only skill catalog enriched)

### Next Steps
1. Enable V3 in inbox scoring (toggle ELEVIA_MATCHING_VERSIONS or scoring gate)
2. A/B test v3 ranking against v1 on real user profiles
3. Monitor the 3 uncovered offers (may reappear after description updates)
4. Retire v2 skills extraction once v3 proven in production

---

## Sign-Off

✓ V3 metier + fallback extraction 100% complete  
✓ 99.67% offer coverage achieved (900/903 offers)  
✓ All quality checks passed (3,915 skills, 100% evidence)  
✓ Constraints enforced on both v3_metier and v3_fallback  
✓ Data integrity verified (0 duplicates, 0 nulls)  
✓ 2.25× richer skill signals vs V1 baseline  
✓ Ready for production integration

**Full extraction pipeline operational and validated.**
