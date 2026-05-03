# FACT_OFFER_SKILLS Quality Audit

**Date**: 2026-05-03  
**Status**: NOT_READY  
**Conclusion**: Insufficient canonical skills coverage for reliable matching

---

## 1. Executive Summary

`fact_offer_skills` contains 144,714 skill records across 839 distinct offers, but data quality is poor:

- **Only 1.47%** (2,132 rows) mapped to `metier:*` canonical IDs
- **94.81%** (136,697 rows) are NULL/empty (parsing garbage)
- **3.72%** (5,383 rows) contain legacy ESCO URIs
- **0%** plain text/unmapped valid skills

**Verdict**: Offers lack sufficient canonical skills for CV↔offer matching. Current data cannot power reliable skill-based recommendations.

---

## 2. Global Metrics

| Metric | Value |
|--------|-------|
| **Total skill records** | 144,714 |
| **Distinct offers** | 839 |
| **Distinct skill_uri values** | 241 |
| **Avg skills per offer** | 172.48 |
| **% metier:* URIs** | 1.47% |
| **% ESCO URIs** | 3.72% |
| **% NULL/empty** | 94.81% |
| **% Plain text** | 0.00% |

---

## 3. Garbage Analysis

**Unmapped garbage skills**: 137,199 rows (94.81% of total)

### Pattern Breakdown

Most garbage is **2-character fragments** from broken tokenization:

| Pattern | Count | Examples |
|---------|-------|----------|
| **2-char codes** | ~15,000+ | `we`, `it`, `qu`, `up`, `us`, `se`, `si`, `il`, `bi`, `ms`, `ai` |
| **Abbreviations** | ~3,000 | `cv`, `hr`, `3d`, `fr`, `qa`, `qa`, `qa` |
| **Technical codes** | ~500 | `b1`, `c1`, `b2`, `c2`, `v5`, `5g`, `5s` |
| **Measurements** | ~50 | `10m`, `15m`, `180o`, `100m`, `km`, `mm` |
| **Short fragments** | ~1,000 | Single letters + common words |

### Top 50 Garbage Examples

```
we (204)     | it (193)     | qu (141)     | up (137)     | us (127)
se (119)     | si (89)      | il (77)      | bi (62)      | ms (62)
ai (61)      | ll (60)      | re (53)      | ne (49)      | b2 (48)
c1 (47)      | if (45)      | ad (41)      | tu (36)      | cv (32)
ia (32)      | hr (30)      | ve (30)      | 3d (27)      | fr (27)
cd (26)      | ca (25)      | rh (25)      | es (24)      | qa (22)
so (22)      | co (21)      | ex (21)      | go (21)      | no (21)
b1 (17)      | eu (14)      | ta (13)      | 5s (12)      | he (12)
```

**Interpretation**: Offers were extracted via naive text tokenization without skill validation. No filtering for minimum length or semantic validity.

---

## 4. Canonical Skills Quality (metier:*)

**Metier rows**: 2,132 (1.47% of total)  
**Distinct canonical skills**: 68  
**Coverage**: Heavily skewed toward languages and generic tools

### Top 30 Canonical Skills

| Rank | Skill | Count | Type |
|------|-------|-------|------|
| 1 | english_language_proficiency | 292 | TOOL |
| 2 | aveva_pi_setup_and_reporting | 206 | CORE_METIER |
| 3 | contr_le_qualit | 179 | CORE_METIER |
| 4 | excel | 148 | TOOL |
| 5 | french_language_proficiency | 128 | TOOL |
| 6 | ing_nierie | 125 | CORE_METIER |
| 7 | cmms_support_for_maintenance_tasks | 107 | CORE_METIER |
| 8 | project_management | 81 | CONTEXT |
| 9 | power_bi | 73 | TOOL |
| 10 | erp | 68 | TOOL |
| 11 | python | 63 | TOOL |
| 12 | sap | 53 | TOOL |
| 13 | recrutement | 46 | CORE_METIER |
| 14 | autocad | 38 | TOOL |
| 15 | data_analysis | 36 | CORE_METIER |
| 16 | azure | 35 | TOOL |
| 17 | docker | 34 | TOOL |
| 18 | procurement | 33 | CORE_METIER |
| 19 | n_gociation | 29 | CORE_METIER |
| 20 | java | 27 | TOOL |

### Skill Type Distribution

| Type | Distinct Skills | Total Occurrences | % |
|------|-----------------|-------------------|---|
| TOOL | 51 | 1,208 | 56.6% |
| CORE_METIER | 13 | 800 | 37.5% |
| CONTEXT | 4 | 124 | 5.8% |

### Domain Tag Distribution (Top 15)

| Domain | Skills | Occurrences |
|--------|--------|-------------|
| domain_specific | 36 | 563 |
| tools | 20 | 548 |
| languages | 2 | 420 |
| finance | 1 | 206 |
| engineering | 1 | 125 |
| soft_skills | 3 | 116 |
| data | 3 | 113 |
| supply_chain | 1 | 33 |
| sales | 1 | 8 |

**Finding**: Language skills (420 occurrences) dominate. Tech skills (python, java, docker) appear in only ~150 rows total. Canonical coverage is **extremely narrow** for matching.

---

## 5. Offer Quality Analysis

### Verdict Distribution

| Category | Count | % |
|----------|-------|---|
| **PARTIAL** (≥1 metier:*) | 761 | 90.7% |
| **DIRTY** (0 metier:*) | 78 | 9.3% |
| **CLEAN** (≥3 metier:* + ≥1 CORE_METIER) | 0 | 0.0% |

**Finding**: Zero "clean" offers. Even offers with metier:* skills don't meet minimum quality threshold.

### Breakdown by Metier Skills

| Metier Skills Count | Offers | % |
|---------------------|--------|---|
| 0 | 78 | 9.3% |
| 1 | ~300 | ~35.7% |
| 2 | ~200 | ~23.8% |
| 3+ | ~261 | ~31.1% |

Only ~31% of offers have ≥3 canonical skills. Most are dominated by language skills, not job-specific competencies.

---

## 6. Sample Offer Review (30 Offers)

### Patterns Observed

**PARTIAL offers (with some metier:*):**
- Most have 1-5 canonical skills
- Heavy garbage contamination (60-95% null skills)
- Canonical skills biased toward languages + generic tools
- Example: `BF-236095` (Business Controller) has only 2 metier:* (`excel`, `english_language_proficiency`) + 166 garbage rows

**Tech-focused offers (rare):**
- `BF-238426` (Business Developer): 3 CORE_METIER + 231 garbage (95.8% garbage ratio)
- `BF-238445` (Dev .NET): 5 metier:* (`docker`, `azure`, `.net`) + only 41 garbage = **BEST CASE** but still 73% garbage

**French labels appear:**
- `contr_le_qualit`, `ing_nierie`, `n_gociation`, `gestion_de_projet` all mapped successfully
- Shows canonical_aliases covers French variants

**Non-tech offers (majority):**
- Business managers, consultants, coordinators
- Skills: languages + generic project management
- No tech tools, frameworks, or specialized competencies
- Examples: VIE Finance, Approval Planner, HR roles

---

## 7. Verdict & Recommendations

### Root Cause Analysis

1. **Data extraction failure**: Offers tokenized naively without skill validation
   - 95% garbage rate indicates broken parsing pipeline
   - No minimum length checks (allows "we", "it", "qu")

2. **Semantic mismatch**: Offer catalog is mostly non-tech roles
   - 839 offers, but only 261 (31%) have ≥3 tech-related canonical skills
   - Language proficiency (420 occurrences) != job skills

3. **Backfill coverage limitation**: 0.5% mapping rate not a bug
   - Only 73 of 15,083 manual skills mapped (rest is garbage)
   - Backfill worked correctly; underlying data is the problem

4. **Canonical dictionary gap**: Only 68 distinct skills in metier:*
   - Missing: specialized tools, frameworks, methodologies
   - Heavy bias toward generic TOOL and CONTEXT categories

### Can Matching Work Now?

**NO.** Offers lack sufficient canonical skills to match CV profiles.

- **CV side**: Works well (17+ skills extracted per comprehensive CV, 95% coverage)
- **Offer side**: Critically weak (avg 2-3 canonical skills per offer, mostly languages)
- **Overlap potential**: Very low for tech profiles

### Recommendations

1. **Do NOT enable skill-based matching yet**
   - Current offer coverage insufficient (0% "clean" offers)
   - Will produce incoherent results

2. **Fix data quality (high effort)**
   - Re-extract offers with proper skill validation
   - Implement minimum length filters
   - Use canonical_aliases for entity linkage during extraction
   - Target: ≥70% garbage reduction, ≥30 skills per offer

3. **Expand canonical dictionary (medium effort)**
   - Add 50+ missing tech tools (javascript, typescript, etc. already added)
   - Add domain-specific skills by role type
   - Target: 500+ distinct canonical skills

4. **Alternative path: Defer skill matching**
   - Use job title similarity + location + compensation for initial ranking
   - Add skill matching as secondary signal later
   - Implement A/B test to measure impact

---

## 8. Data Quality Scorecard

| Dimension | Score | Status |
|-----------|-------|--------|
| **Coverage** | 1.47% | 🔴 CRITICAL |
| **Garbage Ratio** | 94.81% | 🔴 CRITICAL |
| **Canonical Quality** | 68 skills | 🟡 LIMITED |
| **Offer Completeness** | 0% "clean" | 🔴 CRITICAL |
| **Tech Skills Density** | ~2-3 per offer | 🔴 CRITICAL |

**Overall Status**: NOT_READY ❌

---

## Appendix: Sample Offers with Verdicts

| Offer | Title | Metier Count | Garbage % | Verdict |
|-------|-------|--------------|-----------|---------|
| BF-238426 | International Business Developer | 3 CORE_METIER | 95.8% | PARTIAL |
| BF-238445 | Développeur .NET | 5 | 73.2% | PARTIAL |
| BF-238373 | Digital Sales Manager Portugal | 1 CORE_METIER | 92.6% | PARTIAL |
| BF-240151 | Talent Acquisition Manager | 2 | 96.8% | PARTIAL |
| BF-237405 | Industrial Injection Engineer | 3 | 98.2% | PARTIAL |
| BF-236315 | Business Analyst | 1 CORE_METIER | 93.2% | PARTIAL |
| BF-238377 | Transfers Work Coordinator | 5 | 93.3% | PARTIAL |
| BF-237523 | Technicien Projet Neuf | 0 | 96.3% | DIRTY |
| BF-235596 | Ingénieur Technico-Commercial | 0 | 95.2% | DIRTY |
| BF-238376 | Consultant Métier Finance | 0 | 93.7% | DIRTY |

---

**Report Generated**: 2026-05-03  
**Auditor**: Automated Quality Audit  
**Next Review**: After data pipeline improvements
