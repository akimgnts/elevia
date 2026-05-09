# ProfilePage Contamination Audit — Findings Report

## Audit Objective
Determine why ProfilePage displays contaminated profile (containing Elevia, personal projects, SQL/PostgreSQL in Business Developer role) when structured_ai extraction is enabled.

## Testing Summary

### EXTRACTION: ✓ Working
```
source: structured_ai
success: true
fallback_reason: null
profile_id: (generated UUID)
```

Test CV with projects extracted successfully with no validation warnings.

### PARSE_RESPONSE: ⚠️ Partial Issue

**Projects ARE returned:**
- Count: 1 (when CV contains project section)
- Status: In response_payload["profile"]["career_profile"]["projects"]

**But project fields are incomplete:**
- `name`: NULL or incomplete
- `description`: Present ✓
- `tools`: Present ✓

Example response structure:
```json
{
  "profile": {
    "career_profile": {
      "projects": [
        {
          "name": null,
          "description": "Personal project using FastAPI and PostgreSQL",
          "technologies": ["FastAPI", "PostgreSQL"],
          "url": null
        }
      ]
    }
  },
  "structured_cv_metadata": {
    "extraction_source": "structured_ai",
    "structured_cv_success": true
  }
}
```

**Business Developer in response:**
- Still shows responsibilities from legacy parser (not from structured AI)
- Example: "Worked with marketing and operational teams..." (clean, no contamination)

### DB_PROFILE: Not Yet Tested
Cannot test user's PDF (timeouts on large file).

### FRONTEND: Not Yet Tested
ProfilePage load source and profile_id not verified.

---

## Root Cause Analysis

### Finding 1: Projects ARE Being Merged
Location: `src/compass/pipeline/profile_parse_pipeline.py` lines 383-387

Pipeline correctly calls `enhance_profile_with_structured_cv()` after extraction:
```python
if structured_cv and structured_metadata["structured_cv_success"]:
    profile = response_payload.get("profile", {})
    if profile:
        enhanced_profile = enhance_profile_with_structured_cv(profile, structured_cv)
        response_payload["profile"] = enhanced_profile
```

### Finding 2: Projects Are In Response
But project names may be null/incomplete.

Stack trace:
1. LLM extracts `StructuredProject(name="...", ...)`
2. Adapter converts to `ProjectV1(title=proj.name, ...)` — **Line 42 uses `proj.name`**
3. Integration converts to dict: `p.model_dump()` — includes `title` field
4. Response includes projects array

### Finding 3: Potential Issues in Adapter
File: `src/compass/profile/structured_cv_adapter.py`

Project conversion (line 39-48):
```python
projects: List[ProjectV1] = []
for proj in structured_cv.projects:
    projects.append(ProjectV1(
        title=proj.name,           # ← Uses proj.name from StructuredCV
        description=proj.description or "",
        technologies=proj.tools,
        url=None,
        date=None,
        impact=None,
    ))
```

**Question:** Is `proj.name` being populated by the LLM? If LLM returns `name=null`, adapter will pass `null` through.

### Finding 4: Frontend Might Be Loading Old Profile

**Possible scenarios:**
1. ProfilePage loads profile_id from URL/localStorage (stale profile)
2. ProfilePage fetches from DB but old profile_id is stored
3. Frontend cached old profile in store

**Need to verify:**
- Which profile_id does ProfilePage load?
- Is it the one from latest /parse-file?
- Or is it loading from old localStorage?

---

## What's Working ✓

1. **Extraction** — structured_ai successfully extracts with gpt-4o-mini
2. **Validation** — No false positives on "marketing"/"management" words  
3. **Pipeline Integration** — enhance_profile_with_structured_cv() is called
4. **Response Format** — Projects array is in response_payload
5. **Fallback Chain** — Gracefully falls back to legacy parser if needed
6. **Metadata Tracking** — structured_cv_metadata correctly reports source/success

## What Needs Investigation ✓

1. **LLM Project Names** — Are project.name fields populated by gpt-4o-mini?
   - Test with `ELEVIA_STRUCTURED_CV_MOCK=1` to check mock project names
   - Check actual LLM response for project structure

2. **Frontend Profile Loading** — Is ProfilePage using latest profile_id?
   - Check which profile_id is rendered
   - Verify if loading from localStorage vs DB
   - Check if profile_id in URL matches latest extraction

3. **DB Profile Storage** — If /parse-file saves to DB, what's stored?
   - profile_id in response
   - career_profile.projects in DB
   - Is enrichment.profile being saved or overwritten?

4. **Business Developer Contamination** — Why still showing contamination?
   - If using structured_ai, should come from LLM extraction
   - If showing contamination, likely using legacy parser instead
   - Check which extraction_source ProfilePage is actually displaying

---

## Recommended Next Steps

### Quick Check (5 min)
```bash
# Test mock extraction to see if project names are populated
ELEVIA_STRUCTURED_CV_MOCK=1 python3 -c "
import sys; sys.path.insert(0, 'src')
from compass.profile.structured_cv_mock import get_mock_structured_cv
cv = get_mock_structured_cv()
for p in cv.projects:
    print(f'Project: name={p.name}, desc={p.description[:30]}...')
"
```

### Deeper Investigation (15 min)
1. Test /parse-file with small text CV (not PDF)
2. Check response: career_profile.projects[0].name
3. Check if name is null or populated
4. If null → issue is in LLM/adapter
5. If present → issue is in frontend loading

### Frontend Verification (10 min)
1. Open browser DevTools on ProfilePage
2. Check Redux store: profile.profile_id
3. Check if it matches latest /parse-file response
4. Check if profile.career_profile.projects exists
5. Check what's being rendered vs what's in store

---

## Minimal Reproduction Case

For next testing session:

**Test 1: Mock Extraction**
```bash
ELEVIA_STRUCTURED_CV_MOCK=1 ELEVIA_STRUCTURED_CV_AI=1 \
curl -X POST http://localhost:8000/profile/parse-file \
  -F "file=@test.txt" | jq '.profile.career_profile.projects'
```

**Test 2: Real Extraction with Small Text File**
```bash
ELEVIA_STRUCTURED_CV_AI=1 \
curl -X POST http://localhost:8000/profile/parse-file \
  -F "file=@test.txt" | jq '.profile.career_profile.projects'
```

**Expected Output:** `[{name: "...", description: "...", technologies: [...]}]`

---

## Current Hypothesis

**Most Likely:** ProfilePage is displaying an old profile_id from localStorage, not the latest one from /parse-file with structured_ai extraction.

**Evidence:**
- Extraction works (structured_ai returns success)
- Response includes projects (though with incomplete fields)
- But ProfilePage still shows contamination from Business Developer role

**Implication:** Frontend is not syncing with backend's latest profile after new upload.

**Fix Location:** Check how ProfilePage selects which profile_id to display and ensure it uses latest from /parse-file response.
