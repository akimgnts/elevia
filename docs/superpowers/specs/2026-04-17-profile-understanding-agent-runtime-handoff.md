# Profile Understanding Agent Runtime Handoff

**Date:** 2026-04-17

## Purpose

This document hands off the V2 `profile-understanding-agent` from repo integration work to the external runtime team.

The repo is **not** the agent runtime. It only owns:

- the product-side contract
- the adapter boundary
- the wizard UI
- the mapping into the current `career_profile`

The external runtime owns the real agent behavior.

## Recommended Runtime

Use:

- `LangGraph` for graph orchestration, checkpoints, and durable execution
- `Agent Server` to expose the runtime as a callable service
- `LangSmith` for traces, runs, threads, dashboards, and Studio inspection

This is the minimum stack that satisfies:

- agent autonomy
- memory and resumability
- future team-of-agents orchestration
- web visibility outside the repo

## Visibility Model

The agent will only be visible on the web after it is deployed as a real runtime and instrumented with LangSmith.

Repo code alone is not enough.

Expected flow:

1. implement the external runtime graph
2. enable LangSmith tracing for runtime calls
3. deploy via Agent Server or equivalent LangGraph-compatible runtime
4. execute real runs
5. inspect traces, threads, outputs, and tool calls in LangSmith / Studio

## Runtime Responsibility

The runtime must:

- understand profile signal across parsing outputs, CV content, and user answers
- call Elevia resources and market APIs through explicit tools
- distinguish `experience`, `project`, `education`, `certification`, `skill`, and `tool`
- produce relation-aware output, especially `skill -> tools -> context -> autonomy`
- preserve both open signal and canonical mapped signal
- generate confidence-aware clarification questions only where needed

The runtime must not depend on prompt text stored in this repo.

## Required Runtime Inputs

The runtime should accept a normalized payload containing:

- parsed CV payload
- raw CV text or excerpts when available
- accepted, rejected, and pending parser signals
- current `career_profile`
- canonical skills and tool references
- existing profile conventions
- prior wizard answers
- session or thread identifiers

## Required Runtime Outputs

The runtime should return the V2 contract expected by the repo integration:

- `session_id`
- `status`
- `provider`
- `trace_summary`
- `entity_classification`
- `proposed_profile_patch`
- `skill_links`
- `evidence_map`
- `confidence_map`
- `questions`

### Output Rules

- `entity_classification` must separate entity types explicitly
- `skill_links` must preserve the relation between skill, tool, context, and autonomy
- `evidence_map` must retain provenance
- `confidence_map` must allow the wizard to prioritize confirmation
- `questions` must target uncertainty, not restate obvious facts

## Resource Tooling Requirements

The runtime should expose or consume tools for:

- parser signal inspection
- canonical skill search
- tool and software lookup
- market and employment resource lookup
- profile convention lookup
- evidence trace recovery

Tool calls should be visible in LangSmith traces.

## Repo-to-Runtime Boundary

The repo integration should remain thin:

- backend adapter calls external runtime
- frontend wizard renders runtime output
- profile save logic maps runtime output into existing profile models

Do not move runtime orchestration logic back into the repo.

## Integration Note

The current repo implementation is an MVP adapter and wizard shell. It is useful for contract validation, but it is not the final agent runtime.

The next practical step is to replace the fallback provider with a real external runtime implementing this handoff.

## Handoff Checklist

- define the external runtime service
- implement the LangGraph state graph
- wire resource tools and Elevia APIs
- enable LangSmith tracing
- expose the runtime to the repo adapter
- validate the V2 response contract against the wizard
- verify traces and threads appear in LangSmith
