# CV Understanding Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a real CV-understanding layer that segments the CV into typed blocks, extracts mission-level signal, reconciles it with deterministic parsing and references, and only then feeds a lightweight confirmation wizard plus the existing `career_profile`.

**Architecture:** Keep the true understanding runtime external, but refactor the repo-side contract and fallback logic around hierarchical CV understanding instead of generic wizard prompts. The backend becomes responsible for block segmentation, mission-unit extraction, signal reconciliation, and `career_profile_patch` generation, while the frontend only presents what is already understood and asks targeted confirmations when needed.

**Tech Stack:** FastAPI, Pydantic, React, TypeScript, Zustand, existing deterministic parsing pipeline, existing `career_profile` model, future external LangGraph/LangSmith runtime

---

### Task 1: Define the hierarchical CV-understanding contract

**Files:**
- Modify: `apps/api/src/profile_understanding/schemas.py`
- Modify: `apps/web/src/lib/api.ts`
- Test: `apps/api/tests/test_profile_understanding_route.py`

- [ ] **Step 1: Expand the backend test with hierarchical fields**

Add assertions to `apps/api/tests/test_profile_understanding_route.py`:

```python
        self.assertIn("document_blocks", data)
        self.assertIn("mission_units", data)
        self.assertIn("open_signal", data)
        self.assertIn("canonical_signal", data)
        self.assertIn("understanding_status", data)
        self.assertIsInstance(data["document_blocks"], list)
        self.assertIsInstance(data["mission_units"], list)
        self.assertIsInstance(data["open_signal"], dict)
        self.assertIsInstance(data["canonical_signal"], dict)
        self.assertIsInstance(data["understanding_status"], dict)
```

- [ ] **Step 2: Run the route test to verify the new fields fail**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_route
```

Expected: FAIL because the current V2 contract does not yet expose the hierarchical understanding fields.

- [ ] **Step 3: Add the backend schema models**

Update `apps/api/src/profile_understanding/schemas.py` with explicit models:

```python
class ProfileUnderstandingDocumentBlock(BaseModel):
    id: str
    block_type: str
    label: str
    source_text: str | None = None
    confidence: float | None = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProfileUnderstandingMissionUnit(BaseModel):
    id: str
    block_ref: str
    experience_ref: str | None = None
    mission_text: str
    context: str | None = None
    skill_candidates_open: List[str] = Field(default_factory=list)
    tool_candidates_open: List[str] = Field(default_factory=list)
    quantified_signals: List[str] = Field(default_factory=list)
    autonomy_hypothesis: str | None = None
    evidence: List[ProfileUnderstandingEvidence] = Field(default_factory=list)
```

and extend `ProfileUnderstandingSessionResponse`:

```python
    document_blocks: List[ProfileUnderstandingDocumentBlock] = Field(default_factory=list)
    mission_units: List[ProfileUnderstandingMissionUnit] = Field(default_factory=list)
    open_signal: Dict[str, Any] = Field(default_factory=dict)
    canonical_signal: Dict[str, Any] = Field(default_factory=dict)
    understanding_status: Dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: Mirror the contract in `apps/web/src/lib/api.ts`**

Add matching TypeScript interfaces:

```ts
export interface ProfileUnderstandingDocumentBlock {
  id: string;
  block_type: string;
  label: string;
  source_text?: string | null;
  confidence?: number | null;
  metadata: Record<string, unknown>;
}

export interface ProfileUnderstandingMissionUnit {
  id: string;
  block_ref: string;
  experience_ref?: string | null;
  mission_text: string;
  context?: string | null;
  skill_candidates_open: string[];
  tool_candidates_open: string[];
  quantified_signals: string[];
  autonomy_hypothesis?: string | null;
  evidence: ProfileUnderstandingEvidence[];
}
```

- [ ] **Step 5: Re-run the route test**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_route
```

Expected: still FAIL, now because the service does not populate the new fields yet.

### Task 2: Segment the profile into typed CV blocks

**Files:**
- Modify: `apps/api/src/profile_understanding/service.py`
- Test: `apps/api/tests/test_profile_understanding_route.py`

- [ ] **Step 1: Add a failing test assertion for block types**

Extend the route test:

```python
        block_types = {block["block_type"] for block in data["document_blocks"]}
        self.assertIn("experience", block_types)
        self.assertIn("project", block_types)
```

- [ ] **Step 2: Run the test to confirm missing block extraction**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_route
```

Expected: FAIL because `document_blocks` is empty or missing.

- [ ] **Step 3: Implement minimal block segmentation**

Add to `apps/api/src/profile_understanding/service.py`:

```python
def _build_document_blocks(career_profile: Dict[str, Any]) -> List[ProfileUnderstandingDocumentBlock]:
    blocks: List[ProfileUnderstandingDocumentBlock] = []
    for index, experience in enumerate(career_profile.get("experiences", []) or []):
        if not isinstance(experience, dict):
            continue
        label = str(experience.get("title") or "Experience").strip()
        company = str(experience.get("company") or "").strip()
        source_text = " | ".join(
            part for part in [
                label,
                company,
                " ; ".join(str(item).strip() for item in (experience.get("responsibilities") or []) if str(item).strip()),
            ] if part
        )
        blocks.append(ProfileUnderstandingDocumentBlock(
            id=f"block-exp-{index}",
            block_type="experience",
            label=label,
            source_text=source_text or None,
            confidence=0.78,
            metadata={"experience_ref": f"exp-{index}", "company": company},
        ))
```

Repeat the same pattern for:
- `projects`
- `education`
- `certifications`

- [ ] **Step 4: Return `document_blocks` from the session response**

In `_create_stub_session(...)`:

```python
        document_blocks = _build_document_blocks(career_profile)
```

and include:

```python
            document_blocks=document_blocks,
```

- [ ] **Step 5: Re-run the route test**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_route
```

Expected: PASS on block-type assertions, still failing later on mission extraction if those assertions already exist.

### Task 3: Extract mission-level units from experience blocks

**Files:**
- Modify: `apps/api/src/profile_understanding/service.py`
- Test: `apps/api/tests/test_profile_understanding_route.py`

- [ ] **Step 1: Add failing assertions for mission-level extraction**

Extend the route test:

```python
        self.assertTrue(data["mission_units"])
        first_mission = data["mission_units"][0]
        self.assertIn("mission_text", first_mission)
        self.assertIn("skill_candidates_open", first_mission)
        self.assertIn("tool_candidates_open", first_mission)
```

- [ ] **Step 2: Run the test to verify mission units are missing**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_route
```

Expected: FAIL because `mission_units` is empty or absent.

- [ ] **Step 3: Implement mission-unit extraction**

Add to `apps/api/src/profile_understanding/service.py`:

```python
def _extract_quantified_signals(text: str) -> List[str]:
    import re
    return re.findall(r"\\b\\d+(?:[%.,]\\d+)?\\b[^.;,\\n]*", text)


def _build_mission_units(
    career_profile: Dict[str, Any],
    source_context: Dict[str, Any],
) -> List[ProfileUnderstandingMissionUnit]:
    mission_units: List[ProfileUnderstandingMissionUnit] = []
    candidate_labels = _extract_candidate_labels(source_context)

    for index, experience in enumerate(career_profile.get("experiences", []) or []):
        if not isinstance(experience, dict):
            continue
        for mission_index, responsibility in enumerate(experience.get("responsibilities", []) or []):
            mission_text = str(responsibility or "").strip()
            if not mission_text:
                continue
            mission_units.append(ProfileUnderstandingMissionUnit(
                id=f"mission-exp-{index}-{mission_index}",
                block_ref=f"block-exp-{index}",
                experience_ref=f"exp-{index}",
                mission_text=mission_text,
                context=mission_text,
                skill_candidates_open=[str(skill.get("label") or "").strip() for skill in (experience.get("canonical_skills_used") or []) if str(skill.get("label") or "").strip()],
                tool_candidates_open=_dedupe_strings([*_experience_tools_label(experience), *candidate_labels[:3]]),
                quantified_signals=_extract_quantified_signals(mission_text),
                autonomy_hypothesis=str(experience.get("autonomy_level") or "").strip() or None,
                evidence=[_build_evidence("mission_text", source_value=mission_text, confidence=0.72, mapping_status="open")],
            ))
    return mission_units
```

- [ ] **Step 4: Return `mission_units` from the session response**

In `_create_stub_session(...)`:

```python
        mission_units = _build_mission_units(career_profile, payload.source_context)
```

and include:

```python
            mission_units=mission_units,
```

- [ ] **Step 5: Re-run the route test**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_route
```

Expected: PASS on mission-unit assertions.

### Task 4: Reconcile deterministic parser outputs into understanding statuses

**Files:**
- Modify: `apps/api/src/profile_understanding/service.py`
- Test: `apps/api/tests/test_profile_understanding_route.py`

- [ ] **Step 1: Add failing assertions for reconciliation fields**

Extend the route test:

```python
        self.assertIn("accepted", data["understanding_status"])
        self.assertIn("rejected", data["understanding_status"])
        self.assertIn("needs_confirmation", data["understanding_status"])
        self.assertIn("validated_labels", data["open_signal"])
        self.assertIn("rejected_tokens", data["open_signal"])
```

- [ ] **Step 2: Run the test to verify the reconciliation layer is missing**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_route
```

Expected: FAIL because `open_signal`, `canonical_signal`, and `understanding_status` are incomplete.

- [ ] **Step 3: Implement open/canonical/reconciliation payloads**

Add to `apps/api/src/profile_understanding/service.py`:

```python
def _build_open_signal(source_context: Dict[str, Any], mission_units: Sequence[ProfileUnderstandingMissionUnit]) -> Dict[str, Any]:
    return {
        "validated_labels": list(source_context.get("validated_labels", []) or []),
        "rejected_tokens": list(source_context.get("rejected_tokens", []) or []),
        "tight_candidates": list(source_context.get("tight_candidates", []) or []),
        "mission_skill_candidates": [unit.skill_candidates_open for unit in mission_units],
        "mission_tool_candidates": [unit.tool_candidates_open for unit in mission_units],
    }


def _build_canonical_signal(entity_classification: Dict[str, List[ProfileUnderstandingEntity]]) -> Dict[str, Any]:
    return {
        "skills": [item.model_dump() for item in entity_classification.get("skills", [])],
        "tools": [item.model_dump() for item in entity_classification.get("tools", [])],
    }


def _build_understanding_status(source_context: Dict[str, Any], mission_units: Sequence[ProfileUnderstandingMissionUnit]) -> Dict[str, Any]:
    return {
        "accepted": list(source_context.get("validated_labels", []) or []),
        "rejected": [
            token.get("label") or token.get("token")
            for token in (source_context.get("rejected_tokens", []) or [])
            if isinstance(token, dict)
        ],
        "needs_confirmation": [unit.id for unit in mission_units if not unit.tool_candidates_open or not unit.autonomy_hypothesis],
        "mission_units_count": len(mission_units),
    }
```

- [ ] **Step 4: Return these fields from the session**

In `_create_stub_session(...)`:

```python
        open_signal = _build_open_signal(payload.source_context, mission_units)
        canonical_signal = _build_canonical_signal(entity_classification)
        understanding_status = _build_understanding_status(payload.source_context, mission_units)
```

and include them in `ProfileUnderstandingSessionResponse(...)`.

- [ ] **Step 5: Re-run the route test**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_route
```

Expected: PASS.

### Task 5: Build `skill_links` from mission units, not from flat experience skills

**Files:**
- Modify: `apps/api/src/profile_understanding/service.py`
- Test: `apps/api/tests/test_profile_understanding_route.py`

- [ ] **Step 1: Add a failing assertion for mission-driven links**

Extend the route test:

```python
        self.assertTrue(any(link.get("context") == "Produced weekly reporting for leadership" for link in data["skill_links"]))
```

- [ ] **Step 2: Run the test to confirm the current link builder is too flat**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_route
```

Expected: FAIL if context is not reliably driven by a mission unit.

- [ ] **Step 3: Refactor `_build_skill_links(...)` to consume mission units**

Replace the flat skill-link construction with a mission-first version:

```python
def _build_skill_links_from_missions(
    career_profile: Dict[str, Any],
    mission_units: Sequence[ProfileUnderstandingMissionUnit],
) -> List[ProfileUnderstandingSkillLink]:
    experience_lookup = {
        f"exp-{index}": experience
        for index, experience in enumerate(career_profile.get("experiences", []) or [])
        if isinstance(experience, dict)
    }
    links: List[ProfileUnderstandingSkillLink] = []
    for unit in mission_units:
        experience = experience_lookup.get(unit.experience_ref or "")
        if not experience:
            continue
        skills = experience.get("canonical_skills_used", []) or []
        for skill in skills:
            label = str(skill.get("label") or "").strip()
            if not label:
                continue
            links.append(ProfileUnderstandingSkillLink(
                experience_ref=unit.experience_ref,
                skill={"label": label, "uri": skill.get("uri"), "source": "mission_unit"},
                tools=[{"label": tool, "source": "mission_unit"} for tool in unit.tool_candidates_open[:4]],
                context=unit.mission_text,
                autonomy_level=unit.autonomy_hypothesis,
                evidence=list(unit.evidence),
            ))
    return links
```

- [ ] **Step 4: Wire the new builder into `_create_stub_session(...)`**

Use:

```python
        skill_links = _build_skill_links_from_missions(career_profile, mission_units)
```

instead of the older flat builder.

- [ ] **Step 5: Re-run the route test**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_route
```

Expected: PASS with mission-derived `context` on the links.

### Task 6: Make the wizard a confirmation surface, not an “AI page”

**Files:**
- Modify: `apps/web/src/pages/ProfileUnderstandingPage.tsx`
- Verify: `apps/web/src/App.tsx`

- [ ] **Step 1: Change the page copy to focus on confirmation**

In `apps/web/src/pages/ProfileUnderstandingPage.tsx`, replace the header text with copy like:

```tsx
title="Verifier les points cles de votre parcours"
description="Nous avons deja structure votre parcours, vos missions et vos signaux principaux. Verifiez seulement les points qui ont besoin de confirmation avant finalisation du profil."
```

and remove wording that refers explicitly to “agent” or “IA”.

- [ ] **Step 2: Promote understood content before questions**

Add a summary block driven by `document_blocks` and `mission_units` before the question list:

```tsx
{session?.document_blocks?.map((block) => (
  <div key={block.id} className="rounded-[1.25rem] border border-slate-200 bg-white px-4 py-3">
    <div className="text-sm font-semibold text-slate-950">{block.label}</div>
    <div className="mt-1 text-xs uppercase tracking-[0.14em] text-slate-400">{block.block_type}</div>
    {block.source_text && <p className="mt-2 text-sm leading-6 text-slate-600">{block.source_text}</p>}
  </div>
))}
```

- [ ] **Step 3: Make questions read like confirmations, not generic input requests**

When rendering questions, prepend a short intro:

```tsx
<p className="text-sm leading-6 text-slate-600">
  Nous avons besoin d'une confirmation sur ce point pour finaliser votre profil.
</p>
```

and keep `suggested_answer` prefilled.

- [ ] **Step 4: Build and verify the app**

Run in `apps/web`:

```bash
npm run build
```

Expected: PASS with only the usual Vite chunk-size warning.

### Task 7: Inject understood content automatically into `career_profile`

**Files:**
- Modify: `apps/web/src/pages/ProfileUnderstandingPage.tsx`

- [ ] **Step 1: Map mission-derived content into the final profile**

Extend the merge logic in `mergeSessionSkillLinksIntoCareerProfile(...)` so that mission-driven links reinforce the experience fields without overwriting valid existing data:

```tsx
    const missionContexts = mergedLinks
      .map((link) => link.context?.trim())
      .filter((value): value is string => Boolean(value));

    experiences[experienceIndex] = {
      ...currentExperience,
      skill_links: mergedLinks,
      canonical_skills_used: mergedSkills,
      tools: mergedTools,
      autonomy_level: currentExperience.autonomy_level ?? autonomyFromLinks,
      responsibilities:
        Array.isArray(currentExperience.responsibilities) && currentExperience.responsibilities.length > 0
          ? currentExperience.responsibilities
          : missionContexts,
    };
```

- [ ] **Step 2: Ensure unanswered questions do not block understood content**

Keep `handleContinue()` permissive:

```tsx
    const answeredCareer = (session?.questions ?? []).reduce((careerProfile, question) => {
      const answer = answers[question.id]?.trim();
      if (!answer) return careerProfile;
      return applyAnswerToCareerProfile(careerProfile, question, answer);
    }, currentCareer);
```

No hard gate on all questions being answered.

- [ ] **Step 3: Rebuild frontend**

Run:

```bash
npm run build
```

Expected: PASS.

### Task 8: Expose the current runtime mode clearly for product debugging

**Files:**
- Modify: `apps/web/src/pages/ProfileUnderstandingPage.tsx`

- [ ] **Step 1: Add a discreet runtime badge**

Render the provider mode in a low-emphasis debug badge:

```tsx
{session?.provider && (
  <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-[11px] font-medium text-slate-500">
    source: {session.provider}
  </div>
)}
```

This keeps the implementation visible to the team without exposing “AI agent” as product copy.

- [ ] **Step 2: Rebuild frontend**

Run:

```bash
npm run build
```

Expected: PASS.

### Task 9: Final verification

**Files:**
- Verify only

- [ ] **Step 1: Run backend syntax validation**

Run:

```bash
python3 -m py_compile apps/api/src/profile_understanding/schemas.py apps/api/src/profile_understanding/service.py apps/api/src/api/routes/profile_understanding.py apps/api/src/api/routes/profile_understanding_resources.py apps/api/src/api/main.py
```

Expected: PASS.

- [ ] **Step 2: Run backend tests in the project venv**

Run:

```bash
apps/api/.venv/bin/python -m unittest apps.api.tests.test_profile_understanding_route apps.api.tests.test_profile_understanding_resources
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```bash
npm run build
```

Expected: PASS with only the usual Vite warning.

- [ ] **Step 4: Smoke-test the user path**

Verify manually:

1. analyze a CV
2. open `/profile-understanding`
3. confirm the page first shows understood content
4. confirm questions are phrased as validations
5. continue even if some questions stay empty
6. confirm `career_profile` is enriched in `/profile`

---

## Self-Review

### Spec coverage

- hierarchical block understanding: Tasks 1 and 2
- mission-level extraction: Task 3
- deterministic reconciliation: Task 4
- mission-driven `skill_links`: Task 5
- wizard as confirmation surface only: Task 6
- automatic profile injection: Task 7
- hidden-but-visible runtime mode: Task 8

### Placeholder scan

No `TODO`, `TBD`, or vague placeholders remain.

### Type consistency

The same hierarchy is used across the plan:

- `document_blocks`
- `mission_units`
- `open_signal`
- `canonical_signal`
- `understanding_status`
- `skill_links`
- `career_profile_patch`
