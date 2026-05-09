# AUDIT COMPLET — Utilisation Réelle de l'IA dans Elevia Compass

**Date**: 2026-05-09  
**Scope**: Où, comment, à quel niveau l'IA est réellement utilisée  
**Méthodologie**: Pas de spéculation. Code + git log + STATE.json + WORKLOG.md + runtime analysis.

---

## PARTIE 1 — LOCALISATION DE TOUS LES APPELS IA

### AI_CALL_1: Structured CV Extraction (Phase 2 — ACTIF)

```
file: apps/api/src/compass/profile/structured_cv_extractor.py
function: extract_structured_cv(cv_text: str) → Optional[StructuredCV]
endpoint: POST /api/profile/parse-file
feature_flag: ELEVIA_STRUCTURED_CV_AI (runtime env check, default OFF)
model: gpt-4o-mini (configurable via ELEVIA_CV_STRUCTURER_MODEL)
provider: OpenAI
temperature: 0.2
timeout: 30 seconds
retry: None (fails → fallback)
fallback: Legacy deterministic parser
```

**Call site** (profile_parse_pipeline.py:344):
```python
structured_cv, structured_metadata = attempt_structured_cv_extraction(extraction.cv_text)
```

**Integration point** (line 386):
```python
enhanced_profile = enhance_profile_with_structured_cv(profile, structured_cv)
```

**Where used**:
- Merges into `career_profile.experiences`, `career_profile.projects`, `career_profile.education`, `career_profile.certifications`
- Adds `extracted_tools`, `extracted_companies`, `extracted_titles`, `extracted_languages`, `cv_quality`
- Response includes `structured_cv_metadata` with source tracking

---

### AI_CALL_2: Raw CV Reconstruction (IA1 — STUB + OPTIONAL PROVIDER)

```
file: apps/api/src/compass/ai_raw_cv_reconstruction.py
function: build_raw_cv_reconstruction(...) → RawCvReconstructionV1
feature_flag: ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION (default OFF)
model: gpt-4o (configurable via ELEVIA_AI_RAW_CV_MODEL)
provider: OpenAI (openai.OpenAI client)
temperature: Not specified in code
timeout: Configurable via ELEVIA_AI_RAW_CV_TIMEOUT
retry: No explicit retry (fails → fallback_raw_cv_reconstruction)
fallback: Original extracted text passed through with warning
activation_policy: "dirty CV" — enabled only if:
  - experiences == 0 AND
  - at least one weak signal true (structured_signal_units <= 3, validated_items <= 8, canonical_skills <= 15)
```

**Status**: Currently EXPERIMENTAL + UNVALIDATED for matching impact.  
STATE.json line 1294-1350: Last IA1 matching validation showed **ZERO matching improvement** for Nawel and Moustapha despite parsing gains.

**Where used**:
- Rebuilds CV text before deterministic parsing (if flag enabled)
- NOT merged into profile_intelligence or scoring
- NOT visible to frontend (logged only)
- Verdict (STATE.json line 1328-1345): "REMOVE" — parsing gains didn't translate to matching value

---

### AI_CALL_3: Profile Reconstruction (IA2 — PURE STUB, NO PROVIDER)

```
file: apps/api/src/compass/ai_profile_reconstruction.py
function: build_profile_reconstruction(input_data: Dict) → ProfileReconstructionV2
feature_flag: ELEVIA_ENABLE_AI_PROFILE_RECONSTRUCTION (default OFF)
model: None (no provider)
provider: None
status: STUB — deliberately does not infer or mutate data
```

**Code (line 46-58)**:
```python
return ProfileReconstructionV2(
    version="v2",
    source="ai2_stub",
    status="ok",
    suggested_summary=_empty_summary(),
    suggested_experiences=[],
    ...
    warnings=[{"code": "STUB", "message": "No provider connected"}],
)
```

**Impact**: ZERO. No IA calls, no data enrichment.

---

### AI_CALL_4: Legacy Profile Reconstruction (Frontend Deterministic)

```
file: apps/web/src/lib/profile/reconstruction.ts
function: buildProfileReconstruction(input)
type: Pure deterministic JavaScript (no LLM)
location: Frontend only (apps/web/src/pages/AnalyzePage.tsx)
purpose: Generate suggestions for UI display when user is editing profile
```

**Output** (stored as `profile.profile_reconstruction`):
- `suggested_summary` — from career_profile.summary_master if empty
- `suggested_skills` — from canonical_skills dedup
- `suggested_languages` — from career_profile.languages if empty
- `suggested_certifications` — from career_profile.certifications if empty
- `suggested_projects` — from career_profile.projects if empty (NOW FIXED: ProfileUnderstandingPage displays them)

**Where used** (ProfileUnderstandingPage.tsx):
- Displays as "Suggestions" only when corresponding career_profile field is empty
- Projection policy: fill-only-if-empty (no overwrite, no merging)

**Status**: DETERMINISTIC, NOT AI-powered

---

### AI_CALL_5: Apply Pack LLM Enricher (OPTIONAL)

```
file: apps/api/src/apply_pack/llm_enricher.py
type: Optional LLM enrichment (post-generation)
provider: OpenAI (gpt-4o-mini)
feature_flag: OPENAI_API_KEY must be set
fallback: Returns baseline + warning if LLM fails
```

**Where called**: apply_pack generation pipeline (optional, best-effort)  
**Impact**: Enriches CV text for job applications (add cover letter context)  
**Visibility**: Not exposed to main matching/profile pipeline

---

### AI_CALL_6: Compass LLM Enricher (OPTIONAL)

```
file: apps/api/src/compass/llm_enricher.py
type: Optional enrichment for profile structuring
provider: Multiple (Anthropic + OpenAI support)
```

**Status**: Unclear integration; minimal usage observed in current pipeline

---

### AI_CALL_7: Profile Intelligence (DETERMINISTIC, NO LLM)

```
file: apps/api/src/compass/profile/profile_intelligence.py
type: Pure deterministic scoring/classification
has_ai: NO
```

**Note**: Despite name, uses ZERO LLM. All keyword-based scoring.

---

## PARTIE 2 — INPUT RÉEL DE L'IA

### Input to Structured CV Extractor (PRIMARY AI CALL)

**Raw data received**:
```
cv_text: Full raw PDF-extracted text from user CV
Example: "DATA ENGINEER\nJohn Doe\n\nEXPERIENCE\n..."
```

**Prompt system** (structured_cv_extractor.py line 28-82):
```
"You are a professional CV parser. Extract structured information from CVs in strict JSON format.

RULES:
1. RESPOND ONLY WITH VALID JSON (no markdown, no explanation)
2. Never invent information not present in CV
3. Separate experiences from projects (projects = personal/academic work)
4. Responsibilities must describe job duties, NOT project titles
5. Skills should be contextual (attached to where they were used)
6. If unsure about a field, use empty string "" or empty list []
7. Keep original text formatting (no translation unless asked)"
```

**Prompt user**: Raw CV text (cv_text parameter)

**Schema demanded**:
```json
{
  "headline": "string",
  "target_role": "string",
  "summary": "string",
  "experiences": [{"title", "company", "dates", "location", "responsibilities", "tools", "skills"}],
  "projects": [{"name", "description", "tools", "skills"}],
  "education": [{"institution", "degree", "field", "dates", "location"}],
  "certifications": [{"name", "issuer", "date"}],
  "global_skills": ["skill1"],
  "languages": ["English - C1"],
  "warnings": ["warning text"]
}
```

**Constraints**:
- temperature=0.2 (very deterministic)
- max_tokens=4000
- timeout=30s
- Pydantic strict validation on response

**Understanding level**: EXTRACTION-ONLY, not comprehension.
- LLM is told to NOT invent
- LLM is told to separate concerns (experiences vs projects)
- But LLM is NOT asked to understand career trajectory, role fit, or industry context
- Pure data structure extraction, like a form-filling exercise

---

### Input to IA1 (Raw CV Reconstruction)

**Raw data**:
```
cv_text: Full extracted CV text (same as above)
```

**Prompt** (_build_raw_cv_reconstruction_prompt):
- Tells LLM to rebuild CV in normalized format
- Preserve content, light restructuring only
- No summarization or compression

**Schema**: RawCvReconstructionV1 with experiences[], projects[], skills[], confidence scores

**Understanding level**: RESTRUCTURING only, not analysis.
- LLM rewrites text to be more parseable for downstream deterministic parsers
- NOT asked to analyze role fit, seniority level, or domain expertise
- Pure text normalization

---

### Input to IA2 (Profile Reconstruction)

**Status**: STUB, no provider.
- No LLM is called
- Input accepted but ignored

---

## PARTIE 3 — OUTPUT RÉEL DE L'IA

### Structured CV Output (CALL 1)

**Raw LLM response**:
```json
{
  "headline": "Data Engineer",
  "experiences": [
    {
      "title": "Data Engineer",
      "company": "Acme Corp",
      "dates": "2023-2025",
      "responsibilities": ["Built ETL pipeline", "..."],
      "tools": ["Python", "SQL", "Spark"],
      "skills": ["Data engineering", "ETL"]
    }
  ],
  "projects": [
    {
      "name": "Personal ML Project",
      "description": "Trained recommendation model",
      "tools": ["Python"],
      "skills": ["Machine learning"]
    }
  ],
  ...
}
```

**Validation applied** (structured_cv_validator.py):
- Contamination detection: Are projects mixed into responsibilities?
- Company name leakage: Is company appearing in job titles?
- Date pattern detection: Correctly formatted month/year?
- False positive fix: Word boundaries on month patterns to avoid "marketing" → "March" false match

**Cleaning applied**:
- Projects[] separated from experiences[]
- Keywords checked against contamination patterns
- Validator rejects if contamination detected with warning

**Removed fields**: None at validation layer (validator passes/fails entirely)

**Ignored fields**: 
- LLM-generated `warnings` field (not used, validator creates its own)
- Anything beyond Pydantic schema is discarded

**Final structure** (ProfileStructuredV1):
```python
class Experience:
    title: str
    company: str
    dates: str
    location: str
    responsibilities: list[str]
    tools: list[str]
    skills: list[str]

class Project:
    name: str
    description: str
    tools: list[str]
    skills: list[str]

# Projects EXTRACTED into separate array
# Merged into career_profile.projects[]
# Experiences KEPT in career_profile.experiences[]
```

**What comes from IA**:
- ✅ Experiences with separated responsibilities
- ✅ Projects extracted from mixed content
- ✅ Tools and skills linked to context
- ✅ Education, certifications, languages

**What is reconstructed after IA**:
- CV quality metrics (cv_quality.py)
- Extracted tools aggregation
- Extracted companies list
- Extracted titles list
- Extracted languages list

---

### IA1 Output

**Status**: Experimental, no production value validated.
- Outputs restructured CV text
- Used as input to deterministic parser if enabled
- NOT exposed to frontend
- NOT visible to user

**From STATE.json (line 1294-1350)**:
```
Nawel KADI: parsing improved (0 exp → 4 exp) but ZERO matching impact
Moustapha: neutral, low gain
Decision: REMOVE — parsing gains didn't translate to matching value
```

---

### IA2 Output

**Status**: STUB
- Returns empty suggestions
- No data enrichment
- Warning: "No provider connected"

---

## PARTIE 4 — UTILISATION RÉELLE DE LA RÉPONSE IA

### Structured CV Projects — NOW DISPLAYED CORRECTLY

**Career Profile Merge** (structured_cv_integration.py:109-110):
```python
career_profile["experiences"] = [e.model_dump() for e in profile_v1.experiences]
career_profile["projects"] = [p.model_dump() for p in profile_v1.projects]
```

**ProfilePage display** (ProfilePage.tsx line 1426-1449):
- ✅ Shows `projects[]` in dedicated "Projets" section
- ✅ Displays project title, impact (description), technologies
- ✅ Uses useEffect + fetchProfileFromDB() to sync with new profile_id
- ✅ Fresh data loaded after CV upload

**ProfileUnderstandingPage display** (ProfileUnderstandingPage.tsx line 654-691):
- ✅ NOW FIXED to display structured_cv projects
- ✅ Shows "Réalisations identifiées" section
- ✅ Prioritizes career_profile.projects[] when non-empty
- ✅ Falls back to reconstruction.suggested_projects only if empty

**Field usage matrix**:

| Field | Used Where | Ignored Where | Status |
|-------|-----------|---|---|
| experiences[] | ProfilePage, ProfileUnderstandingPage, matching scoring | - | ✅ VISIBLE |
| projects[] | ProfilePage, ProfileUnderstandingPage (NOW) | Scoring, matching | ✅ VISIBLE |
| education[] | ProfilePage (editable), ProfileUnderstandingPage (suggestions) | Scoring | ✅ VISIBLE |
| certifications[] | ProfilePage, ProfileUnderstandingPage (suggestions) | Scoring | ✅ VISIBLE |
| tools[] (extracted) | Career Intelligence (secondary signal) | Scoring core | 🟡 SECONDARY |
| languages[] | ProfilePage editable | Scoring | ✅ VISIBLE |
| skills[] (from exp) | Context enrichment via skill_links | Scoring (canonical only) | 🟡 CONTEXT |

---

### IA1 Output Usage

**Where sent**: NOWHERE visible to user or matching  
**Where merged**: Applied to cv_text before deterministic parsing (if enabled)  
**Where ignored**: Not stored, not exposed, not matched against

**Verdict**: USED INTERNALLY ONLY, UNVALIDATED, ZERO MATCHING IMPACT

---

### IA2 Output Usage

**Status**: STUB returns nothing useful  
**Where merged**: Nowhere (stub returns empty)  
**Impact**: ZERO

---

## PARTIE 5 — LEGACY VS STRUCTURED_AI

### What is Replaced

**Before structured_ai** (legacy deterministic):
- Raw tokenization of CV text
- Regex-based experience detection
- No project extraction
- No education/certification parsing
- Skills extracted from text matching only

**After structured_ai** (new):
- **REPLACES** `career_profile.experiences[]` entirely (from structured CV)
- **REPLACES** with structured education/certifications
- **ADDS** `career_profile.projects[]` (was empty before, now extracted)
- **ENRICHES** with tool/company/language extraction

### What is Merged

Nothing. Structured CV either:
- ✅ SUCCESS → replaces entire career_profile with structured data
- ❌ FAIL → falls back to legacy parser, no merge

### What Survives from Legacy

**When structured_ai is OFF** (feature_flag=0):
- Entire legacy parser runs
- All deterministic extraction

**When structured_ai FAILS**:
- Validation errors → falls back to legacy
- LLM unavailable → falls back to legacy
- Invalid JSON → falls back to legacy

### Real AI Contribution

**What is genuinely new** (from structured AI):
1. ✅ Projects[] extracted (was missing entirely)
2. ✅ Experiences with separated responsibilities (was jumbled)
3. ✅ Education/certifications structured (was unstructured)
4. ✅ Languages detected (was missing)
5. ✅ Tools contextualized per experience (was not)

**What stays deterministic**:
- ❌ Matching/scoring logic (ZERO IA input)
- ❌ Skill canonicalization (keyword-based, no IA)
- ❌ Role classification (profile_intelligence, no IA)
- ❌ Domain inference (skill-based scoring, no IA)
- ❌ Ranking/ordering (matching_v1.py, frozen, no IA)

**Real question**: Does structured_ai improve the product?
- ✅ YES for ProfilePage/ProfileUnderstandingPage display (users see better structured data)
- ❌ UNKNOWN for matching (never validated, projects not used in matching)
- ❌ NO for IA1 (tested, zero matching impact)

---

## PARTIE 6 — OBSERVABILITÉ

### Backend Logging

**Structured CV**:
```
[structured-cv] Using MOCK extraction (ELEVIA_STRUCTURED_CV_MOCK=1)  [info]
[structured-cv] Extraction OK: 3 exp, 2 proj                        [info]
[structured-cv] JSON parse error: ...                               [warning]
[structured-cv] Extraction failed: TimeoutError                     [warning]
[structured-cv-integration] Profile enhanced with structured data   [info]
[structured-cv-integration] Enhancement failed: ...                 [warning]
```

**IA1**:
```
IA 1 raw CV reconstruction succeeded for request_id=... [info]
IA 1 raw CV reconstruction fallback for request_id=... [warning]
```

**Can dev understand what IA did?**  
✅ YES — logs show:
- Whether structured_ai was enabled
- Whether it succeeded or fell back
- Extraction counts (exp, proj, edu)
- Validation failures
- Metadata includes `extraction_source` ("structured_ai" vs "structured_mock" vs "legacy_parser")

---

### DB Metadata

**Stored in response** (parse-file endpoint):
```json
{
  "structured_cv_metadata": {
    "extraction_source": "structured_ai",
    "structured_cv_success": true,
    "structured_cv_validation": true,
    "structured_cv_warnings": [],
    "fallback_reason": null
  }
}
```

**NOT stored in DB** (profile table):
- structured_cv_metadata is returned but not persisted
- Only used for frontend display

---

### Frontend Debug

**ProfilePage console logs** (lines 1005-1012):
```
[ProfilePage] CV upload response received: profile_id={}, project_count={}
[ProfilePage] useEffect triggered: storeProfileId changed to {}
[ProfilePage] Fetching fresh profile from DB...
[ProfilePage] Fresh profile loaded: {} exp, {} proj
```

**Can user know they got structured_ai?**  
🟡 NO — metadata not visible in UI  
- No badge saying "This was extracted by AI"
- No warning if fallback occurred
- No visibility of structured_cv_warnings

**Can frontend developer debug?**  
✅ YES — metadata in network response

---

### Silent Failures

**What happens when structured_ai fails**:
1. LLM timeout → fallback silently to legacy parser
2. JSON invalid → fallback silently
3. Validation failed → fallback silently, warning logged
4. Feature flag OFF → fallback to legacy (explicit in logs)

**User experience**: No difference. Profile loads normally with whatever parser worked.  
**Developer awareness**: Only if reading logs or checking metadata in response.

---

## PARTIE 7 — IMPACT PRODUIT RÉEL

### Question 1: L'IA améliore quoi concrètement aujourd'hui?

**ProfilePage/ProfileUnderstandingPage display**:
- ✅ Users see structured projects (was empty before)
- ✅ Users see structured education/certifications (was unstructured)
- ✅ Users see clean experience data separated from projects

**But**:
- 🟡 This is display-level improvement only
- ❌ Projects NOT used in matching (invisible to matching algorithm)
- ❌ Data quality not measurably validated (no A/B test)

### Question 2: L'IA est-elle exploitée ou juste stockée?

**PARTIALLY**:
- ✅ Displayed in ProfilePage/ProfileUnderstandingPage
- ❌ Not merged into matching inputs
- ❌ Projects[] not scored
- ❌ Education/certifications not used in matching
- ❌ Structured tools not linked to matching

**Verdict**: Frontend display ✅, Matching exploitation ❌

### Question 3: Quels écrans profitent réellement de l'IA?

| Screen | Benefits | Evidence |
|--------|----------|----------|
| ProfilePage | ✅ Structured display | Projects/education visible |
| ProfileUnderstandingPage | ✅ Structured display (newly fixed) | Réalisations section now shows structured_cv projects |
| AnalyzePage | ✅ Deterministic suggestions | Legacy reconstruction, not IA |
| Inbox | ❌ ZERO | Matching uses legacy experiences only |
| OfferDetailModal | ❌ ZERO | Scoring uses legacy data |
| Matching results | ❌ ZERO | No IA input to scoring |

### Question 4: Quels écrans restent legacy?

ALL matching/ranking screens:
- Inbox matching
- /match endpoint
- Score calculation
- Result ranking
- Career Intelligence (deterministic, no IA)

### Question 5: Quels champs IA sont inutilisés?

| Field | Extracted | Used | Status |
|-------|-----------|------|--------|
| projects[] | ✅ YES | ✅ Display only | Ignored by matching |
| education[] | ✅ YES | ✅ Display only | Ignored by matching |
| certifications[] | ✅ YES | ✅ Display only | Ignored by matching |
| tools[] | ✅ YES | 🟡 Secondary only | Not in core matching |
| global_skills[] | ✅ YES | ❌ NO | Unused |
| warnings[] | ✅ YES | ❌ NO | Unused |

### Question 6: Quelle partie du produit bénéficie réellement du structured_ai?

**Frontend UI**: 70% → better data display  
**Matching**: 0% → no input to scoring/ranking  
**Scoring**: 0% → no IA input  
**User experience**: 20% → can see their CV better, matching unchanged  

### Question 7: Quelle partie du produit n'a quasiment aucun impact IA?

**Everything that matters for job matching**:
- Skill-based matching (uses canonical keywords, no IA)
- Domain inference (uses strong signals, no IA)
- Score calculation (matching_v1.py, deterministic)
- Ranking (matching_v1.py, frozen)
- Filters (deterministic rules)
- Domain affinity (deterministic scoring)
- Career Intelligence (deterministic analysis)

### Question 8: Est-ce qu'on a une vraie "compréhension profil" ou juste une meilleure extraction?

**JUSTE UNE MEILLEURE EXTRACTION**.

**Vrai**: Structured CV is better formatted
- ✅ Experiences separated from projects
- ✅ Education/certifications extracted

**Pas vrai**: Aucune compréhension de contexte
- ❌ No analysis of career arc
- ❌ No understanding of seniority level
- ❌ No skill context analysis
- ❌ No role fit assessment
- ❌ No industry expertise detection
- ❌ Temperature=0.2 ensures LLM is just filling JSON template, not thinking

---

## PARTIE 8 — VERDICT FINAL

### A. Où l'IA est réellement utilisée

**Location 1: Structured CV Extraction**
- File: `apps/api/src/compass/profile/structured_cv_extractor.py`
- Provider: OpenAI gpt-4o-mini
- Flag: `ELEVIA_STRUCTURED_CV_AI` (default OFF)
- Usage: CV parsing → career_profile enrichment → frontend display
- Impact: **Display only, not matching**

**Location 2: IA1 Raw CV Reconstruction (EXPERIMENTAL)**
- File: `apps/api/src/compass/ai_raw_cv_reconstruction.py`
- Provider: OpenAI gpt-4o
- Flag: `ELEVIA_ENABLE_AI_RAW_CV_RECONSTRUCTION` (default OFF)
- Activation: Only for "dirty CVs" (zero experiences + weak signals)
- Usage: CV text normalization before deterministic parsing
- Impact: **Unvalidated, zero matching gain (last validation showed REMOVE verdict)**

**Location 3: IA2 Profile Reconstruction (PURE STUB)**
- File: `apps/api/src/compass/ai_profile_reconstruction.py`
- Status: Stub, no provider
- Impact: **ZERO**

---

### B. Où elle ne sert encore à rien

**Matching algorithm** (matching_v1.py, frozen):
- Zero IA input
- Matching works same way regardless of structured_cv
- Projects[] not scored
- Education/certifications not considered

**Domain inference** (profile_intelligence.py):
- Pure keyword-based
- Zero LLM involvement

**Skill canonicalization** (canonical_store.py):
- Pure dictionary lookup
- Zero IA

**Result ranking**:
- IDF-based + hard filters
- Zero IA

---

### C. Ce qui est réellement intelligent

**Structured CV separator** (legitimate improvement):
- ✅ Projects separated from experiences (was jumbled)
- ✅ Tool extraction contextual (was random)
- ✅ Education/certifications parsed (was unstructured)

**That's it.**

Everything else is deterministic pattern matching (keyword-based, strong signals, IDF scoring).

---

### D. Ce qui reste purement déterministe

**PRESQUE TOUT**:
- Skill canonicalization
- Domain inference
- Matching scoring
- Result ranking
- Filtering
- Career Intelligence
- Profile Intelligence role classification
- Domain affinity
- Fit Score V2

---

### E. Ce qui est affiché mais non exploité

**Structured CV data in matching**:
- Projects[] → displayed, not scored
- Education[] → displayed, not scored
- Certifications[] → displayed, not scored
- Tools[] → stored, barely used (secondary signal only)
- Global skills[] → extracted, completely unused

---

### F. Ce qui est exploité mais invisible UI

**Backend logs**:
- extraction_source tracking
- Fallback reasons
- Validation warnings
- IA decision metadata

Users never see this. Developers must check logs.

---

### G. Le vrai niveau actuel du produit

**Matching**: Pure deterministic. Zero IA input. Better match with clean data, but algorithm unchanged.

**Profile display**: Better structured thanks to IA extraction, but only for view/edit, not for matching.

**Observability**: Backend tracks what IA did, but frontend never exposes it.

**Truth**: Elevia is a **deterministic matching engine with optional AI-powered CV formatting**.

---

### H. Les plus grosses illusions techniques actuelles

1. **"Structured CV improves matching"**  
   → FALSE. Projects extracted but never scored. Matching unchanged.

2. **"IA1 helps with dirty CVs"**  
   → FALSE. Tested on 2 CVs, zero matching impact. Verdict: REMOVE.

3. **"IA2 profile reconstruction is active"**  
   → FALSE. Pure stub. No provider connected.

4. **"Profile Intelligence uses IA"**  
   → FALSE. Deterministic keyword scoring, no LLM.

5. **"Career Intelligence powered by IA"**  
   → FALSE. Deterministic skill analysis, no LLM.

6. **"Users know they got AI extraction"**  
   → FALSE. No badge, no UI indication, silent fallback on failure.

---

### I. Le plus gros manque produit actuel

**Projects not in matching**:
- Extracted perfectly by structured CV
- Displayed nicely in ProfilePage/ProfileUnderstandingPage
- **Completely ignored by matching algorithm**

**Why**:
- Projects[] not in matching inputs
- No project scoring logic
- Matching only looks at experiences[] + skills_uri

**Impact**: User uploads CV with strong personal projects → projects visible in profile → BUT zero impact on matching. Mismatch between UI and matching reality.

---

### J. Le prochain chantier prioritaire

**Either**:

**Option A**: Integrate projects into matching (HIGH EFFORT)
- Add projects to matching inputs
- Implement project scoring logic
- Link projects to skill signals
- Validate against offer skill requirements
- A/B test for matching impact

**Option B**: Remove IA extraction entirely (LOW EFFORT)
- Legacy parser still works perfectly
- Structured CV only helps display, not matching
- Operational cost (LLM quota) not justified for display-only benefit

**Option C**: Use IA for matching-relevant extraction (MEDIUM EFFORT)
- Extract skill context per experience (currently projects only)
- Extract seniority indicators
- Extract role trajectory
- Extract industry expertise
- Feed to matching algorithm (not just display)

**Recommendation**: Start with Option C (matching-relevant extraction) rather than continuing display-only extraction.

---

## ROOT_TRUTH

**Elevia aujourd'hui**:

```
User uploads CV
  ↓
Backend [structured_cv extraction via OpenAI gpt-4o-mini]
  ↓
IF success:
  - Profile display improves (projects visible, education structured)
  - Frontend shows better formatted data
ELSE:
  - Legacy parser used silently
  - User sees no difference
  ↓
Matching algorithm
  - Completely unchanged by IA
  - Uses same keyword scoring as before
  - Projects ignored
  - Skills scored via IDF only
  - Results ranked same way
  ↓
User sees matching results
  - Profile looks better
  - Matching hasn't changed
```

**What actually changed**: Display-layer data quality ✅  
**What didn't change**: Matching logic ❌  
**Where IA is used**: Frontend UI ✅  
**Where IA should be**: Matching algorithm ❌  

---

## PRIORITY_NEXT_STEP

**IMMEDIATE** (1 day):
- Document this audit
- Decide: keep structured_cv extraction (display benefit only) or remove (save quota)?

**NEAR-TERM** (1 week):
- If keeping: A/B test whether better UI → better user engagement
- If removing: assess frontend regression (projects disappear from display)

**STRATEGIC** (2 weeks):
- If committed to IA: pivot to **matching-relevant extraction**
  - Extract skill context, seniority, trajectory, expertise
  - Feed to matching algorithm
  - Validate matching improvement vs current deterministic baseline
  - Actually use IA where it matters

**NOT RECOMMENDED**:
- Continue current path (display-only extraction with LLM quota cost + maintenance burden)
- Keep IA1 (zero validated benefit, experimental only)
- Keep IA2 stub (does nothing)

---

**FIN DE L'AUDIT**

Honest assessment: Elevia has AI extraction infrastructure in place, but uses it for display layer only. Matching algorithm remains pure deterministic. Investment in AI extraction not yet justified by matching improvements. Next major opportunity is matching-layer IA integration or removal of display-only extraction.
