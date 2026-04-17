# Profile Understanding Agent V2 Design

**Date:** 2026-04-17

## Goal

Design the real external `profile-understanding-agent` so it can:

- access Elevia resources and market-facing APIs
- distinguish profile entities with higher precision
- preserve both open user signal and canonical mapped signal
- produce actionable `skill_links` that connect skill, tool, context, and autonomy
- feed the existing Profile page with richer structured output
- be deployable and observable through LangGraph + Agent Server + LangSmith

This V2 replaces the earlier MVP framing where the wizard mainly collected generic clarifications. The target is now a true profile-comprehension agent with domain tools and structured relational output.

## Non-Goals

- replacing the deterministic parser
- redesigning the final Profile page
- changing matching core or score logic
- collapsing all future agent roles into one agent
- forcing all profile data into canonical skills only

## Why V2 Is Needed

The current MVP integration is useful as a shell, but it is not yet the right agent behavior.

Its main limitations are:

- it does not yet use Elevia resource tools
- it does not reason over market and reference data
- it asks generic questions instead of high-value clarification questions
- it does not explicitly separate raw/open signal from canonical/mapped signal
- it does not yet model entity types strongly enough
- it does not guarantee a precise `skill -> tool -> context -> autonomy` relationship

That last point is the critical gap. A profile is not useful enough if the system only knows that `Python`, `SQL`, and `Data Analysis` appear somewhere. It must know:

- in which experience or project they were used
- whether a label is a skill, tool, certification, education signal, or role clue
- which tool supported which skill
- under what business context and autonomy level

## Recommended Platform

Use:

- `LangGraph` for the agent graph, state transitions, checkpoints, and durable execution
- `Agent Server` to expose the agent runtime as a service the product can call
- `LangSmith` for traces, threads, runs, debugging, dashboards, and Studio access

Do not rely on the repo alone to make the agent visible in the web UI.

### Visibility Model

To see the agent on the web:

1. run the real agent in a LangGraph-compatible runtime
2. connect it to LangSmith tracing
3. deploy it through Agent Server or a LangSmith-compatible deployment path
4. execute real runs on the agent
5. inspect it in LangSmith / Studio

Code living in the repo is not enough by itself. The repo only provides the product-side integration boundary.

Sources used for this decision:

- [LangSmith Observability](https://docs.langchain.com/langsmith/observability)
- [Monitor projects with dashboards](https://docs.langchain.com/langsmith/dashboards)
- [Use threads](https://docs.langchain.com/langsmith/use-threads)
- [Runs](https://docs.langchain.com/langsmith/runs)
- [Observability in Studio](https://docs.langchain.com/langsmith/observability-studio)

## Agent Role

### Name

`profile-understanding-agent`

### Responsibility

Transform all available profile signal into a structured profile understanding package before the user reaches the final Profile page.

The agent owns:

- entity understanding
- skill/tool disambiguation
- relation building
- confidence-aware question generation
- profile enrichment proposal

It does not own:

- final profile editing UX
- offer matching
- application execution
- final orchestration across the whole agent team

## Position in the Product Flow

Target flow:

`Analyse -> Profile Understanding Wizard -> Profil -> Cockpit -> Inbox -> Candidatures -> Marche`

The wizard remains, but it becomes an interface for confirming high-value hypotheses from the agent, not a thin manual questionnaire.

## Runtime Boundary

The repo must contain only:

- the contract for calling the agent
- the client / adapter used to reach the external runtime
- the wizard UI that consumes the structured result
- mapping logic into the current `career_profile`

The external runtime must contain:

- the role definition
- graph logic
- tool calling logic
- memory behavior
- subagent behavior if enabled later
- question generation policy
- resource access rules

This preserves the requirement that the repo must not contain the real agent brain.

## Resource Access Model

The agent must be able to use dedicated tools over Elevia resources.

### Required Tool Families

- `parser-signal-tool`
  - read kept, rejected, pending, and ambiguous parser signals
- `canonical-skill-tool`
  - search canonical skills and existing mapped labels
- `tool-reference-tool`
  - search known tools / software / platforms already used by the product
- `market-resource-tool`
  - query market-facing job resources and other employment data sources connected to Elevia
- `profile-convention-tool`
  - inspect current profile structuring conventions, including existing `career_profile` and `skill_links` patterns
- `evidence-trace-tool`
  - recover provenance for an inferred field or relation

### Tooling Principle

The agent should not guess first when Elevia already has a useful source of truth. It should search internal references and APIs before asking the user.

## Input Package

The agent input should be a normalized bundle composed by the product.

### Core Inputs

- parsed CV payload
- raw CV text or segmented document excerpts when available
- accepted parser outputs
- rejected parser outputs
- pending parser outputs
- current top-level profile
- current `career_profile`
- profile intelligence fields if present

### Reference Inputs

- canonical skills
- tool references
- internal mapping conventions
- existing skill suggestions
- existing profile structuring conventions
- market API context when available

### Session Inputs

- thread id / session id
- user answers from previous wizard turns
- saved checkpoints
- prior confidence map if the wizard resumes

## Truth Model

The model must preserve both open signal and normalized signal.

### Truth Priority

1. explicit user answer
2. validated deterministic parser output
3. evidence-backed agent inference
4. weak or ambiguous parser signal

### Dual-Signal Requirement

For relevant fields, the system should keep both:

- `raw/open signal`
  - what the CV or user actually said, even if not mapped
- `canonical/mapped signal`
  - what Elevia successfully aligned to internal references

This matters because users may mention:

- tools not in the reference base
- soft skills not yet modeled
- certifications not yet normalized
- new competencies that should remain visible even before mapping

The agent must never drop useful signal only because it cannot map it yet.

## Entity Model

The agent must explicitly classify profile content into entity types.

### Required Entity Types

- `experience`
  - a real professional role
- `project`
  - a scoped project that may live inside an experience or stand alone
- `education`
  - school, degree, field, institution, period
- `certification`
  - certificate, exam, issuer, status
- `skill`
  - a capability or competence
- `tool`
  - a software, platform, framework, or operational instrument
- `language`
  - spoken language skill
- `role_signal`
  - title or function clue used to understand career positioning

### Classification Principle

The agent must not flatten all extracted labels into “skills”. It must classify them first, then decide how they should appear in the profile.

## Core Relational Output

The most important structured output is the relation layer.

### Mandatory Relation Shape

For each relevant experience or project, the agent should be able to emit relations equivalent to:

- `skill`
- `tools[]`
- `context`
- `autonomy_level`
- `evidence`

This should map naturally onto the existing `skill_links` structure already supported by the repo.

### Example

Instead of:

- `Python`
- `SQL`
- `Power BI`
- `Data Analysis`

The agent should produce:

- experience: `Data Analyst - Acme`
- skill: `Data Analysis`
- tools: `Python`, `SQL`, `Power BI`
- context: `weekly performance reporting for leadership`
- autonomy_level: `autonomous`

## Output Contract

The external runtime should return a structured package with six core sections.

### 1. `entity_classification`

Structured entities identified from the profile:

- experiences
- projects
- education items
- certifications
- tools
- skills
- role signals

### 2. `proposed_profile_patch`

A patch aligned to the current Elevia profile schema, especially:

- `career_profile.experiences`
- `career_profile.projects`
- `career_profile.education`
- `career_profile.certifications`
- `career_profile.selected_skills`
- `career_profile.pending_skill_candidates`
- `career_profile.skill_links`

### 3. `skill_links`

A normalized relation-first view that can be written into each experience.

### 4. `evidence_map`

For each important field or relation:

- source type
- supporting text or source reference
- confidence
- mapping status

### 5. `questions`

A prioritized list of targeted confirmation questions for the wizard.

### 6. `confidence_map`

Confidence at the level of:

- entity
- relation
- profile field
- question cluster

## Question Strategy

The wizard should only ask where confirmation adds value.

### Good Questions

- “Sur cette mission, utilisiez-vous surtout `Power BI`, `Excel` ou `SQL` pour faire l’analyse de performance ?”
- “Cette ligne correspond-elle a une vraie experience pro, ou plutot a un projet d’ecole ?”
- “Cette certification est-elle active et souhaitez-vous la faire apparaitre dans le profil ?”
- “Pour cette competence, travailliez-vous en execution, en autonomie, ou en ownership ?”

### Bad Questions

- generic profile completion questions with no grounding
- questions the parser already resolved confidently
- questions with no downstream impact on relation quality

### Question Trigger Rules

Generate questions when:

- entity classification is ambiguous
- a skill/tool boundary is uncertain
- a skill-to-tool link is plausible but not confirmed
- autonomy is missing on an otherwise strong experience
- a high-value credential appears but is incomplete
- a raw user signal cannot yet be mapped safely

## Memory and Session Model

The agent must support:

- stateful threads
- resumable sessions
- checkpointed wizard progress
- memory scoped by user and by session
- later support for subagent delegation

### Memory Principle

Memory should preserve:

- prior user confirmations
- rejected hypotheses
- accepted mappings
- preferred terms used by the user
- unresolved open signals that should be revisited later

## Observability and Web Visibility

The deployed agent should be inspectable in LangSmith.

### Required Visibility

- runs
- threads
- traces
- tool calls
- input/output payloads
- dashboards per project
- Studio access for thread debugging

### Practical Answer to the Product Need

If you want to “see the agent on the web”, you need the deployed external runtime connected to LangSmith. The repo-side stub and API route are not enough to surface it in LangSmith.

## Orchestrator Compatibility

This agent is one member of a future team.

The orchestrator should be able to:

- call it with a normalized input package
- pass resource permissions and tool context
- receive structured outputs
- decide whether to continue the wizard
- hand the result to another specialist agent

The agent must therefore stay role-bounded: profile understanding only.

## Failure and Fallback Model

The system must handle three degraded modes cleanly.

### Mode A: external agent unavailable

Fallback to:

- deterministic parser output
- repo-side profile editing
- optional lightweight question set

### Mode B: resource tools partially unavailable

Fallback to:

- parser evidence
- local references
- lower confidence on unresolved links

### Mode C: mapping impossible

Fallback to:

- preserve open signal
- surface it as pending / unmapped rather than dropping it

## Implementation Consequences

This V2 spec implies that the next implementation cycle should focus on four areas:

1. external runtime design
2. resource tool contract design
3. richer output contract for entity and relation layers
4. wizard refactor to consume confidence-based questions instead of generic freeform prompts

## Success Criteria

The design succeeds when:

- the agent can consult Elevia resources rather than only CV text
- the system preserves both open signal and canonical signal
- entity types are cleanly differentiated
- `skill_links` become substantially richer and more trustworthy
- the wizard asks fewer but better questions
- the agent can be observed in LangSmith once deployed
- the repo remains only the integration surface, not the embedded agent brain
