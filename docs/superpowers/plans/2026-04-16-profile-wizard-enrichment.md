# Profile Wizard Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect backend `enrichment_report` to the frontend Profile wizard so auto-filled enrichment is visible, traceable, editable, and merged into the guided clarification flow.

**Architecture:** Extend the existing `/profile` wizard without changing backend logic. `ProfilePage.tsx` becomes the integration point for both `structuring_report` and `enrichment_report`, Step 1 becomes a value-oriented understanding screen, Step 2 becomes multi-`skill_link` aware with provenance badges, and Step 3 merges/deduplicates questions from both backend layers.

**Tech Stack:** React, TypeScript, existing profile wizard components in `apps/web/src/components/profile`, Zustand profile store, Vite build, Python guardrail tests for UI contract checks.

---

## File Map

- Modify: `apps/web/src/pages/ProfilePage.tsx`
  - Read and normalize `enrichment_report`, merge wizard questions, manage provenance-aware editing, and wire all steps.
- Modify: `apps/web/src/components/profile/profileWizardTypes.ts`
  - Add shared types for enrichment report, auto-filled entries, merged question records, and provenance metadata.
- Modify: `apps/web/src/components/profile/AgentUnderstandingStep.tsx`
  - Display understanding + enrichment value summary, including the “What This Changes For You” block.
- Modify: `apps/web/src/components/profile/StructuredExperiencesStep.tsx`
  - Render all `skill_links` per experience and expose per-link correction controls.
- Modify: `apps/web/src/components/profile/ClarificationQuestionsStep.tsx`
  - Accept merged questions and surface source-aware, deduplicated clarification flow.
- Modify: `apps/web/src/components/profile/ProfileValidationStep.tsx`
  - Explicitly close the product loop: matching, CV, cockpit.
- Modify: `apps/web/tests/test_profile_wizard_flow.py`
  - Add guardrail assertions for enrichment integration and multi-`skill_link` flow.
- Verify only: `apps/web/src/pages/AnalyzePage.tsx`
  - No code change expected; ensure analyze still routes to `/profile` cleanly after wizard update.

### Task 1: Add shared enrichment types and failing wizard guardrails

**Files:**
- Modify: `apps/web/src/components/profile/profileWizardTypes.ts`
- Modify: `apps/web/tests/test_profile_wizard_flow.py`

- [ ] **Step 1: Add failing Python guardrail assertions for enrichment wiring**

```python
def test_profile_page_reads_enrichment_report_and_merges_questions() -> None:
    source = PROFILE_PAGE.read_text(encoding="utf-8")

    assert "enrichment_report" in source
    assert "priority_signals" in source
    assert "learning_candidates" in source
    assert "confidence_scores" in source
    assert "mergedQuestions" in source or "mergeWizardQuestions" in source


def test_profile_page_handles_multi_skill_link_editing() -> None:
    source = PROFILE_PAGE.read_text(encoding="utf-8")

    assert "selectedSkillLinkIndex" in source
    assert "experience.skill_links.map" in source or ".map((link, linkIndex) =>" in source
    assert "Ajouté automatiquement" in source
```

- [ ] **Step 2: Run the guardrail test file to verify RED**

Run: `./.venv/bin/pytest apps/web/tests/test_profile_wizard_flow.py -q`
Expected: FAIL because enrichment wiring and multi-`skill_link` handling are not yet present.

- [ ] **Step 3: Extend shared wizard types for enrichment data**

```ts
export type EnrichmentAutoFilled = {
  experience_index?: number;
  skill_link_index?: number | null;
  target_field?: "tools" | "context" | "autonomy_level" | "skill_link";
  value?: string;
  confidence?: number;
  reason?: string;
};

export type EnrichmentQuestionType = "autonomy" | "tool" | "skill" | "context";

export type EnrichmentQuestion = {
  type?: EnrichmentQuestionType;
  experience_index?: number;
  skill_link_index?: number | null;
  target_field?: "tools" | "context" | "autonomy_level" | "skill_link" | "skill";
  question?: string;
  confidence?: number;
};

export type EnrichmentReport = {
  auto_filled?: EnrichmentAutoFilled[];
  suggestions?: Array<Record<string, unknown>>;
  questions?: EnrichmentQuestion[];
  reused_rejected?: Array<Record<string, unknown>>;
  confidence_scores?: Array<Record<string, unknown>>;
  priority_signals?: Array<Record<string, unknown>>;
  canonical_candidates?: Array<Record<string, unknown>>;
  learning_candidates?: Array<Record<string, unknown>>;
  stats?: Record<string, number>;
};

export type EnrichmentTraceEntry = {
  source?: string;
  confidence?: number;
};
```

- [ ] **Step 4: Re-run the guardrail test and confirm it still fails on wiring, not on missing types**

Run: `./.venv/bin/pytest apps/web/tests/test_profile_wizard_flow.py -q`
Expected: FAIL, but now specifically because `ProfilePage.tsx` does not yet consume the new types and flow.

### Task 2: Wire enrichment into ProfilePage state and Step 1

**Files:**
- Modify: `apps/web/src/pages/ProfilePage.tsx`
- Modify: `apps/web/src/components/profile/AgentUnderstandingStep.tsx`
- Test: `apps/web/tests/test_profile_wizard_flow.py`

- [ ] **Step 1: Add failing expectations for Step 1 value messaging**

```python
def test_profile_page_step_one_includes_value_moment() -> None:
    source = PROFILE_PAGE.read_text(encoding="utf-8")

    assert "What This Changes For You" in source or "Ce que ça change pour vous" in source
    assert "autoFilledCount" in source
    assert "remainingQuestionsCount" in source
```

- [ ] **Step 2: Run the single guardrail test and verify RED**

Run: `./.venv/bin/pytest apps/web/tests/test_profile_wizard_flow.py::test_profile_page_step_one_includes_value_moment -q`
Expected: FAIL because Step 1 does not yet expose enrichment value.

- [ ] **Step 3: Normalize enrichment_report and compute merged Step 1 metrics in ProfilePage**

```ts
const enrichmentReport = normalizeEnrichmentReport(fullProfile.enrichment_report);
const mergedQuestions = mergeWizardQuestions(
  structuringReport.questions_for_user || [],
  enrichmentReport.questions || [],
);
const autoFilledCount = enrichmentReport.auto_filled?.length || 0;
const remainingQuestionsCount = mergedQuestions.length;
const prioritySignalCount = enrichmentReport.priority_signals?.length || 0;
```

Add helpers:

```ts
function normalizeEnrichmentReport(value: unknown): EnrichmentReport {
  if (!value || typeof value !== "object") return {};
  const rec = value as Record<string, unknown>;
  return {
    auto_filled: Array.isArray(rec.auto_filled) ? (rec.auto_filled as EnrichmentAutoFilled[]) : [],
    suggestions: Array.isArray(rec.suggestions) ? (rec.suggestions as Array<Record<string, unknown>>) : [],
    questions: Array.isArray(rec.questions) ? (rec.questions as EnrichmentQuestion[]) : [],
    reused_rejected: Array.isArray(rec.reused_rejected) ? (rec.reused_rejected as Array<Record<string, unknown>>) : [],
    confidence_scores: Array.isArray(rec.confidence_scores) ? (rec.confidence_scores as Array<Record<string, unknown>>) : [],
    priority_signals: Array.isArray(rec.priority_signals) ? (rec.priority_signals as Array<Record<string, unknown>>) : [],
    canonical_candidates: Array.isArray(rec.canonical_candidates) ? (rec.canonical_candidates as Array<Record<string, unknown>>) : [],
    learning_candidates: Array.isArray(rec.learning_candidates) ? (rec.learning_candidates as Array<Record<string, unknown>>) : [],
    stats: rec.stats && typeof rec.stats === "object" ? (rec.stats as Record<string, number>) : {},
  };
}
```

- [ ] **Step 4: Update Step 1 component props and content**

```tsx
<AgentUnderstandingStep
  report={structuringReport}
  autoFilledCount={autoFilledCount}
  remainingQuestionsCount={remainingQuestionsCount}
  prioritySignalCount={prioritySignalCount}
  autoFilledItems={enrichmentReport.auto_filled || []}
/>
```

Inside `AgentUnderstandingStep.tsx`, render:
- existing structuring summary
- new `Ce que ça change pour vous` block
- grouped list of auto-filled items with badge `Ajouté automatiquement`
- optional confidence display

- [ ] **Step 5: Run the guardrail file to verify GREEN for Step 1 wiring**

Run: `./.venv/bin/pytest apps/web/tests/test_profile_wizard_flow.py -q`
Expected: at least the Step 1 enrichment assertions now pass; remaining failures should move to Step 2 / Step 3 gaps.

### Task 3: Make Step 2 multi-skill_link aware with enrichment provenance

**Files:**
- Modify: `apps/web/src/pages/ProfilePage.tsx`
- Modify: `apps/web/src/components/profile/StructuredExperiencesStep.tsx`
- Test: `apps/web/tests/test_profile_wizard_flow.py`

- [ ] **Step 1: Add a failing guardrail for per-link editing and provenance badges**

```python
def test_profile_page_tracks_selected_skill_link_index_and_user_validated_state() -> None:
    source = PROFILE_PAGE.read_text(encoding="utf-8")

    assert "selectedSkillLinkIndex" in source
    assert "user_validated" in source or "userValidated" in source
    assert "Ajouté automatiquement" in source
```

- [ ] **Step 2: Run the single guardrail test to verify RED**

Run: `./.venv/bin/pytest apps/web/tests/test_profile_wizard_flow.py::test_profile_page_tracks_selected_skill_link_index_and_user_validated_state -q`
Expected: FAIL because Step 2 still centers the first link only.

- [ ] **Step 3: Add per-experience selected link state and provenance helpers in ProfilePage**

```ts
const [selectedSkillLinkIndex, setSelectedSkillLinkIndex] = useState<Record<number, number>>({});

function getSelectedSkillLinkIndex(experienceIndex: number, experience: ExperienceV2): number {
  const current = selectedSkillLinkIndex[experienceIndex] ?? 0;
  const total = experience.skill_links?.length || 0;
  if (total === 0) return 0;
  return current >= 0 && current < total ? current : 0;
}
```

Add a helper to resolve enrichment provenance from `career_profile.enrichment_meta` for a given `experienceIndex`, `skillLinkIndex`, and field.

- [ ] **Step 4: Replace first-link-only editing with selected-link editing**

Update the `renderCorrectionPanel(index)` logic so it:
- renders a selector or tabs for all `skill_links`
- edits the selected `skill_link` index, not hardcoded `0`
- shows enrichment provenance badges on `tools`, `context`, and `autonomy`

Use a pattern like:

```tsx
const activeIndex = getSelectedSkillLinkIndex(index, experience);
const activeLink = experience.skill_links?.[activeIndex] ?? fallbackLink;
```

- [ ] **Step 5: When user edits an auto-filled field, clear the auto badge and mark UI state as user-validated**

Implementation direction:

```ts
function markFieldUserValidated(experienceIndex: number, skillLinkIndex: number, field: "tools" | "context" | "autonomy_level") {
  setEditedEnrichmentFields((current) => ({
    ...current,
    [`${experienceIndex}:${skillLinkIndex}:${field}`]: "user_validated",
  }));
}
```

This can remain frontend-only metadata for now. The UI must stop showing `Ajouté automatiquement` once the user changes the field.

- [ ] **Step 6: Update StructuredExperiencesStep to render all links**

Each experience card should render one block per `skill_link` with:
- skill
- tools
- context
- autonomy
- provenance badge when applicable

- [ ] **Step 7: Re-run the guardrail file and confirm GREEN for multi-link display/editing**

Run: `./.venv/bin/pytest apps/web/tests/test_profile_wizard_flow.py -q`
Expected: Step 2 assertions pass; any remaining failures should now be Step 3 merged-question issues.

### Task 4: Merge and deduplicate structuring + enrichment questions in Step 3

**Files:**
- Modify: `apps/web/src/pages/ProfilePage.tsx`
- Modify: `apps/web/src/components/profile/ClarificationQuestionsStep.tsx`
- Test: `apps/web/tests/test_profile_wizard_flow.py`

- [ ] **Step 1: Add a failing guardrail for merged question deduplication**

```python
def test_profile_page_merges_and_deduplicates_questions() -> None:
    source = PROFILE_PAGE.read_text(encoding="utf-8")

    assert "mergeWizardQuestions" in source
    assert "experience_index" in source
    assert "target_field" in source
```

- [ ] **Step 2: Run the single guardrail test to verify RED**

Run: `./.venv/bin/pytest apps/web/tests/test_profile_wizard_flow.py::test_profile_page_merges_and_deduplicates_questions -q`
Expected: FAIL because no merge/dedupe helper exists yet.

- [ ] **Step 3: Add a merge helper in ProfilePage**

```ts
function mergeWizardQuestions(
  structuringQuestions: StructuringQuestion[],
  enrichmentQuestions: EnrichmentQuestion[],
): StructuringQuestion[] {
  const seen = new Set<string>();
  const merged: StructuringQuestion[] = [];

  for (const question of [...structuringQuestions, ...enrichmentQuestions]) {
    const experienceIndex = question.experience_index ?? -1;
    const targetField = question.target_field ?? "unknown";
    const key = `${experienceIndex}:${targetField}`;
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(question);
  }

  return merged;
}
```

- [ ] **Step 4: Feed merged questions into Step 3 instead of structuring-only questions**

```tsx
<ClarificationQuestionsStep
  questions={mergedQuestions}
  experiences={experiences}
  onAnswer={applyClarificationAnswer}
  onNext={() => setWizardStep("validation")}
/>
```

- [ ] **Step 5: Ensure answered questions no longer appear if the relevant field is already set**

Before returning merged questions, filter out items whose target field is already resolved in current `experiences` state.

- [ ] **Step 6: Re-run the guardrail file to verify GREEN**

Run: `./.venv/bin/pytest apps/web/tests/test_profile_wizard_flow.py -q`
Expected: PASS

### Task 5: Close the product loop in Step 4 and run full verification

**Files:**
- Modify: `apps/web/src/components/profile/ProfileValidationStep.tsx`
- Verify only: `apps/web/src/pages/AnalyzePage.tsx`
- Test: `apps/web/tests/test_profile_wizard_flow.py`

- [ ] **Step 1: Add a failing guardrail for loop closure messaging**

```python
def test_profile_validation_step_closes_the_product_loop() -> None:
    source = VALIDATION_STEP.read_text(encoding="utf-8")

    assert "matching" in source.lower()
    assert "cv" in source.lower()
    assert "cockpit" in source.lower()
```

- [ ] **Step 2: Run the targeted guardrail test to verify RED**

Run: `./.venv/bin/pytest apps/web/tests/test_profile_wizard_flow.py::test_profile_validation_step_closes_the_product_loop -q`
Expected: FAIL because the step does not yet explicitly restate the downstream product usage.

- [ ] **Step 3: Update ProfileValidationStep with explicit outcome messaging**

Render a short block such as:
- this profile will be used for matching
- this profile will be used for CV generation
- this profile will be used in the cockpit

and keep the existing CTA flow toward cockpit.

- [ ] **Step 4: Run the frontend build and guardrail verification**

Run: `./.venv/bin/pytest apps/web/tests/test_profile_wizard_flow.py -q`
Expected: PASS

Run: `cd apps/web && npm run build`
Expected: PASS

### Task 6: Refresh the graph and inspect final diff

**Files:**
- Verify only: `apps/web/src/pages/ProfilePage.tsx`
- Verify only: `apps/web/src/components/profile/AgentUnderstandingStep.tsx`
- Verify only: `apps/web/src/components/profile/StructuredExperiencesStep.tsx`
- Verify only: `apps/web/src/components/profile/ClarificationQuestionsStep.tsx`
- Verify only: `apps/web/src/components/profile/ProfileValidationStep.tsx`
- Verify only: `apps/web/src/components/profile/profileWizardTypes.ts`
- Verify only: `apps/web/tests/test_profile_wizard_flow.py`

- [ ] **Step 1: Run graphify update after code changes**

Run: `graphify update .`
Expected: graph update completes successfully.

- [ ] **Step 2: Inspect the final diff for only the planned wizard-enrichment files**

Run: `git diff -- apps/web/src/pages/ProfilePage.tsx apps/web/src/components/profile/AgentUnderstandingStep.tsx apps/web/src/components/profile/StructuredExperiencesStep.tsx apps/web/src/components/profile/ClarificationQuestionsStep.tsx apps/web/src/components/profile/ProfileValidationStep.tsx apps/web/src/components/profile/profileWizardTypes.ts apps/web/tests/test_profile_wizard_flow.py`
Expected: diff shows only the planned enrichment wizard integration changes.
