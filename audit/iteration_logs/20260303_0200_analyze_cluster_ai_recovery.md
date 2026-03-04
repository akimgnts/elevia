# Sprint 4 — Analyze Page Cluster-Aware AI Skill Recovery
**Date:** 2026-03-03
**Sprint:** S4 — AI Skill Recovery (UI Display Only)
**Status:** ✅ COMPLETED

---

## Objective

Build end-to-end cluster-aware AI skill recovery for the Analyze page:
- Backend: LLM-powered skill recovery from ignored/noise tokens
- Frontend: DEV-only toggle + AI pills + display-only disclaimer
- Tests: 17 backend + 6 frontend static tests
- Non-negotiable: recovered skills never injected into matching pipeline

---

## Files Created

| File | Purpose |
|------|---------|
| `apps/api/src/compass/analyze_skill_recovery.py` | LLM call + deterministic post-filter |
| `apps/api/src/api/routes/analyze_recovery.py` | POST /analyze/recover-skills (DEV-only) |
| `apps/api/tests/test_analyze_skill_recovery.py` | 17 backend tests (4 test classes) |
| `apps/web/tests/test_analyze_recovery_button.py` | 6 frontend static analysis tests |
| `audit/golden/analyze_recovery_request.json` | Golden request fixture |
| `audit/golden/analyze_recovery_response.json` | Golden response fixture (synthetic) |

## Files Modified

| File | Change |
|------|--------|
| `apps/api/src/api/main.py` | Register `analyze_recovery_router` |
| `apps/web/src/lib/api.ts` | Add `RecoverSkillsRequest`, `RecoveredSkillItem`, `RecoverSkillsResponse`, `fetchRecoverSkills()` |
| `apps/web/src/pages/AnalyzePage.tsx` | Add state, handler, button, AI pills section |

---

## Backend Architecture

### `analyze_skill_recovery.py`

**Input:** `(cluster, ignored_tokens, noise_tokens, validated_esco_labels, profile_text_excerpt)`

**Pipeline:**
1. Check `OPENAI_API_KEY` → `ai_available` flag
2. LLM call: `gpt-4o-mini`, temperature=0, `json_object` format
3. Strict cluster-aware prompt (French, max 20 items)
4. Deterministic post-filter:
   - Generic blacklist: autonomie, leadership, communication, work, experience, etc.
   - Handle/slug rejection: `^[a-z0-9_\-]{1,8}$` on original (not lowercased)
   - Number-only rejection
   - Short label rejection (< 3 chars)
   - Cluster coherence check (DATA_IT, FINANCE, RH patterns)
   - ESCO dedup guard
5. Cap to `MAX_RECOVERED_SKILLS = 20`
6. Returns `RecoveryResult` with `recovered_skills` list + `ai_available` + `error`

**Key bug fixed during implementation:**
- Handle regex ran on lowercased token: "Python" → "python" → matched `^[a-z0-9_\-]{1,8}$` → falsely rejected
- Fix: match handle pattern on `stripped` (original case), not `lower`

### `analyze_recovery.py`

**Endpoint:** `POST /analyze/recover-skills`

**DEV gate:** Returns 400 with `DEV_TOOLS_DISABLED` error unless `ELEVIA_DEV_TOOLS=1`

**Graceful:** Returns 200 with `ai_available=False` and `error=openai_key_missing` when key absent

---

## Frontend Architecture

### `api.ts` additions
```typescript
interface RecoverSkillsRequest {
  cluster: string;
  ignored_tokens: string[];
  noise_tokens?: string[];
  validated_esco_labels?: string[];
  profile_text_excerpt?: string;
}

interface RecoveredSkillItem {
  label: string; kind: string; confidence: number;
  source: string; evidence: string; why_cluster_fit: string;
}

interface RecoverSkillsResponse {
  recovered_skills: RecoveredSkillItem[];
  ai_available: boolean;
  cluster: string;
  ignored_token_count: number;
  noise_token_count: number;
  error: string | null;
  request_id: string;
}

async function fetchRecoverSkills(payload): Promise<RecoverSkillsResponse>
```

### `AnalyzePage.tsx` additions
- **State:** `recoveredSkills`, `recoveringSkills`, `recoveryError` (reset on file select + parse)
- **Handler:** `handleRecover()` — calls `fetchRecoverSkills` with `(cluster, filtered_tokens, validated_labels)`
- **Button:** Violet-styled, DEV-only (`isDev && profileCluster?.dominant_cluster && filteredTokens?.length > 0`)
  - Label: "Récupérer des compétences (IA)" / "Récupération IA..." when loading
  - `disabled={recoveringSkills}` + error display
- **Pills:** Violet pills with "IA" tag after ESCO pills, disclaimer "affichage uniquement — non injectées"

---

## Test Results

### Backend (17 tests)
```
TestRecoveryRejectsGenericWords     8 passed
TestRecoveryRecombinesMachinelearning 5 passed
TestRecoveryCapsTo20                2 passed
TestEndpointDevOnlyGate             2 passed

17/17 PASSED
```

### Frontend static (6 tests)
```
test_fetch_recover_skills_imported           PASSED
test_recovered_skills_state_and_handler_exist PASSED
test_recovery_button_is_dev_gated            PASSED
test_recovered_skills_render_with_ia_tag_and_disclaimer PASSED
test_endpoint_call_sends_required_fields     PASSED
test_recovered_skills_not_injected_into_skills_uri PASSED

6/6 PASSED
```

---

## Score-Invariance Proof

Recovered skills:
- Never added to `profile.skills_uri`
- Never passed to `fetchKeySkills()` or any matching call
- `RecoverSkillsResponse` has no `skills_uri` field
- Display only: rendered in violet pills with "non injectées" disclaimer
- Frontend test `test_recovered_skills_not_injected_into_skills_uri` asserts this statically

---

## Non-Negotiables Verified

| Constraint | Status |
|-----------|--------|
| DO NOT modify matching_v1.py | ✅ Not touched |
| DO NOT modify idf.py | ✅ Not touched |
| IA not on every request — explicit toggle | ✅ Button-triggered only |
| Recovered skills display-only | ✅ Never injected into skills_uri |
| DEV-only gate | ✅ `ELEVIA_DEV_TOOLS=1` required on backend; `isDev` on frontend |
| Graceful when key absent | ✅ Returns `ai_available=False`, error=openai_key_missing |
| Max 20 results | ✅ `MAX_RECOVERED_SKILLS=20` capped in `_filter_recovered` |

---

## Sample Acceptance Check

**Endpoint blocked without dev tools:**
```
POST /analyze/recover-skills
→ 400 { "error": { "code": "DEV_TOOLS_DISABLED", ... } }
```

**Endpoint with ELEVIA_DEV_TOOLS=1, no OpenAI key:**
```
POST /analyze/recover-skills { "cluster": "DATA_IT", "ignored_tokens": ["python"] }
→ 200 { "recovered_skills": [], "ai_available": false, "error": "openai_key_missing" }
```

**With key + DATA_IT cluster:**
→ Returns ≤ 20 recovered skill items, all cluster-coherent, no generic words, no ESCO duplicates

---

## Golden Artifacts

- `audit/golden/analyze_recovery_request.json` — synthetic request for DATA_IT cluster
- `audit/golden/analyze_recovery_response.json` — synthetic expected response (6 skills recovered)
