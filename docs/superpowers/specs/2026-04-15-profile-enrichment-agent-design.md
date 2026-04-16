# Profile Enrichment Agent Design

## Goal

Add a backend-authoritative enrichment layer that runs automatically after `ProfileStructuringAgent`, enriches the existing `career_profile` additively, persists a deterministic `enrichment_report`, and improves profile completeness without reducing trust.

This agent is not allowed to create a second profile representation. It must work on the same `career_profile` already used by:

- frontend profile validation
- `apply_pack_cv_engine`
- `html_renderer`

## Why This Exists

The current backend now has a real structuring layer:

- CV parsing produces `ProfileStructuredV1`
- canonical mapping surfaces canonical skills, unresolved signals, and removed noise
- `ProfileStructuringAgent` turns that into conservative `skill_links` plus a `structuring_report`

What is still missing is a safe enrichment layer that can:

- improve incomplete experiences
- reuse weak signals without trusting them blindly
- surface suggestions and questions with confidence
- prepare a better clarification flow for the frontend

The enrichment layer must improve completeness, but it must never act like an aggressive guesser.

## Existing Seam

The correct integration point already exists in:

- `apps/api/src/compass/pipeline/cache_hooks.py`

Current relevant backend flow:

1. `structure_profile_text_v1(cv_text, debug=False)`
2. `from_profile_structured_v1(...)`
3. `ProfileStructuringAgent().run(...)`
4. persist `profile["career_profile"]`
5. persist `profile["structuring_report"]`
6. derive `profile["experiences"] = to_experience_dicts(...)`

The new agent must run after structuring and before the final persistence of enriched derived payloads:

1. build `career_profile`
2. run `ProfileStructuringAgent`
3. run `ProfileEnrichmentAgent`
4. persist:
   - `profile["career_profile"]`
   - `profile["structuring_report"]`
   - `profile["enrichment_report"]`
   - `profile["experiences"]`

This keeps one coherent backend profile pipeline:

`CV -> parsing -> canonical mapping -> structuring -> enrichment -> career_profile(final)`

## Recommended Architecture

Use a deterministic orchestrator:

- `ProfileEnrichmentAgent` is the stable product-facing entrypoint
- private helpers inside the same file perform narrow enrichment tasks
- existing `career_profile` and `skill_links` remain the canonical persisted structures
- `structuring_report` remains input context, not a replacement data model

This is intentionally conservative for V1. The agent should be able to enrich a partially complete profile, but when in doubt it should emit a suggestion or a question instead of changing the stored profile.

## New Module

Create:

- `apps/api/src/compass/structuring/profile_enrichment_agent.py`

Public interface:

```python
class ProfileEnrichmentAgent:
    def __init__(self):
        pass

    def run(self, profile_input: dict) -> dict:
        """
        Returns:
        {
            "career_profile_enriched": {...},
            "enrichment_report": {...}
        }
        """
```

This first version is deterministic-first only. Any future AI layer must remain optional, controlled, and off by default.

## Inputs

The agent consumes:

```python
{
    "career_profile": {...},
    "structuring_report": {...},
    "canonical_skills": [...],
    "unresolved": [...],
    "rejected_noise": [...],
}
```

Input meanings:

- `career_profile`: already structured profile produced by the current backend pipeline
- `structuring_report`: diagnostics and ambiguity output from `ProfileStructuringAgent`
- `canonical_skills`: canonical mapping output already available in the parse pipeline
- `unresolved`: weak unresolved parsing or mapping signals
- `rejected_noise`: weak or noisy signals that were previously rejected

The agent must degrade gracefully if some optional inputs are absent.

## Outputs

The agent returns:

```python
{
    "career_profile_enriched": {...},
    "enrichment_report": {
        "auto_filled": [...],
        "suggestions": [...],
        "questions": [...],
        "reused_rejected": [...],
        "confidence_scores": [...],
        "priority_signals": [...],
        "canonical_candidates": [...],
        "learning_candidates": [...],
        "stats": {
            "suggestions_count": int,
            "auto_filled_count": int,
            "questions_count": int,
        },
    },
}
```

Persistence requirements:

- `profile["career_profile"] = career_profile_enriched`
- `profile["enrichment_report"] = enrichment_report`
- `profile["experiences"] = to_experience_dicts(load_career_profile(career_profile_enriched))`

`enrichment_report` is product-facing. It is expected to feed the Profile wizard and later diagnostics surfaces.

## Auto-fill Traceability

Any enrichment actually written into `career_profile` must remain traceable in the profile payload itself.

This is required to avoid silent enrichment and preserve user trust.

For V1, any auto-filled field written by the enrichment agent must carry additive source metadata alongside the enriched value, without breaking the existing schema contract used by downstream consumers.

Implementation direction:

- preserve the existing field values used by current consumers
- add parallel additive metadata describing enrichment provenance
- never replace plain scalar business fields with incompatible structures

Recommended shape:

```json
{
  "enrichment_meta": {
    "experiences": [
      {
        "skill_links": [
          {
            "tools": [
              {
                "label": "Power BI",
                "source": "enrichment",
                "confidence": 0.8
              }
            ],
            "context": {
              "source": "enrichment",
              "confidence": 0.76
            }
          }
        ]
      }
    ]
  }
}
```

The exact metadata shape can be simplified during implementation, but the rule is fixed:

- every `auto_filled` mutation must be inspectable from the persisted profile payload
- the profile wizard must be able to explain where that value came from
- downstream readers that expect the current schema must keep working unchanged

## Core Safety Rule

For V1:

**any existing `skill_link` is protected**

Presence of a `skill_link` means the enrichment agent must treat it as a trusted persisted structure and may only enrich it non-destructively.

If a `skill_link` already exists, the agent may only:

- add a missing tool
- add missing context
- add missing autonomy
- add a suggestion linked to that `skill_link`
- add a user question
- add an uncertainty record

If a `skill_link` already exists, the agent must never:

- replace the `skill`
- replace or remove an existing tool
- rewrite non-empty `context`
- change already-set `autonomy_level`

This rule protects trust and keeps the agent additive.

## Responsibilities

### 1. Analyze all available signals per experience

For each experience, the agent inspects:

- `responsibilities`
- existing `skill_links`
- `canonical_skills_used`
- `tools`
- `structuring_report.used_signals`
- `structuring_report.uncertain_links`
- `unresolved`
- `rejected_noise`

The agent should interpret unresolved and rejected items as weak evidence only. They may support a suggestion or question, but they cannot justify aggressive auto-fill by themselves.

### 2. Enrich existing `skill_links` conservatively

When a `skill_link` exists:

- complete missing `tools` if there is one clear tool candidate with strong experience-level evidence
- complete missing `context` from the best supporting sentence fragment
- complete missing `autonomy_level` only from existing experience autonomy fields or equivalent deterministic mapping

Additional V1 guardrail:

If an auto-fill touches an existing `skill_link`, it is limited to:

- adding a missing tool
- adding empty context
- adding empty autonomy

and nothing else.

### 3. Create additive enrichment for sparse experiences

If an experience has no `skill_links` or has incomplete structure:

- reuse canonical skills only when they already exist in canonical inputs or strong explicit text evidence
- if one canonical skill already exists, prefer enriching that one rather than creating multiple speculative links
- if multiple tools are plausible, do not auto-fill
- if confidence is medium, emit a suggestion
- if confidence is low, emit a question

If no canonical match exists:

- do not inject anything into `career_profile`
- push the signal to `canonical_candidates`

### 4. Compute confidence deterministically

Use the mandatory confidence function:

```python
def compute_confidence(evidence_count, explicit_tool, keyword_strength, context_coherence):
    score = 0
    if explicit_tool:
        score += 0.4
    score += min(evidence_count * 0.2, 0.4)
    score += keyword_strength  # 0 -> 0.2
    score += context_coherence  # 0 -> 0.2
    return round(min(score, 1.0), 2)
```

Definitions:

- `evidence_count`: number of distinct, relevant deterministic signals found in the same experience
- `explicit_tool`: true when the tool label is explicitly present in the experience or linked sentence
- `keyword_strength`: bounded heuristic from `0.0` to `0.2` based on direct label or alias overlap
- `context_coherence`: bounded heuristic from `0.0` to `0.2` based on consistency between the candidate enrichment and the overall experience context

Context coherence exists to penalize technically possible but contextually weak enrichments.

Examples:

- `Python` in an explicitly analytical or engineering experience -> higher coherence
- `SAP` in a finance or operations context -> potentially higher coherence
- a tool with no nearby contextual support in the experience language -> low coherence

Decision rules:

- `>= 0.75` -> `auto_add`
- `0.50 - 0.74` -> `suggestion`
- `< 0.50` -> `question`

The thresholds are strict. Confidence is used to limit risk, not to maximize recall.

## Experience-level enrichment behavior

### Tool enrichment

Tools may be added automatically only when:

- the candidate tool is explicit
- the candidate maps cleanly to one experience and one target `skill_link`
- there is no competing tool ambiguity

If multiple tools are plausible:

- do not auto-fill
- emit a suggestion or question instead

### Context enrichment

Context must come from deterministic sentence fragments already present in the experience.

Rules:

- use the best short supporting responsibility fragment
- do not rewrite filled context
- do not synthesize business language beyond simple trimming

### Autonomy enrichment

Autonomy may be filled only when:

- `skill_link.autonomy_level` is empty
- the experience already has deterministic autonomy information

The agent must not infer autonomy from vague language or from weak unresolved signals.

### Skill enrichment

The agent must never invent a new skill.

It may only:

- attach a canonical skill already present in `canonical_skills`
- or use strong explicit text evidence that maps directly to an already known canonical skill

If this bar is not met:

- no injection into `career_profile`
- add a `canonical_candidate` or a user-facing question instead

## Report Structure

### `auto_filled`

Records deterministic enrichments actually written into `career_profile`.

Example:

```json
{
  "experience_index": 0,
  "skill_link_index": 0,
  "target_field": "tools",
  "value": "Power BI",
  "confidence": 0.8,
  "reason": "explicit tool in same responsibility sentence"
}
```

### `suggestions`

Records plausible but non-persisted enrichments.

These should be usable by the frontend wizard as “agent suggestions”, not as facts already accepted into the profile.

### `questions`

Records low-confidence or ambiguous gaps to clarify with the user.

Format:

```json
{
  "type": "tool|skill|context|autonomy",
  "experience_index": 0,
  "skill_link_index": 0,
  "target_field": "tools|skill|context|autonomy_level",
  "question": "Quel outil principal utilisiez-vous pour cette activité ?",
  "confidence": 0.42
}
```

Questions must be:

- short
- actionable
- tied to a concrete experience
- tied to a concrete field when possible

### `reused_rejected`

Records rejected or removed items that were considered as weak evidence during enrichment.

This list exists for transparency. It does not mean the rejected signal became accepted.

### `confidence_scores`

Records computed confidence decisions for traceability.

Each entry should contain enough information to explain:

- which experience was analyzed
- which target field was considered
- which score was computed
- which action threshold was selected

### `priority_signals`

Records the most product-relevant enriched signals.

This is not a scoring-core feature. It is a deterministic prioritization layer for downstream product surfaces such as:

- cockpit summaries
- explainability
- CV emphasis

Format:

```json
{
  "experience_index": 0,
  "skill": "Data Analysis",
  "reason": "strong structured signal with explicit tools and context",
  "confidence": 0.84
}
```

Rules:

- only include high-confidence or high-value structured signals
- keep the list short and readable
- this list does not change matching
- this list exists to highlight what matters most in the enriched profile

### `canonical_candidates`

Records unresolved non-injected candidates for future canonical review.

The enrichment agent must not modify the canonical store automatically.

### `learning_candidates`

Records repeated unresolved or weakly structured patterns that should later help improve canonical coverage.

Format:

```json
{
  "raw": "prospection",
  "suggested_canonical": "Business Development",
  "frequency": 4,
  "reason": "repeated unresolved token near structured commercial experience signals"
}
```

Rules:

- do not write these into the canonical store automatically
- do not inject them into `career_profile`
- keep them as diagnostic and improvement output only

This is the learning loop for the product, not an online mutation of the canonical layer.

## Logging

Add backend logging in `cache_hooks.py`:

```python
ENRICHMENT_STATS = enrichment["enrichment_report"]["stats"]
```

Log:

- `suggestions_count`
- `auto_filled_count`
- `questions_count`

Logging must remain informational only and must not alter pipeline output.

## Integration

Modify:

- `apps/api/src/compass/pipeline/cache_hooks.py`

After `ProfileStructuringAgent`, add:

```python
enrichment = ProfileEnrichmentAgent().run(
    {
        "career_profile": career_profile_dict,
        "structuring_report": structuring_report,
        "canonical_skills": canonical_skills,
        "unresolved": unresolved,
        "rejected_noise": removed,
    }
)

career_profile_dict = enrichment["career_profile_enriched"]
profile["enrichment_report"] = enrichment["enrichment_report"]
```

Then rebuild `profile["experiences"]` from the enriched final `career_profile`.

`ProfileStructuringAgent` remains the conservative structuring layer.
`ProfileEnrichmentAgent` remains a fully additive post-processor.

## Non-goals

This work must not:

- modify matching core
- modify `skills_uri`
- modify `matching_v1`
- create a new profile format
- overwrite or rewrite validated frontend state
- invent new skills outside canonical inputs or strong explicit text evidence
- silently replace existing `skill_links`

## Testing Strategy

Create:

- `apps/api/tests/test_profile_enrichment_agent.py`

Required coverage:

1. no hallucinated skills
2. confidence thresholds are respected
3. uncertain cases become suggestions instead of auto-fill
4. unresolved signals are reused only as weak signals
5. deterministic output on repeated input
6. existing `skill_links` are not rewritten
7. auto-fill on existing `skill_links` is limited to empty `tools`, `context`, or `autonomy_level`
8. pipeline integration persists `enrichment_report`
9. existing `apply_pack` and `html_renderer` flows still work

Integration verification must include:

- `test_profile_enrichment_agent.py`
- `test_profile_structuring_agent.py`
- `test_career_profile_v2_integration.py`
- `test_apply_pack_cv_engine.py`
- `test_html_renderer.py`

## Success Criteria

The work is successful when:

- the agent runs automatically in `run_profile_cache_hooks()`
- `career_profile` is enriched additively before frontend usage
- `enrichment_report` is persisted for frontend and diagnostics
- missing tools or context can become safe suggestions
- ambiguous gaps become better user questions
- canonical gaps become visible without polluting the profile
- matching and scoring remain unchanged
- existing `skill_links` keep trust because they are never destructively rewritten
