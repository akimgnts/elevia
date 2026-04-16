# Profile Structuring Agent Design

## Goal

Add a backend-authoritative structuring layer that runs automatically after CV parsing and canonical mapping, enriches the existing `career_profile`, persists a deterministic `structuring_report`, and feeds downstream product surfaces without introducing a parallel profile format.

## Why This Exists

The current pipeline already produces:

- parsed `ProfileStructuredV1`
- canonical skill signals
- enriched `career_profile`
- per-experience `skill_links`

But the product still lacks a single reusable backend agent responsible for turning raw parse artifacts into a coherent, inspectable structuring result. That missing layer causes fragmentation between:

- parsed responsibilities
- mapped canonical skills
- tools
- unresolved signals
- frontend clarification needs

The new agent fills that gap without changing matching or scoring.

## Existing Seam

The correct integration point already exists in:

- `apps/api/src/compass/pipeline/cache_hooks.py`

Current backend flow:

1. `structure_profile_text_v1(cv_text, debug=False)`
2. `from_profile_structured_v1(...)`
3. persist `profile["career_profile"]`
4. persist `profile["experiences"] = to_experience_dicts(career_profile)`

The new agent must run after `from_profile_structured_v1(...)` has built the initial `CareerProfile`, then enrich that same structure in place.

This preserves the current contract for:

- frontend profile editor
- `apply_pack_cv_engine`
- `html_renderer`

## Recommended Architecture

Use a lightweight orchestrator:

- `ProfileStructuringAgent` is the stable product-facing entrypoint
- internal deterministic helpers perform narrow tasks
- existing logic is reused where sound, especially the current `skill_link_builder`

This avoids duplicating the whole pipeline while still giving the repo a reusable, persistent structuring module.

## New Module

Create:

- `apps/api/src/compass/structuring/profile_structuring_agent.py`

Public interface:

```python
class ProfileStructuringAgent:
    def __init__(self, mode: str = "deterministic"):
        ...

    def run(self, profile_input: dict) -> dict:
        """
        Returns:
        {
            "career_profile_enriched": {...},
            "structuring_report": {...}
        }
        """
```

`mode="deterministic"` is the only supported operational mode for now. Any future LLM mode must remain optional and off by default.

## Inputs

The agent consumes a dict assembled in `cache_hooks.py`:

```python
{
    "career_profile": career_profile_dict,
    "raw_profile": raw_profile,
    "canonical_skills": canonical_skills,
    "unresolved": unresolved,
    "removed": removed,
}
```

Input meanings:

- `career_profile`: output of `from_profile_structured_v1(...)`
- `raw_profile`: current profile payload being built in cache hooks
- `canonical_skills`: canonical mapping results already available from the parse pipeline or profile payload
- `unresolved`: unresolved mapping candidates already surfaced by the pipeline
- `removed`: rejected or removed noisy candidates already surfaced by the pipeline

If some optional inputs are absent, the agent must degrade gracefully and still return deterministic output.

## Outputs

The agent returns:

```python
{
    "career_profile_enriched": {...},
    "structuring_report": {
        "used_signals": [...],
        "uncertain_links": [...],
        "questions_for_user": [...],
        "canonical_candidates": [...],
        "rejected_noise": [...],
        "unresolved_candidates": [...],
        "stats": {
            "experiences_processed": int,
            "skill_links_created": int,
            "questions_generated": int,
            "coverage_ratio": float,
        },
    },
}
```

Persistence requirements:

- `profile["career_profile"] = career_profile_enriched`
- `profile["experiences"] = to_experience_dicts(...)` from the enriched profile
- `profile["structuring_report"] = structuring_report`

## Responsibilities

### 1. Experience Restructuring

For each experience in `career_profile.experiences`:

- dedupe repeated responsibilities
- trim whitespace and empty lines
- preserve source meaning
- keep phrasing short and action-based when a simple deterministic normalization is possible
- never synthesize responsibilities from unrelated signals

This step is cleanup, not generation. If a responsibility is weak but valid, keep it rather than invent a better one.

### 2. Skill Link Construction

`skill_links` remain the primary structured unit:

```json
{
  "skill": { "label": "Data Analysis", "uri": null },
  "tools": [{ "label": "Python" }],
  "context": "Analyse des écarts avec Python et SQL",
  "autonomy_level": "autonomous"
}
```

Rules:

- use only existing canonical skills
- never invent a new skill label or URI
- attach tools only on strong evidence
- when exactly one canonical skill exists, allow deterministic fallback linking
- prefer precision over recall
- ambiguous links go to `uncertain_links`, not to persisted `skill_links`

Implementation direction:

- reuse the existing `build_skill_links_for_experience(...)`
- extend around it rather than replacing it wholesale
- keep persisted `skill_links` conservative

### 3. Signal Classification

The agent must classify what happened during structuring into:

- `used_signals`
- `rejected_noise`
- `unresolved_candidates`
- `uncertain_links`

Expected meanings:

- `used_signals`: responsibilities, canonical skills, tools, context snippets actually used in the enriched profile
- `rejected_noise`: signals ignored because too generic, duplicated, empty, or too weak
- `unresolved_candidates`: unresolved parse/canonical fragments worth surfacing later
- `uncertain_links`: possible tool-to-skill or skill-to-context relations that failed the precision threshold

This classification is for transparency and product diagnostics, not for scoring.

### 4. Question Generation

The agent generates clarification prompts only when ambiguity is actionable.

Format:

```json
[
  {
    "type": "tool",
    "experience_index": 0,
    "question": "Quel outil principal utilisiez-vous pour cette activité de reporting ?"
  }
]
```

Rules:

- at most 3 to 5 questions per experience
- only when ambiguity exists
- short, concrete, user-facing wording
- no speculative or broad interview-style questions

Question types allowed:

- `autonomy`
- `tool`
- `skill`
- `context`

### 5. Canonical Improvement Loop

The agent should extract potential future canonical improvements without writing into the canonical store.

Format:

```json
[
  {
    "raw_value": "powerbi",
    "normalized_value": "power bi",
    "type": "tool",
    "confidence": 0.82,
    "reason": "appears repeatedly in experience tools but not in canonical skill labels"
  }
]
```

Rules:

- informative only
- deterministic confidence values or discrete heuristic scores converted to float
- no automatic mutation of aliases or canonical data

## Determinism And Idempotence

The agent must be:

- deterministic-first
- idempotent
- stable on repeated runs over the same input

That means:

- no randomness
- no clock-based variation in payload output
- stable ordering for all emitted lists where possible
- dedupe rules must preserve a deterministic order

## Integration Plan

### `cache_hooks.py`

After initial `career_profile` creation:

1. materialize the profile input dict
2. run `ProfileStructuringAgent(mode="deterministic")`
3. replace `career_profile_dict`
4. persist `structuring_report`
5. rebuild `profile["experiences"]` from the enriched profile
6. emit `STRUCTURING_STATS` log line

Important:

- no changes to matching keys such as `skills_uri`, `languages`, `education_level`
- no changes to `matching_v1` or score core

### `career_profile.py`

Keep `CareerProfile` as the canonical structured payload. Avoid introducing a second enriched schema. If needed, add helper conversion functions that support the agent, but do not alter the contract expected by existing consumers.

## Logging

The agent must produce structured stats:

```python
STRUCTURING_STATS = {
    "experiences_processed": int,
    "skill_links_created": int,
    "questions_generated": int,
    "coverage_ratio": float,
}
```

Recommended coverage definition:

- ratio of experiences with at least one persisted `skill_link` over total processed experiences

Logs are informational only.

## Testing Strategy

Create:

- `apps/api/tests/test_profile_structuring_agent.py`

Required tests:

- creates `skill_links` from existing canonical signals only
- never hallucinates non-canonical skills
- returns deterministic output on repeated runs
- maps unresolved ambiguity to `questions_for_user`
- extracts `canonical_candidates` without mutating canonical storage

Integration coverage must also extend existing tests:

- `apps/api/tests/test_career_profile_v2_integration.py`
- `apps/api/tests/test_apply_pack_cv_engine.py`
- `apps/api/tests/test_html_renderer.py`

Key assertions:

- agent runs automatically in `run_profile_cache_hooks()`
- `profile["career_profile"]` is enriched
- `profile["structuring_report"]` is persisted
- `profile["experiences"]` still exposes `skill_links`
- downstream document generation remains intact

## Non-Goals

This design explicitly does not do the following:

- modify scoring core
- modify `matching_v1`
- create a second profile format
- mutate canonical storage automatically
- add mandatory LLM behavior
- move structuring authority into the frontend

## Risks

### Risk 1: Over-enrichment

If the agent becomes too permissive, `skill_links` quality drops and product trust decreases.

Mitigation:

- keep persisted links conservative
- surface ambiguity in `uncertain_links` and `questions_for_user`

### Risk 2: Duplicate logic with `career_profile.py`

If cleanup and link-building logic diverge between extractor and agent, the pipeline becomes harder to reason about.

Mitigation:

- keep the extractor responsible for baseline profile construction
- keep the agent responsible for post-extraction structuring enrichment
- reuse current builders where possible

### Risk 3: Downstream contract drift

If the agent changes the shape of `career_profile`, Apply Pack or renderer paths could break.

Mitigation:

- enrich only within the existing schema
- add regression coverage on document generation

## Final Recommendation

Implement the new structuring layer as a deterministic backend orchestrator that enriches the existing `career_profile`, persists a `structuring_report`, and reuses current `skill_link` logic instead of replacing the whole pipeline.

This gives the product the missing bridge between parsing and product usage while keeping schema stability and downstream compatibility.
