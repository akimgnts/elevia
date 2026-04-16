# Profile Wizard Enrichment Design

## Goal

Connect backend `enrichment_report` to the frontend Profile wizard so the product exposes both:

- what the system understood (`structuring_report`)
- what the system completed automatically (`enrichment_report`)

This is a product orchestration change, not a new architecture. The existing wizard remains the interaction surface, but it must start showing the backend intelligence that already exists.

## Why This Exists

The backend now has two real layers:

- `ProfileStructuringAgent`
- `ProfileEnrichmentAgent`

But the current product only exposes the first one in the Profile wizard.

As a result:

- the user sees structuring
- the user does not see enrichment
- auto-filled intelligence is effectively invisible
- the product behaves as if the enrichment layer barely exists

That wastes most of the value of the new backend.

## Product Rule

For V1 of the wizard integration:

**auto-filled enrichment is already applied**

It is not shown as a pending proposal.

The product must say:

- we understood this
- we completed this automatically
- you can correct it if needed

It must not fall back to:

- we propose that you fill this form

## Core UX Rule

Every `auto_filled` enrichment must be:

- visible
- traceable
- editable

If the system auto-filled a tool, context, or autonomy field, the user must be able to see:

- that it was added automatically
- that it came from enrichment
- the confidence when available

The user must still be able to correct or remove it.

## Existing Seam

The relevant frontend surface already exists in:

- `apps/web/src/pages/ProfilePage.tsx`

The page already reads:

- `career_profile`
- `structuring_report`
- `profile_wizard_meta`

The new work extends this page to also consume:

- `enrichment_report`
- `career_profile.enrichment_meta`

No backend change is required for this frontend iteration.

## Scope

This design covers:

1. Step 1 enrichment visibility
2. Step 2 multi-`skill_links` editing and enrichment provenance
3. Step 3 merged question flow

This design does not yet cover:

- cockpit usage of `priority_signals`
- CV generation usage of `enrichment_report`
- backend unification of structuring responsibilities

Those are later phases.

## Step 1 — Understanding Plus Enrichment

The first wizard step must stop showing only “what the system understood”.

It must show:

- structured experiences count
- structured `skill_links` count
- number of auto-filled enrichments applied
- number of remaining questions
- number of priority signals if available

The copy must make the value explicit:

- what was understood automatically
- what was completed automatically
- what the user does not have to fill manually

### Required value block

Step 1 must include a non-technical block:

## What This Changes For You

This block must not read like backend telemetry.

It must read like product value, for example:

- your profile is already usable
- most of the information was completed automatically
- only a few targeted points still need clarification

The purpose of Step 1 is not just to summarize system activity.
It must create the user “click” moment:

- the system already did meaningful work
- the profile is no longer a blank form
- the remaining effort is limited and understandable

### Required UI blocks

#### A. What We Understood

Use the existing `structuring_report` summary:

- experiences structured
- `skill_links` identified
- ambiguities remaining

#### B. What We Completed Automatically

New block sourced from `enrichment_report.auto_filled`

Display grouped by experience when possible.

Each item should expose:

- field type (`tool`, `context`, `autonomy`)
- value
- badge `Ajouté automatiquement`
- confidence when available

#### C. What Still Needs Confirmation

Display the count and short summary of merged wizard questions.

The intent is:

- “the system already did most of the work”
- “only a few targeted clarifications remain”

## Step 2 — Multi-SkillLink Experience Editing

The current Step 2 still behaves like a mono-`skill_link` correction surface because it edits only the first `skill_link`.

That is no longer acceptable.

### Required rule

Each experience must display **all** `skill_links`.

Editing must be tied to the selected `skill_link` index, not hardcoded to index `0`.

### Experience card model

One experience remains one card.

Inside the card, display one structured block per `skill_link`:

- skill
- tools
- context
- autonomy

Each `skill_link` block should also show enrichment provenance when available from `career_profile.enrichment_meta`.

### Provenance badges

If a field was added by enrichment, show a badge such as:

- `Ajouté automatiquement`
- optional confidence, for example `0.82`

Fields that may carry this provenance:

- tools
- context
- autonomy

Persisted pre-existing fields should not be mislabeled as auto-filled.

### Editing model

Default mode remains structured read mode.

When the user clicks `Corriger`:

- the panel opens for a specific `skill_link`
- edits apply to that `skill_link` index only
- the user can modify or remove previously auto-filled values

This keeps the wizard structured while respecting the multi-skill backend model.

## Step 3 — Merged Clarification Questions

Step 3 must stop using only `structuring_report.questions_for_user`.

It must merge:

- `structuring_report.questions_for_user`
- `enrichment_report.questions`

### Rules

- present one unified list
- preserve typed rendering (`autonomy`, `tool`, `skill`, `context`)
- keep `experience_index`
- keep `skill_link_index` when available
- keep `target_field`
- dedupe redundant questions by:
  - `experience_index`
  - `target_field`

### Priority

Display order should be:

1. structuring questions first
2. enrichment questions second

This keeps the harder structural ambiguities ahead of additive clarifications.

### Write-back rule

Answers still write directly into `career_profile` state.

The same rule already adopted for the wizard remains:

- no side bucket
- no separate unresolved form state
- the answer modifies the actual profile being edited

If a merged enrichment question becomes answered through user editing before Step 3:

- it should no longer surface as an active question
- deduplication should prevent near-identical duplicates from structuring and enrichment

## Data Contract

### New frontend reads

From `fullProfile`:

- `enrichment_report`
- `career_profile.enrichment_meta`

### Required normalization

Add local normalization helpers for:

- `enrichment_report.auto_filled`
- `enrichment_report.questions`
- `enrichment_report.priority_signals`
- `enrichment_report.confidence_scores`
- `enrichment_report.learning_candidates`

The normalization must be defensive and preserve backward compatibility when the report is absent.

## Fallback Rules

If `enrichment_report` is absent:

- the wizard must still work with `structuring_report`
- Step 1 omits enrichment summary
- Step 2 omits provenance badges
- Step 3 uses only structuring questions

This must degrade gracefully, not revert to the old full-form default.

## UI Rules

### Auto-fill behavior

- auto-fill is already applied
- never hidden
- never presented as “please fill this”
- always editable

### After user modification

If the user edits a field that was originally auto-filled:

- the `Ajouté automatiquement` badge must disappear for that field
- the field should be treated as user-validated in UI state

The exact backend persistence of this validation state can stay additive for now, but the frontend behavior must be explicit:

- once the user changes the value, it is no longer presented as a system-added untouched value

Otherwise the product creates trust confusion.

### Readability

- do not overload Step 1 with raw JSON-like diagnostics
- group enrichments into human-readable summaries
- keep confidence secondary, not dominant

### No regression into form chaos

- do not bring back the old full free-form profile as default
- advanced mode remains secondary
- structured reading remains the main path

## Files Expected To Change

- `apps/web/src/pages/ProfilePage.tsx`
- `apps/web/src/components/profile/AgentUnderstandingStep.tsx`
- `apps/web/src/components/profile/StructuredExperiencesStep.tsx`
- `apps/web/src/components/profile/ClarificationQuestionsStep.tsx`
- `apps/web/src/components/profile/profileWizardTypes.ts`

Additional helper components may be extracted if needed, but only if they support this exact wizard behavior.

## Success Criteria

This work is successful when:

- Step 1 visibly shows enrichment already applied
- Step 1 includes a clear “what this changes for you” value moment
- Step 2 shows all `skill_links`, not only the first one
- auto-filled fields are visibly traceable and editable
- edited auto-filled fields stop looking like untouched automatic output
- Step 3 uses both structuring and enrichment questions
- Step 3 deduplicates redundant merged questions
- the wizard still works if `enrichment_report` is missing
- the UI keeps a guided product flow instead of returning to a hidden full-form workflow

## Loop Closure

The wizard must explicitly close the product loop.

By the end of Step 3 or in Step 4, the user must be reminded that this profile will be used for:

- matching
- CV generation
- cockpit guidance

The product message should be explicit, for example:

- this profile will now be used to surface relevant opportunities

Without this reminder, the wizard explains intelligence but does not connect it to user outcome.

## Non-goals

This iteration does not:

- redesign the whole profile page
- move enrichment logic into the frontend
- change backend scoring or matching
- change `ProfileEnrichmentAgent` logic
- wire `priority_signals` into cockpit yet
- wire `enrichment_report` into CV generation yet
