# Structured CV Extraction — Implementation Guide

## Status

✅ **Phase 1 Complete**: Extractor + Validator + Tests (11 passing)

⏳ **Phase 2 Pending**: Integration into `/parse-file` route (behind feature flag)

## Architecture

```
PDF
→ raw text extraction (existing)
→ StructuredCV extractor (NEW — AI-powered)
  ├─ LLM structured extraction
  ├─ JSON schema validation (Pydantic)
  └─ Fallback if disabled/failed
→ Contamination validator (NEW)
  ├─ Projects ≠ experiences
  ├─ No responsibility contamination
  ├─ Skills properly contextualized
  └─ Flags critical issues
→ Profile data (existing)
→ Matching (existing)
```

## Modules Created

### 1. `structured_cv_schemas.py`
Pydantic models for structured CV data:
- `StructuredExperience` — job with title, company, dates, responsibilities, tools, skills
- `StructuredProject` — personal/academic project (separate from experiences)
- `StructuredEducation`, `StructuredCertification` — education blocks
- `StructuredCV` — complete structure

### 2. `structured_cv_extractor.py`
AI-powered extraction:
```python
extract_structured_cv(cv_text: str) -> Optional[StructuredCV]
```

**Features**:
- Lazy imports openai (no dependency if disabled)
- Configurable model via `ELEVIA_CV_STRUCTURER_MODEL` (default: gpt-4o-mini)
- Feature flag: `ELEVIA_STRUCTURED_CV_AI=1` (disabled by default)
- Graceful fallback: returns None if key missing, AI fails, or disabled
- Low temperature (0.2) for deterministic parsing
- JSON extraction from markdown/raw responses

**Requirements**:
- `OPENAI_API_KEY` environment variable
- `openai` Python package (optional — skipped if not installed)

### 3. `structured_cv_validator.py`
Contamination detection:
```python
validate_structured_cv(cv: StructuredCV) -> (bool, List[str])
```

**Checks**:
1. **Projects separation** — Project names shouldn't appear in responsibility text
2. **Experience contamination** — Responsibilities shouldn't contain:
   - Other company names
   - Section headers (EDUCATION, EXPERIENCE, etc)
   - Job title patterns (Title — Company — Dates)
3. **Skills contextualization** — Warns if skills appear both contextual + global
4. **Valid structure** — At least title+company per experience

### 4. `structured_cv_pipeline.py`
Integration layer:
```python
extract_and_validate_cv(cv_text: str) -> (Optional[StructuredCV], bool, List[str])
```

Returns:
- `(cv, True, [])` — Valid extraction
- `(cv, True, warnings)` — Valid with warnings
- `(None, False, errors)` — Critical contamination detected
- `(None, True, ["..."])` — AI unavailable (use fallback parser)

## Test Coverage

11 tests, all passing:

✅ Projects separated from experiences  
✅ No false projects when empty  
✅ Alternance/apprenticeship proper closure  
✅ Skills contextualized (no contamination)  
✅ Project contamination detected  
✅ Company contamination detected  
✅ Section header contamination detected  
✅ Valid data passes validation  
✅ AI disabled returns None  
✅ JSON extraction from markdown  
✅ JSON extraction from raw response  

Run tests:
```bash
source .venv/bin/activate
python3 -m pytest tests/test_structured_cv_extractor.py -v
```

## How to Use

### Basic Usage

```python
from compass.profile.structured_cv_pipeline import extract_and_validate_cv

# Try structured extraction
cv, is_valid, warnings = extract_and_validate_cv(raw_cv_text)

if cv is not None and is_valid:
    # Use structured data
    print(f"Experiences: {len(cv.experiences)}")
    print(f"Projects: {len(cv.projects)}")
else:
    # Fallback to existing parser
    cv_old = structure_profile_text_v1(raw_cv_text)
```

### Configuration

**Environment Variables**:
```bash
# Enable AI extraction (default: disabled)
ELEVIA_STRUCTURED_CV_AI=1

# OpenAI API key (required if AI enabled)
OPENAI_API_KEY=sk-...

# Optional: specify model (default: gpt-4o-mini)
ELEVIA_CV_STRUCTURER_MODEL=gpt-4o
```

### Feature Flag: /parse-file Route

To enable in `/parse-file`:
```python
from compass.profile.structured_cv_pipeline import extract_and_validate_cv

# Inside route handler
cv_structured, is_valid, warnings = extract_and_validate_cv(raw_text)

if cv_structured and is_valid:
    # Use structured extraction
    profile_data = convert_structured_to_profile(cv_structured)
else:
    # Fallback to existing parser
    profile_data = structure_profile_text_v1(raw_text)
```

## What's NOT Done

❌ Not wired into `/parse-file` yet  
❌ No `convert_structured_to_profile()` adapter  
❌ No debug mode comparing old vs new parser  
❌ No matching impact benchmark  

## Next Steps (Phase 2)

1. **Create adapter**: `structured_to_profile_v1()` converter
   - Map StructuredExperience → ExperienceV1
   - Map StructuredProject → ProjectV1
   - Preserve all fields

2. **Integrate into /parse-file**:
   - Add feature flag check
   - Call `extract_and_validate_cv()`
   - Use adapter if valid
   - Fallback to existing parser if not

3. **Debug mode** (optional):
   - Compare old parser output vs structured
   - Add side-by-side comparison in response
   - Flag differences for analysis

4. **Benchmark**:
   - Test with Data Engineer CV
   - Verify projects properly separated
   - Check inbox matching impact
   - Measure contamination reduction

## Fallback Guarantees

✅ **No regression**: If structured extraction fails, uses existing parser  
✅ **Graceful degradation**: AI disabled → use fallback automatically  
✅ **Validation strict**: Detects contamination → rejects AI output  
✅ **Safe by default**: Feature flag disabled (opt-in)

## Testing with Real CV

```bash
# Enable AI extraction
export ELEVIA_STRUCTURED_CV_AI=1
export OPENAI_API_KEY=sk-...

# Run structured extraction tests
python3 -m pytest tests/test_structured_cv_extractor.py -v

# Test on real CV (after Phase 2 integration)
# Upload CV → check structured extraction in response
```

## Files

**Created**:
- `src/compass/profile/structured_cv_schemas.py`
- `src/compass/profile/structured_cv_extractor.py`
- `src/compass/profile/structured_cv_validator.py`
- `src/compass/profile/structured_cv_pipeline.py`
- `tests/test_structured_cv_extractor.py`

**To Modify** (Phase 2):
- `src/compass/pipeline/profile_parse_pipeline.py` — wire into /parse-file
- `src/compass/profile/contracts.py` — optional: add StructuredCV fields to response

**Keep** (no changes):
- `src/compass/profile_structurer.py` — unchanged, used as fallback

## Validation Examples

### ✅ Valid CV
```json
{
  "headline": "Data Engineer",
  "experiences": [
    {"title": "Data Engineer", "company": "TechCorp", "responsibilities": ["Built ETL"]}
  ],
  "projects": [
    {"name": "CV Matching", "description": "Personal project"}
  ]
}
```

### ❌ Invalid: Project in responsibilities
```json
{
  "experiences": [
    {"title": "Business Dev", "responsibilities": ["Personal project — CV Matching"]}
  ],
  "projects": [{"name": "CV Matching"}]
}
```
→ **Rejected**: Projects shouldn't contaminate experiences

### ❌ Invalid: Company name in responsibilities
```json
{
  "experiences": [
    {"company": "TechCorp", "responsibilities": ["OtherCorp — Senior Engineer"]},
    {"company": "OtherCorp"}
  ]
}
```
→ **Rejected**: Company names shouldn't appear in responsibilities

---

**Created by**: Claude  
**Date**: 2026-05-08  
**Status**: Phase 1 ✅ | Phase 2 ⏳
