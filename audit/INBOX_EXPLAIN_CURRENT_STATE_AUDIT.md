# Current /Inbox Explain Output Audit

**Date**: 2026-05-03  
**Scope**: Explainability payload structure & quality  
**Focus**: Is the data there? Is it clear?

---

## Executive Summary

Audit of `/inbox?explain=true` output to assess if explanations are:
1. Present (data exists)
2. Clear (human-readable)
3. Complete (all needed context)
4. Actionable (user understands why match happened)

**Status**: ✅ **Data present** | ⚠ **Clarity needs work** | ⚠ **Organization can improve**

---

## 1. Current Explain Schemas

### A. ExplainBlock (Detailed, Debug-friendly)

**Purpose**: Full technical breakdown per offer  
**Location**: `InboxItem.explain` (when `explain=true`)

**Structure**:
```python
explain:
  matched_display: List[SkillExplainItem]     # Top 6 matched (for card)
  missing_display: List[SkillExplainItem]     # Top 6 missing (for card)
  matched_full: List[SkillExplainItem]        # All matched (max 30)
  missing_full: List[SkillExplainItem]        # All missing (max 30)
  
  # Categorized by importance
  matched_core: List[SkillExplainItem]
  missing_core: List[SkillExplainItem]
  matched_secondary: List[SkillExplainItem]
  missing_secondary: List[SkillExplainItem]
  matched_context: List[SkillExplainItem]
  missing_context: List[SkillExplainItem]
  
  # Score breakdown
  breakdown: ExplainBreakdown
    - skills_score: 40.5
    - language_score: 10.0
    - education_score: 5.0
    - country_score: 0.0
    - total: 55.5 (pre-rounding)
  
  # Near-match signals
  near_matches: List[NearMatchItem]
  near_match_count: int
```

**Assessment**:
- ✓ COMPREHENSIVE (all data present)
- ✓ STRUCTURED (categorized by importance)
- ⚠ OVERWHELMING (too many lists, might confuse users)
- ⚠ TECHNICAL (score breakdown is mathematical, not narrative)

### B. OfferExplanation (Clean, Front-ready)

**Purpose**: Human-friendly summary  
**Location**: Could be derived from ExplainBlock + scoring context

**Structure**:
```python
explanation:
  score: 55
  fit_label: "Strong Match"
  summary_reason: "You have 5 of 8 core Python skills..."
  strengths: ["Python expert", "React experience", ...]
  gaps: ["Docker", "Kubernetes"]
  blockers: []
  next_actions: ["Learn Docker for full fit"]
```

**Assessment**:
- ✓ CLEAR (narrative format)
- ✓ ACTIONABLE (suggests next steps)
- ⚠ NOT YET IMPLEMENTED (doesn't exist in current /inbox response)

### C. OfferIntelligence (Role context)

**Purpose**: Understand what role this offer represents  
**Location**: `InboxItem.offer_intelligence`

**Structure**:
```python
offer_intelligence:
  dominant_role_block: "DATA_IT"
  secondary_role_blocks: ["ENGINEERING_INDUSTRY"]
  dominant_domains: ["Analytics", "Backend"]
  required_skills: ["SQL", "Python"]
  optional_skills: ["Spark", "Tableau"]
  offer_summary: "Data engineer role handling ETL pipelines..."
  role_hypotheses: [
    {"label": "Data Engineer", "confidence": 0.92},
    {"label": "Analytics Engineer", "confidence": 0.81}
  ]
```

**Assessment**:
- ✓ INFORMATIVE (context about role)
- ✓ PRESENT (populated in response)
- ⚠ TECHNICAL (internal role blocks might confuse users)

### D. SemanticExplainability (Alignment signals)

**Purpose**: NLP-based role/domain/signal alignment  
**Location**: `InboxItem.semantic_explain`

**Structure**:
```python
semantic_explain:
  role_alignment:
    profile_role: "Data Engineer"
    offer_role: "Data Analyst"
    alignment: "high"  # high|medium|low
  
  domain_alignment:
    shared_domains: ["Data", "Analytics"]
    profile_only_domains: ["ML"]
    offer_only_domains: ["BI Tools"]
  
  signal_alignment:
    matched_signals: ["data_analysis", "python"]
    missing_core_signals: ["machine_learning"]
  
  alignment_summary: "You and this role overlap significantly..."
```

**Assessment**:
- ✓ SEMANTIC (understands context)
- ✓ ALIGNED (shows domains & signals)
- ⚠ VERBOSE (summary might be long)

---

## 2. What's Currently Returned by /Inbox

### Populated Fields (As of audit date)

| Field | Present | Quality | Notes |
|-------|---------|---------|-------|
| `score` | ✓ | GOOD | 0-100, rounded |
| `title` | ✓ | GOOD | Offer title |
| `company` | ✓ | GOOD | Company name |
| `location` | ✓ | GOOD | City/country |
| `skill_overlap` | ✓ | GOOD | Integer count |
| `domain_affinity` | ✓ | GOOD | aligned/related/out |
| `explain.matched_display` | ✓ | GOOD | Top 6 matched skills |
| `explain.missing_display` | ✓ | MEDIUM | Top 6 missing skills |
| `explain.breakdown` | ✓ | TECHNICAL | Score breakdown by component |
| `explain.matched_core` | ✓ | GOOD | CORE skills that matched |
| `explain.missing_core` | ✓ | GOOD | CORE skills that don't exist |
| `offer_intelligence` | ✓ | MEDIUM | Role hypothesis, required_skills |
| `semantic_explain` | ✓ | MEDIUM | Role/domain alignment |
| `rome_link` | ✓ | TECHNICAL | ROME occupation code |
| `scoring_v2` | ✓ | TECHNICAL | Debugging only |
| `scoring_v3` | ✓ | TECHNICAL | Debugging only |

### NOT Currently Present

- ❌ `explanation.summary_reason` (clean text "why")
- ❌ `explanation.strengths` (highlighted positives)
- ❌ `explanation.gaps` (missing non-core skills)
- ❌ `explanation.blockers` (hard requirements not met)
- ❌ `explanation.next_actions` (how to improve fit)

---

## 3. User Experience Analysis

### User Goal
**"Why is this offer recommended to me?"**

### Current Flow (With explain=true)

```
User sees inbox response:
├─ score: 55 ← What does this mean?
├─ title: "Data Engineer" ← Understand offer
├─ explain.matched_display: [Python, SQL, Excel]
│  └─ User: "OK, I have these skills"
├─ explain.missing_core: [Spark, Scala]
│  └─ User: "Hmm, I'm missing these"
├─ explain.breakdown:
│  ├─ skills_score: 45
│  ├─ language_score: 10
│  └─ [Math equations...]
│     └─ User: "Lost in the numbers"
└─ domain_affinity: "aligned"
   └─ User: "But what domain?"
```

**User Journey**:
1. ✓ Gets score (but unclear why)
2. ✓ Sees matched skills (good)
3. ✓ Sees missing skills (good)
4. ✗ Confused by score breakdown (too technical)
5. ✗ Doesn't understand domain connection
6. ✗ Doesn't know what to do next

### Quality Assessment

**Rating by Criterion**:

| Criterion | Status | Evidence |
|-----------|--------|----------|
| "Why recommended?" | ❌ MISSING | No narrative reason |
| "What matched?" | ✓ GOOD | matched_display clear |
| "What's missing?" | ✓ GOOD | missing_core clear |
| "How close am I?" | ⚠ MEDIUM | Score present but not explained |
| "What's the role?" | ⚠ MEDIUM | Role present but jargon-heavy |
| "What do I do next?" | ❌ MISSING | No action items |
| "Is score fair?" | ❌ MISSING | Only math, no justification |

---

## 4. Useful vs Useless Fields

### ✓ USEFUL (Keep visible)

1. **Score (0-100)** — Simple, actionable
2. **Matched skills (top 6)** — Immediate relevance
3. **Missing core skills** — Clear gap analysis
4. **Skill overlap count** — Quantifies match
5. **Domain affinity** — Contextual signal
6. **Offer title** — What is the role?

### ⚠ MEDIUM (Keep but simplify)

7. **Offer intelligence** — Required skills list (yes), role hypotheses (too technical)
8. **Semantic explain** — Alignment summary (good), technical alignment (debugging)
9. **ROME link** — Useful for career planning, not match explanation

### ✗ TECHNICAL (Hide by default)

- `explain.breakdown` — Score math (for debugging only)
- `explain.matched_full` — All 30 matched (overwhelming)
- `explain.missing_full` — All missing (too long)
- `scoring_v2/v3` — Internal signal details
- `explain.near_matches` — Complex concept
- `compass_explain` — Internal structure

---

## 5. Missing Elements for Complete Explanation

### Missing Narrative

**What's needed**:
```
"You're a good match because:
 • You have 5 of 8 core Python/SQL skills (62% coverage)
 • Your data analysis experience aligns with the role
 • You're missing Docker/Kubernetes (nice-to-haves)

To improve this match:
 • Learn Docker containerization (will unlock 15% more offers)
 • Get Spark experience (common in similar roles)
"
```

**Currently**: Only data, no story.

### Missing Actionability

**What's needed**:
- Clear next steps (e.g., "Learn Docker")
- Impact of learning (e.g., "+15% match fit")
- Priority ranking (Core vs Secondary skills)

**Currently**: Shows gaps, no guidance.

### Missing Context

**What's needed**:
- Why is Python "core"? (Industry standard)
- Why is Docker "secondary"? (Nice-to-have)
- Industry context for the role

**Currently**: Just lists, no "why".

---

## 6. Recommendations by Scenario

### Scenario A: User reads on mobile (quick decision)

**Needs**:
- Score (do I qualify?)
- Top 3 matched skills
- Top 1-2 missing core skills
- 1-line why (domain match)

**Current explain complexity**: TOO HIGH  
**Current format**: Lists work, but overwhelming

**Fix**: Create "compact" mode with 5-field summary.

### Scenario B: User researches offer (deep dive)

**Needs**:
- Full skill breakdown (matched vs missing, by importance)
- Role hypothesis with confidence
- Industry alignment
- Learning path to improve fit

**Current explain complexity**: PARTIALLY MET  
**Current format**: Data exists but scattered

**Fix**: Organize ExplainBlock fields + add narrative layer.

### Scenario C: Recruiter uses as feedback tool

**Needs**:
- Why was candidate shortlisted?
- What skills are in demand?


- What's the gap analysis?

**Current explain complexity**: GOOD for this use case  
**Current format**: Technical fields sufficient

**Fix**: No change needed (internal use).

---

## 7. Status Assessment

### Data Availability

**Overall**: ✅ **COMPREHENSIVE**

- ✓ Matched skills: present in 3+ formats (display, full, core/secondary)
- ✓ Missing skills: present in 3+ formats
- ✓ Score breakdown: mathematically complete
- ✓ Role context: offer intelligence populated
- ✓ Semantic signals: role/domain/signal alignment present

### Clarity for End User

**Overall**: ⚠ **NEEDS SIMPLIFICATION**

- ❌ No narrative reason (just data)
- ❌ No actionable guidance (what to do next?)
- ⚠ Score breakdown too technical (why 55 vs 45?)
- ⚠ Role jargon not explained (what is "DATA_IT"?)
- ✓ Skill lists clear when not overwhelming

### Completeness

**Overall**: ⚠ **PARTIAL (75%)**

Data present: 75%
- Missing: narrative reason (-15%)
- Missing: next actions (-10%)

---

## 8. Implementation Path

### Option 1: Simplify (Fastest)
**Effort**: 2 hours  
**Approach**: Hide technical fields by default, show compact summary

```json
{
  "score": 55,
  "fit_label": "Good Match",
  "matched_skills_count": 5,
  "missing_core_count": 2,
  "domain_match": "aligned"
}
```

**Status**: QUICK IMPROVEMENT  
**Trade-off**: Less detail

### Option 2: Add Narrative Layer (Recommended)
**Effort**: 4 hours  
**Approach**: Generate `summary_reason` + `next_actions` from existing data

```python
# In compass/scoring/scoring_v2.py or new module:
def generate_offer_explanation(match_result) -> OfferExplanation:
    # Use existing matched_skills, missing_skills, score
    reason = f"You have {matched_count}/{total} {profile_skills}"
    next_actions = [generate_skill_priority(missing)]
    return OfferExplanation(
        score=score,
        summary_reason=reason,
        strengths=top_matched,
        gaps=missing_secondary,
        blockers=missing_core,
        next_actions=next_actions
    )
```

**Status**: GOOD BALANCE  
**Trade-off**: +4 hours dev, clearer UX

### Option 3: Restructure (Future)
**Effort**: 8 hours  
**Approach**: Redesign explain payload from scratch

```json
{
  "why_recommended": "You match on core skills",
  "headline": "5 of 8 core skills (62% fit)",
  "match_breakdown": {
    "core": {"matched": 5, "total": 8},
    "secondary": {"matched": 2, "total": 6}
  },
  "next_steps": ["Learn Docker", "Get Spark experience"]
}
```

**Status**: COMPREHENSIVE OVERHAUL  
**Trade-off**: Most effort, clearest UX

---

## 9. Data Reuse Assessment

### Can we reuse existing data?

**YES**: 80%+ of needed data is already computed:

```
✓ Matched skills:   explain.matched_core/secondary/context
✓ Missing skills:   explain.missing_core/secondary/context
✓ Score components: explain.breakdown (skills/language/education/country)
✓ Role context:     offer_intelligence.required_skills
✓ Semantic:         semantic_explain.alignment_summary

❌ Summary reason:  NOT COMPUTED (need to generate from above)
❌ Next actions:    NOT COMPUTED (need to derive from gaps)
```

### Effort to reuse

- **Reorganize existing fields**: 2 hours
- **Add text generation layer**: 4 hours
- **No new data sources needed**: ✓

---

## 10. Final Verdict

### Status: **NEEDS_SIMPLIFICATION** (Not "NOT_READY")

**Why not "NOT_READY"?**
- Data is present ✓
- Structure is sensible ✓
- Tests pass ✓
- Just needs UX layer

**Why not "READY"?**
- End user facing narrative missing ✗
- Action items missing ✗
- Technical fields mixed with user-facing ✗

### Recommended Action

**Build Option 2 (Add Narrative Layer)**:
1. Reuse all existing `explain.*` fields
2. Add text generation (`summary_reason`, `next_actions`)
3. Filter technical fields from default response
4. Keep debug fields available via query param

**Timeline**: 4 hours dev + 1 hour testing = **5 hours total**

**Impact**: 
- ✓ No scoring changes
- ✓ No matching changes
- ✓ Pure UX improvement
- ✓ Reuses 80% existing data

---

## 11. Validation Checklist

| Criterion | Current | After Option 2 | Notes |
|-----------|---------|-----------------|-------|
| User understands "why" | ❌ | ✓ | Narrative added |
| User knows next steps | ❌ | ✓ | Action items added |
| Data present | ✓ | ✓ | No change |
| Scoring unaffected | ✓ | ✓ | Display-only |
| Complexity | ⚠ | ✓ | Simplified layer |
| Mobile-friendly | ❌ | ✓ | Compact mode |
| Debugging support | ✓ | ✓ | Technical fields still there |

---

## Conclusion

**Current state**: Data is abundant, but presentation is raw.

**Action**: Don't rebuild, reformat. Reuse existing `explain.*` fields and add a narrative layer on top.

**Effort**: ~5 hours  
**Complexity**: Low (text generation + field filtering)  
**Risk**: Very low (display-only, no scoring impact)

**Status**: ✅ **Ready to implement Option 2**

**Next**: Add `OfferExplanation` builder that formats `ExplainBlock` for end users.

---

**Audit Date**: 2026-05-03  
**Status**: FINAL  
**Recommendation**: CODE - Add narrative layer (Option 2)
