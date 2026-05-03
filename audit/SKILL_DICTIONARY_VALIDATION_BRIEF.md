# Skill Dictionary — Validation Brief
**Date:** 2026-05-01  
**Status:** Ready for human review

---

## Summary

**Dictionnaire canonique construit à partir des V3 skills existantes (3,244 rows → 2,591 canonical skills).**

### Métriques clés

| Metric | Value | Notes |
|--------|-------|-------|
| Source skills (rows) | 3,244 | offer_skills V3 distinctes |
| Distinct labels | 3,223 | Uniques |
| Proposed canonical skills | 2,591 | À valider |
| Proposed aliases | 632 | Variantes groupées |
| Compression ratio | 1.24x | Modeste mais valide |
| Suspect classifications | 82 | À revoir |

### Distributions

| Type | Count | % |
|------|-------|---|
| CORE_METIER | 2,152 | 83.1% |
| TOOL | 269 | 10.4% |
| CONTEXT | 159 | 6.1% |
| NOISE | 11 | 0.4% |

---

## Top 10 Clusters (Importance × Frequency)

1. **data analysis** (43 occ)
   - Variantes: Data Analytics, data analysis and reporting, market data analysis, SQL data analysis, ...
   - Type: CORE_METIER
   - **Decision:** Merge OK

2. **international environment** (42 occ)
   - Variantes: International environments, environnement international (FR/EN)
   - Type: CONTEXT
   - **Decision:** Merge OK (+ note language normalization needed)

3. **customer relationship management** (36 occ)
   - Variantes: customer support, customer account growth, customer satisfaction, ...
   - Type: CORE_METIER
   - **Decision:** Check if "customer support" should be separate TOOL category

4. **Excel** (30 occ)
   - Variantes: Excel proficiency, advanced Excel, Excel file management
   - Type: TOOL
   - **Decision:** Merge OK (remove "excellence" false positives)

5. **client relationship management** (19 occ)
   - Variantes: B2B client relationship, relationship management
   - Type: CORE_METIER
   - **Decision:** Merge OK

6. **business development** (18 occ)
   - Variantes: B2B business development, business development activities
   - Type: CORE_METIER
   - **Decision:** Merge OK

7. **project management** (17 occ)
   - Variantes: Agile project management, project management expertise
   - Type: CORE_METIER
   - **Decision:** Merge OK

8. **technical documentation** (16 occ)
   - Variantes: technical documentation writing, technical documentation creation
   - Type: CORE_METIER
   - **Decision:** Merge OK

9. **English language proficiency** (15 occ)
   - Variantes: English, bilingual proficiency, technical English
   - Type: TOOL
   - **Decision:** Merge OK (Note: language skills may need separate domain_tag)

10. **market analysis** (15 occ)
    - Variantes: agricultural market analysis, market research
    - Type: CORE_METIER
    - **Decision:** Merge OK

---

## Critical Issues to Review

### Issue 1: "Excellence" System False Positives

**Problem:** Excel cluster includes:
- "Faurecia Excellence System methodologies"
- "operational excellence initiatives"
- "système d'excellence Hutchinson"

**Impact:** Inflates Excel cluster from ~20 to 30 occurrences

**Recommendation:** 
- Remove non-skill labels (company-specific excellence systems)
- Keep only: Excel, Excel proficiency, advanced Excel

**Action:** Manual split → separate `operational_excellence_system` skill

---

### Issue 2: Suspect Classifications (82 cases)

**Problem:** TOOL-like skills classified as CORE_METIER:
- "digital sales management" → CORE or TOOL?
- "C++ software development" → should be TOOL not CORE
- "SAP integration" → TOOL not CORE
- "Java application development" → TOOL not CORE

**Impact:** Scoring will weight these as domain skills, may inflate matches

**Recommendation:**
- Review heuristic: if label contains programming language or SaaS tool → TOOL
- Reclassify 15-20 cases from CORE to TOOL

**Action:** Generate reclassification proposal → validate with domain expert

---

### Issue 3: Language Mixing (EN/FR)

**Problem:** Same canonical skills exist in both languages:
- "international environment" + "environnement international" (duplicates)
- "développement commercial" (FR) vs "business development" (EN)
- "Négociation" (FR) + "contract negotiation" (EN)

**Impact:** Affects matching consistency (CV FR may not match offers EN)

**Recommendation:**
- Choose primary language (EN by default)
- Add FR as alias only
- Or create language-aware canonical_id (skill:en:data_analysis vs skill:fr:analyse_donnees)

**Action:** Standardize to EN except for French-only contexts

---

### Issue 4: Too Generic Labels

**Problem:** Skills too broad:
- "cross-functional collaboration" (NOISE) — 11 occ
- "continuous improvement" — appears in 7 variants
- "team management" vs "project management" (overlap)

**Impact:** Low signal-to-noise in matching

**Recommendation:**
- Mark generics explicitly (or move to soft-signals only)
- Domain tag = "soft-skills" for these
- Weight lower in scoring

**Action:** Create `domain_tag = "soft-skills"` category

---

## Decisions Awaiting Human Input

### Decision 1: Cluster Merging Threshold

**Question:** Should we cluster more aggressively (reduce to ~2,200) or stay conservative (~2,591)?

**Options:**
- A) Current (1.24x): Conservative, safer merges only
- B) Aggressive (1.36x): Merge more variants (threshold 0.60 instead of 0.65)
- C) Ultra-aggressive (1.50x): Merge very loose variants

**Recommendation:** **Option A (stay conservative)** — easier to split later than re-merge

---

### Decision 2: Language Normalization

**Question:** How to handle FR/EN mixing?

**Options:**
- A) Primary EN, FR as aliases (simplest)
- B) Language-aware canonical_id (skill:en:data_analysis vs skill:fr:analyse_donnees)
- C) Create separate FR dictionary (parallel)

**Recommendation:** **Option A** — implement language_tag field on aliases, default to EN

---

### Decision 3: Domain Tag Taxonomy

**Question:** What domain_tag values to use?

**Current proposal:**
- backend, frontend, data, devops, domain-specific (catch-all)
- Add: soft-skills, tools, languages

**Recommendation:** Expand to:
```
backend, frontend, data, devops, engineering, operations, sales, finance,
hr, legal, supply-chain, soft-skills, tools, languages, certifications
```

---

### Decision 4: Reclassification of Suspect Cases

**Question:** Approve reclassification of 82 suspected skills?

**Examples of proposed changes:**
- "digital sales management" CORE → TOOL ❌ (actually domain-specific, keep CORE)
- "C++ software development" CORE → TOOL ✓
- "Java application development" CORE → TOOL ✓
- "SAP integration" CORE → TOOL ✓

**Recommendation:** Generate detailed reclassification table, review ≥20 examples manually

---

## Next Steps

### Phase 1: Validate Dictionary (This Week)

- [ ] Human review of Top 50 canonical skills
- [ ] Approve cluster merges (or propose splits)
- [ ] Identify false positives (e.g., "excellence" systems)
- [ ] Decide language normalization approach
- [ ] Define domain_tag taxonomy

### Phase 2: Implement DB Tables (Next Week)

- [ ] Create `canonical_skills` table
  ```sql
  canonical_id (PK), label, skill_type, domain_tag, language (optional)
  ```
- [ ] Create `canonical_aliases` table
  ```sql
  alias, canonical_id (FK), confidence (optional)
  ```
- [ ] Backfill from JSON

### Phase 3: Test Integration (Before CV Parsing)

- [ ] Migrate offer_skills to reference canonical_ids
- [ ] Build CV parsing → canonical mapping layer
- [ ] Test fuzzy matching on sample CVs
- [ ] Measure matching quality vs V2

### Phase 4: ESCO Mapping (Before Production)

- [ ] Map ESCO URIs → canonical_ids
- [ ] Build CV profile normalization layer
- [ ] Test end-to-end CV → offers matching
- [ ] Validate against baseline

---

## Files Generated

1. **audit/SKILL_DICTIONARY_DRAFT.md** — Full report with top 50 + recommendations
2. **audit/skill_dictionary_draft.json** — Machine-readable canonical skills + aliases
3. **audit/SKILL_DICTIONARY_VALIDATION_BRIEF.md** — This file (decisions summary)

---

## Validation Checklist

- [x] All V3 skills extracted and deduplicated
- [x] Variants identified and clustered
- [x] Compression ratio calculated (1.24x)
- [x] Suspect classifications flagged (82 cases)
- [x] Source labels preserved (for traceability)
- [x] Occurrences aggregated correctly
- [ ] Human review of top clusters
- [ ] Domain tag taxonomy finalized
- [ ] Language normalization decided
- [ ] Reclassification approved

---

## Sign-Off

**Dictionary Status:** ✓ Analytically sound, ⏳ awaiting human validation

**Ready for:** Product/domain expert review before DB implementation

**Not ready for:** Production deployment (pending decisions above)

---

## Appendix: Uncertainty Zones

### High Confidence (Merge)
- Data analysis variants (25 → 1 canonical) ✓
- CRM variants (27 → 1 canonical) ✓
- Excel variants (12 → 1 canonical) ✓

### Medium Confidence (Review Suggested)
- Project management vs Agile (overlap?)
- Customer support vs CRM (different scopes?)
- Technical documentation variants (7 → need classification)

### Low Confidence (Keep Separate)
- SAP-specific skills (keep granular, domain-specific)
- Language-specific skills (EN vs FR contexts)
- Company-specific "excellence" systems (remove)

---

**Created:** 2026-05-01
**Source:** V3 metier + fallback extraction (899/903 offers, 3,915 skills)
**Compression:** 3,223 labels → 2,591 canonical (–632 aliases)
