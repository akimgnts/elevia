# Profile Understanding Agent V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the repo-side profile-understanding integration so it can support a real external agent with resource access, relation-rich outputs, and a higher-value wizard that maps into the existing profile model.

**Architecture:** Keep the real agent runtime outside the repo, but strengthen the repo contract around it. The backend will expose structured resource access and a richer session payload, while the frontend wizard will consume entity classification, evidence-backed `skill_links`, and confidence-driven questions instead of generic freeform prompts.

**Tech Stack:** FastAPI, Pydantic, TypeScript, React, Zustand, existing Elevia profile model, external LangGraph/LangSmith runtime contract

---

### Task 1: Define the V2 backend contract for agent outputs

**Files:**
- Modify: `apps/api/src/profile_understanding/schemas.py`
- Test: `apps/api/tests/test_profile_understanding_route.py`

- [ ] **Step 1: Expand the failing backend contract test**

Add assertions for the new V2 payload shape in `apps/api/tests/test_profile_understanding_route.py`:

```python
        self.assertIn("entity_classification", data)
        self.assertIn("skill_links", data)
        self.assertIn("evidence_map", data)
        self.assertIn("confidence_map", data)
        self.assertIsInstance(data["entity_classification"], dict)
        self.assertIsInstance(data["skill_links"], list)
        self.assertIsInstance(data["evidence_map"], dict)
        self.assertIsInstance(data["confidence_map"], dict)
        self.assertTrue(any(link.get("skill", {}).get("label") == "Data Analysis" for link in data["skill_links"]))
```

- [ ] **Step 2: Run the backend contract test to verify it fails**

Run from repo root:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_route
```

Expected: FAIL because the current response model does not expose `entity_classification`, `skill_links`, `evidence_map`, or `confidence_map`.

- [ ] **Step 3: Add the richer V2 schema models**

Update `apps/api/src/profile_understanding/schemas.py` with nested models that preserve the external-runtime boundary while making the contract explicit:

```python
class ProfileUnderstandingEntity(BaseModel):
    id: str
    entity_type: str
    label: str
    confidence: float | None = None
    raw_value: str | None = None


class ProfileUnderstandingEvidence(BaseModel):
    source_type: str
    source_value: str | None = None
    confidence: float | None = None
    mapping_status: str | None = None


class ProfileUnderstandingSkillLink(BaseModel):
    experience_ref: str | None = None
    skill: dict
    tools: list[dict] = Field(default_factory=list)
    context: str | None = None
    autonomy_level: str | None = None
    evidence: list[ProfileUnderstandingEvidence] = Field(default_factory=list)


class ProfileUnderstandingSessionResponse(BaseModel):
    session_id: str
    status: Literal["ready", "pending", "error"] = "ready"
    provider: str
    trace_summary: Dict[str, Any] = Field(default_factory=dict)
    entity_classification: Dict[str, list[ProfileUnderstandingEntity]] = Field(default_factory=dict)
    proposed_profile_patch: Dict[str, Any] = Field(default_factory=dict)
    skill_links: list[ProfileUnderstandingSkillLink] = Field(default_factory=list)
    evidence_map: Dict[str, list[ProfileUnderstandingEvidence]] = Field(default_factory=dict)
    confidence_map: Dict[str, float] = Field(default_factory=dict)
    questions: List[ProfileUnderstandingQuestion] = Field(default_factory=list)
```

- [ ] **Step 4: Re-run the backend contract test**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_route
```

Expected: still FAIL, now because the service stub does not yet populate the new fields.

- [ ] **Step 5: Commit the contract-only change**

```bash
git add apps/api/src/profile_understanding/schemas.py apps/api/tests/test_profile_understanding_route.py
git commit -m "feat(profile-understanding): define v2 response contract"
```

### Task 2: Enrich the backend adapter with entity, relation, and evidence outputs

**Files:**
- Modify: `apps/api/src/profile_understanding/service.py`
- Test: `apps/api/tests/test_profile_understanding_route.py`

- [ ] **Step 1: Add a failing assertion for tool-vs-skill relation output**

Extend `apps/api/tests/test_profile_understanding_route.py`:

```python
        data_analysis_links = [
            link for link in data["skill_links"]
            if link.get("skill", {}).get("label") == "Data Analysis"
        ]
        self.assertTrue(data_analysis_links)
        self.assertTrue(any(tool.get("label") == "SQL" for tool in data_analysis_links[0].get("tools", [])))
        self.assertEqual(data["entity_classification"]["skills"][0]["entity_type"], "skill")
```

- [ ] **Step 2: Run the test to confirm service behavior is still insufficient**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_route
```

Expected: FAIL on missing `skill_links` contents and `entity_classification`.

- [ ] **Step 3: Implement the minimal V2 stub adapter**

Update `apps/api/src/profile_understanding/service.py` so the repo stub produces a structurally correct fallback while remaining explicit that the real agent lives outside the repo:

```python
def _build_entity_classification(career_profile: Dict[str, Any], source_context: Dict[str, Any]) -> Dict[str, list[dict]]:
    experiences = career_profile.get("experiences", []) or []
    entities = {
        "experiences": [],
        "projects": [],
        "education": [],
        "certifications": [],
        "skills": [],
        "tools": [],
    }
    for index, experience in enumerate(experiences):
        if not isinstance(experience, dict):
            continue
        entities["experiences"].append({
            "id": f"exp-{index}",
            "entity_type": "experience",
            "label": str(experience.get("title") or "Experience"),
            "confidence": 0.72,
            "raw_value": str(experience.get("company") or ""),
        })
        for skill in experience.get("canonical_skills_used", []) or []:
            entities["skills"].append({
                "id": f"exp-{index}-skill-{str(skill.get('label') or '').lower()}",
                "entity_type": "skill",
                "label": str(skill.get("label") or ""),
                "confidence": 0.7,
                "raw_value": str(skill.get("label") or ""),
            })
    return entities


def _build_skill_links(career_profile: Dict[str, Any], source_context: Dict[str, Any]) -> List[dict]:
    links: List[dict] = []
    candidate_tools = _extract_candidate_labels(source_context)
    for index, experience in enumerate(career_profile.get("experiences", []) or []):
        if not isinstance(experience, dict):
            continue
        canonical_skills = experience.get("canonical_skills_used", []) or []
        for skill in canonical_skills:
            label = str(skill.get("label") or "").strip()
            if not label:
                continue
            links.append({
                "experience_ref": f"exp-{index}",
                "skill": {"label": label, "uri": skill.get("uri")},
                "tools": [{"label": tool} for tool in candidate_tools[:3]],
                "context": (experience.get("responsibilities") or [""])[0] or None,
                "autonomy_level": experience.get("autonomy_level"),
                "evidence": [{"source_type": "parser_signal", "source_value": tool, "confidence": 0.45, "mapping_status": "open"} for tool in candidate_tools[:2]],
            })
    return links
```

- [ ] **Step 4: Return the new fields from the session response**

In the stub response block, add:

```python
        entity_classification = _build_entity_classification(career_profile, payload.source_context)
        skill_links = _build_skill_links(career_profile, payload.source_context)
        evidence_map = {
            "career_profile.skill_links": [
                {"source_type": "stub_adapter", "source_value": "repo_fallback", "confidence": 0.4, "mapping_status": "open"}
            ]
        }
        confidence_map = {
            "entity_classification": 0.65,
            "skill_links": 0.48,
        }
```

and include them in `ProfileUnderstandingSessionResponse(...)`.

- [ ] **Step 5: Re-run the backend contract test**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_route
```

Expected: PASS.

- [ ] **Step 6: Commit the service upgrade**

```bash
git add apps/api/src/profile_understanding/service.py apps/api/tests/test_profile_understanding_route.py
git commit -m "feat(profile-understanding): add v2 entity and relation fallback outputs"
```

### Task 3: Expose resource-oriented backend endpoints for the future external agent

**Files:**
- Create: `apps/api/src/api/routes/profile_understanding_resources.py`
- Modify: `apps/api/src/api/main.py`
- Test: `apps/api/tests/test_profile_understanding_resources.py`

- [ ] **Step 1: Write the failing resource endpoint test**

Create `apps/api/tests/test_profile_understanding_resources.py`:

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api.main import app


class ProfileUnderstandingResourcesTests(unittest.TestCase):
    def test_resources_endpoint_returns_reference_sections(self) -> None:
        with TestClient(app) as client:
            resp = client.get("/profile-understanding/resources")

        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertIn("canonical_skills", data)
        self.assertIn("profile_schema", data)
        self.assertIn("tool_hints", data)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new test to verify the route does not exist yet**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_resources
```

Expected: FAIL with 404 or import error for the missing route.

- [ ] **Step 3: Add the resource route**

Create `apps/api/src/api/routes/profile_understanding_resources.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["profile-understanding"])


@router.get("/profile-understanding/resources")
async def get_profile_understanding_resources() -> dict:
    return {
        "canonical_skills": [],
        "tool_hints": [],
        "profile_schema": {
            "experience_fields": ["title", "company", "responsibilities", "tools", "canonical_skills_used", "skill_links"],
            "skill_link_fields": ["skill", "tools", "context", "autonomy_level"],
        },
    }
```

- [ ] **Step 4: Register the new route in `apps/api/src/api/main.py`**

Add:

```python
from .routes.profile_understanding_resources import router as profile_understanding_resources_router
```

and include it in both router registration blocks:

```python
app.include_router(profile_understanding_resources_router)
app.include_router(profile_understanding_resources_router, prefix=_P)
```

- [ ] **Step 5: Re-run the resource test**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_resources
```

Expected: PASS.

- [ ] **Step 6: Commit the resource surface**

```bash
git add apps/api/src/api/routes/profile_understanding_resources.py apps/api/src/api/main.py apps/api/tests/test_profile_understanding_resources.py
git commit -m "feat(profile-understanding): expose agent resource references"
```

### Task 4: Refactor the frontend wizard to consume V2 outputs

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/pages/ProfileUnderstandingPage.tsx`
- Test/Verify: `apps/web/src/App.tsx`

- [ ] **Step 1: Add the richer client-side response types**

Update `apps/web/src/lib/api.ts`:

```ts
export interface ProfileUnderstandingEntity {
  id: string;
  entity_type: string;
  label: string;
  confidence?: number | null;
  raw_value?: string | null;
}

export interface ProfileUnderstandingEvidence {
  source_type: string;
  source_value?: string | null;
  confidence?: number | null;
  mapping_status?: string | null;
}

export interface ProfileUnderstandingSkillLink {
  experience_ref?: string | null;
  skill: { label: string; uri?: string | null };
  tools: Array<{ label: string }>;
  context?: string | null;
  autonomy_level?: string | null;
  evidence: ProfileUnderstandingEvidence[];
}
```

and update `ProfileUnderstandingSessionResponse`:

```ts
export interface ProfileUnderstandingSessionResponse {
  session_id: string;
  status: "ready" | "pending" | "error";
  provider: string;
  trace_summary: Record<string, unknown>;
  entity_classification: Record<string, ProfileUnderstandingEntity[]>;
  proposed_profile_patch: Record<string, unknown>;
  skill_links: ProfileUnderstandingSkillLink[];
  evidence_map: Record<string, ProfileUnderstandingEvidence[]>;
  confidence_map: Record<string, number>;
  questions: ProfileUnderstandingQuestion[];
}
```

- [ ] **Step 2: Update the wizard page to show relation-aware context**

In `apps/web/src/pages/ProfileUnderstandingPage.tsx`, add a right-column summary driven by `session.skill_links` and `session.entity_classification`:

```tsx
{session?.skill_links?.slice(0, 4).map((link) => (
  <div key={`${link.experience_ref}-${link.skill.label}`} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
    <div className="text-sm font-semibold text-slate-950">{link.skill.label}</div>
    <div className="mt-1 text-sm text-slate-600">
      {(link.tools || []).map((tool) => tool.label).join(", ") || "Aucun outil confirme"}
    </div>
    {link.context && <div className="mt-2 text-xs leading-5 text-slate-500">{link.context}</div>}
  </div>
))}
```

- [ ] **Step 3: Apply confirmed answers back into `career_profile.skill_links`**

In the wizard continuation logic, merge `session.skill_links` into the proposed `career_profile`:

```tsx
const mergedSkillLinks = (session?.skill_links ?? []).map((link) => ({
  skill: link.skill,
  tools: link.tools,
  context: link.context ?? undefined,
  autonomy_level: link.autonomy_level ?? undefined,
}));

if (Array.isArray(nextCareer.experiences) && mergedSkillLinks.length > 0) {
  nextCareer.experiences = nextCareer.experiences.map((experience, index) => ({
    ...experience,
    skill_links: index === 0 ? mergedSkillLinks : experience.skill_links ?? [],
  }));
}
```

- [ ] **Step 4: Verify the route still compiles and the app builds**

Run in `apps/web`:

```bash
npm run build
```

Expected: PASS with the usual Vite chunk-size warning only.

- [ ] **Step 5: Commit the wizard refactor**

```bash
git add apps/web/src/lib/api.ts apps/web/src/pages/ProfileUnderstandingPage.tsx
git commit -m "feat(profile-understanding): consume v2 relation outputs in wizard"
```

### Task 5: Document deployment and web visibility for the external runtime

**Files:**
- Create: `docs/superpowers/specs/2026-04-17-profile-understanding-agent-runtime-handoff.md`

- [ ] **Step 1: Write the deployment handoff doc**

Create `docs/superpowers/specs/2026-04-17-profile-understanding-agent-runtime-handoff.md` with the minimal operational contract:

```md
# Profile Understanding Agent Runtime Handoff

## Purpose

This document defines what the external runtime must implement so the repo-side integration can call it safely.

## Required capabilities

- stateful thread execution
- LangSmith tracing enabled
- support for resource tools
- V2 response contract:
  - entity_classification
  - proposed_profile_patch
  - skill_links
  - evidence_map
  - confidence_map
  - questions

## Visibility

To inspect the agent on the web:

1. deploy the runtime
2. enable LangSmith tracing
3. execute runs on a real thread
4. inspect traces, runs, and threads in LangSmith Studio
```

- [ ] **Step 2: Sanity-check the doc for ambiguity**

Run:

```bash
rg -n "TODO|TBD|placeholder" docs/superpowers/specs/2026-04-17-profile-understanding-agent-runtime-handoff.md
```

Expected: no matches.

- [ ] **Step 3: Commit the runtime handoff**

```bash
git add docs/superpowers/specs/2026-04-17-profile-understanding-agent-runtime-handoff.md
git commit -m "docs(profile-understanding): add external runtime handoff"
```

### Task 6: Final verification across backend and frontend

**Files:**
- Verify only

- [ ] **Step 1: Run the backend profile-understanding tests**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_route apps.api.tests.test_profile_understanding_resources
```

Expected: PASS.

- [ ] **Step 2: Run the frontend production build**

Run in `apps/web`:

```bash
npm run build
```

Expected: PASS with only the pre-existing chunk-size warning.

- [ ] **Step 3: Smoke-test the user flow manually**

Verify:

1. upload or paste a CV on `/analyze`
2. continue to `/profile-understanding`
3. confirm the page shows relation-aware summary cards
4. answer at least one question
5. continue to `/profile`
6. confirm `skill_links` remain visible and editable

- [ ] **Step 4: Commit the final verified state**

```bash
git status --short
git add apps/api/src/profile_understanding apps/api/src/api/main.py apps/api/src/api/routes/profile_understanding_resources.py apps/api/tests/test_profile_understanding_route.py apps/api/tests/test_profile_understanding_resources.py apps/web/src/lib/api.ts apps/web/src/pages/ProfileUnderstandingPage.tsx docs/superpowers/specs/2026-04-17-profile-understanding-agent-runtime-handoff.md
git commit -m "feat(profile-understanding): prepare v2 agent integration surface"
```

---

## Self-Review

### Spec coverage

- resource access model: covered by Task 3
- richer output contract: covered by Tasks 1 and 2
- wizard consuming relation-aware output: covered by Task 4
- runtime / LangSmith visibility handoff: covered by Task 5
- end-to-end verification: covered by Task 6

### Placeholder scan

No `TODO`, `TBD`, or “implement later” placeholders remain in the plan.

### Type consistency

The plan keeps the same V2 core types across backend and frontend:

- `entity_classification`
- `skill_links`
- `evidence_map`
- `confidence_map`
- `questions`

