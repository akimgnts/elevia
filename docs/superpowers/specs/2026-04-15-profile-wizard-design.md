# Profile Wizard Design

## Goal

Turn the current Profile page into a strict, guided wizard that helps the user validate what the backend structuring agent understood from the CV, instead of asking the user to fill a large free-form profile editor.

The wizard must consume existing backend outputs:

- `career_profile`
- `career_profile.experiences[*].skill_links`
- `structuring_report`
- `structuring_report.questions_for_user`

No backend change is required for this phase.

## Why This Change

The backend now produces a real structuring layer:

- enriched `career_profile`
- rebuilt `skill_links`
- `structuring_report`
- clarification questions

But the current product still exposes Profile mostly as an editor. That means the user does not yet benefit from the main value of the new backend layer:

- understanding what the system inferred
- validating ambiguity instead of retyping everything
- correcting structure instead of filling raw forms

The Profile page should now become the validation interface for the structuring agent.

## Current Frontend State

The current frontend already provides the critical inputs:

- `apps/web/src/pages/ProfilePage.tsx`
  - already reads and normalizes `career_profile`
  - already renders `skill_links`
  - already persists enriched profile edits
- `apps/web/src/store/profileStore.ts`
  - already stores the full `userProfile`
  - already persists parse results, so `structuring_report` is already available once present in the backend payload

This means the wizard can be built by extending current frontend structures rather than creating a new data flow.

## Product Decision

Use a strict wizard inside the existing `/profile` route.

This means:

- keep one page route: `/profile`
- introduce internal step state
- show only the current step as the main surface
- allow backward navigation
- control forward progression through wizard rules

The wizard is strict because the product flow now requires:

`Analyse -> Profil -> Cockpit -> Inbox`

The Profile page must visibly enforce that sequence without adding fragile route-level guards.

## Recommended Approach

Use a single-route wizard container inside `ProfilePage.tsx`.

Recommended internal steps:

1. `Ce que l’agent a compris`
2. `Vos expériences structurées`
3. `Questions de clarification`
4. `Validation finale`

This is the best fit because it:

- preserves existing routing
- preserves current store and save flows
- keeps implementation incremental
- aligns with the backend structuring layer already built

Avoid:

- multi-route profile wizard
- parallel wizard state store disconnected from `userProfile`
- replacing all existing editor controls at once

## Strict Product Rules

These rules are mandatory for the wizard to create real product value rather than becoming an extra UI layer.

### 1. Free-form Profile mode is no longer the default

The current full-form Profile editor must stop being the primary experience.

Strict rule:

- the default `/profile` experience is the wizard
- the old complete form is not shown by default
- legacy fields must be:
  - hidden by default
  - exposed only inside Step 2 when needed
  - or available behind an explicit `mode avancé`

The product must not show the user a full raw profile form as the first interaction after parsing.

### 2. Structured information is primary, legacy inputs are secondary

The wizard validates and corrects the agent’s output.

That means:

- `skill_links`
- `questions_for_user`
- `structuring_report`

are the primary surfaces.

Legacy field editing remains a fallback, not the main interaction model.

## Wizard Structure

### Step 1. Agent Understanding

Purpose:

- show the user what the backend structuring layer understood from the uploaded CV
- build trust before asking for edits
- create an immediate perception of time saved and work already done

Content:

- summary counts:
  - structured experiences
  - `skill_links`
  - unresolved candidates
  - questions generated
- clear value block:
  - what was detected automatically
  - what the user would otherwise have had to fill manually
  - a simple estimate of structuring gain
- concise overview of the main structured experiences
- highlight uncertain areas from `structuring_report`

Example product framing:

- `4 expériences structurées automatiquement`
- `18 compétences détectées`
- `9 skill_links construits`

The user should understand in under a few seconds that the system already did meaningful work on their behalf.

Data sources:

- `career_profile.experiences`
- `structuring_report.stats`
- `structuring_report.uncertain_links`
- `structuring_report.rejected_noise`

Primary CTA:

- `Continuer vers mes expériences`

Secondary CTA:

- optional back-to-analysis only if already supported by current shell flow

### Step 2. Structured Experiences

Purpose:

- let the user validate and adjust the structured experiences rather than starting from a blank form

Strict layout rule:

- one experience = one card
- one card = at most 3 visible blocks by default:
  - main skill structure
  - associated tools
  - impact / context

Content per experience:

- primary skill signal via `skill_links`
- associated tools
- impact and context
- autonomy only where it helps interpretation

Strict UI rule:

- not more than a small number of visible editable fields by default
- no return to a 10-field experience form as the main surface
- extra legacy fields, if still needed, must be collapsed behind an advanced edit affordance

This step must feel like constrained guided correction, not a classic editor.

Primary CTA:

- `Continuer vers les questions`

### Step 3. Clarification Questions

Purpose:

- surface only the ambiguities the backend could not resolve confidently

Primary source:

- `structuring_report.questions_for_user`

Presentation rules:

- grouped by experience when possible
- short and actionable
- no more than the current backend output

Allowed question types:

- autonomy
- tool
- skill
- context

Answer behavior:

- answers should write back into the same local profile state used by the rest of `ProfilePage`
- answers must directly modify the underlying `career_profile`
- the user should not need to understand internal report terminology

This is critical to avoid:

- duplicated state
- divergence between answers and profile data
- loss of downstream value for Apply Pack and renderer flows

If no questions exist:

- render a lightweight confirmation state instead of an empty page

Primary CTA:

- `Continuer vers la validation`

### Step 4. Final Validation

Purpose:

- provide a final summary before the user leaves Profile for the Cockpit

Content:

- profile completeness
- number of structured experiences
- number of `skill_links`
- remaining ambiguities, if any
- next-step reminder: Cockpit then Inbox
- projection toward the next product surface
- a lightweight opportunity preview when available

Example direction:

- `Vous êtes maintenant prêt à voir vos opportunités`
- mini preview such as matched offers count or readiness for Cockpit/Inbox

The step must connect the validation effort to the next visible user value.

Primary CTA:

- `Valider mon profil`

Secondary CTA:

- `Voir mon cockpit`

This step should make the product hierarchy explicit:

- analysis parsed the CV
- profile validated the structure
- cockpit now becomes useful

## Navigation Rules

The wizard must be strict but not brittle.

Rules:

- user can move backward freely
- user should not skip directly to final validation from the first step
- forward progression can require basic readiness checks
- no extra route guards are needed outside the page

Recommended minimal readiness rules:

- Step 1 -> Step 2: always allowed if a profile exists
- Step 2 -> Step 3: allowed once at least one experience exists
- Step 3 -> Step 4: always allowed, even if some questions remain unanswered
- final validation can still show residual ambiguity rather than hard-blocking the user

This keeps the flow guided without becoming frustrating.

## Post-Validation Replay

The wizard needs a defined behavior when the user comes back later to `/profile`.

Required mode:

- after first validation, the page enters a post-validation mode
- the initial surface becomes a summary / review entry point
- the user sees:
  - a short validated profile summary
  - current structuring status
  - a clear `modifier mon profil` entry back into the wizard

This avoids replay confusion and prevents the page from feeling like it restarts from zero every time.

The post-validation mode should still preserve the wizard model:

- summary first
- guided editing second
- raw full-form editing never restored as the default

## Fallback Behavior

If the backend payload is incomplete, the page must degrade cleanly.

Fallback rules:

- if `structuring_report` is absent:
  - fall back to the current Profile experience editor mode
- if `questions_for_user` is empty:
  - Step 3 becomes a confirmation step
- if `skill_links` are sparse:
  - reuse existing manual editor controls

This preserves compatibility during transitional states and old saved profiles.

## Frontend Architecture

Keep `/profile` as the only route.

Recommended internal composition:

- `ProfilePage.tsx`
  - owns wizard step state
  - owns normalized profile state
  - remains save authority
- extracted presentational components as needed:
  - `ProfileWizardHeader`
  - `AgentUnderstandingStep`
  - `StructuredExperiencesStep`
  - `ClarificationQuestionsStep`
  - `ProfileValidationStep`

These components should remain thin and local to the Profile domain.

No new global store is needed.

## Data Model Expectations

Frontend uses existing profile payload shape only:

- `userProfile.career_profile`
- `userProfile.structuring_report`
- `career_profile.experiences[*].skill_links`

The frontend should not reinterpret backend diagnostics into a second structure beyond lightweight normalized UI helpers.

## UX Principles

The page should feel like:

- “we understood this from your CV”
- “confirm or correct”
- “resolve what is ambiguous”
- “continue to cockpit”

It should not feel like:

- “fill a long profile form”
- “edit every field manually”
- “re-enter everything the parser already saw”

Design priorities:

- strong step hierarchy
- visible progress
- minimal noise
- obvious primary CTA
- structured information first, raw fields second

## Risks

### Risk 1. Wizard becomes a thin skin over the same large form

If all fields remain equally visible, the product benefit disappears.

Mitigation:

- show only the relevant step
- make `skill_links` and questions primary
- progressively disclose legacy editing controls

### Risk 2. Old saved profiles lack `structuring_report`

This could produce empty or broken steps.

Mitigation:

- explicit fallback mode
- question step collapses gracefully

### Risk 3. Users feel blocked by strict progression

If the wizard blocks too aggressively, it harms adoption.

Mitigation:

- allow backward navigation
- use soft readiness checks
- allow final validation even with residual ambiguity

## Final Recommendation

Implement a strict wizard inside the current `/profile` page that transforms Profile from an editor into a validation flow for the backend structuring layer.

This is the shortest path to visible user value from the new backend architecture, while preserving the existing route, store, schema, and save flow.
