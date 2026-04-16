# Document Understanding Phase 2 Block 1 Design

## Goal

Add instrumentation-only comparison around `document_understanding` so the team can measure, on a real CV corpus, whether `CVUnderstandingAgent` improves documentary structure relative to the legacy path.

This block must not change product behavior.

## Scope

This phase covers **Bloc 1 only**:

- instrument understanding-vs-legacy comparison metrics
- persist those metrics in `profile["document_understanding"]["parsing_diagnostics"]["comparison_metrics"]`
- add structured logging for each run
- add a small batch report over the CV corpus in `/Users/akimguentas/Downloads/cvtest`

This phase does **not** cover:

- identity injection
- experience reconciliation
- project injection into `career_profile`
- `ProfileStructuringAgent` behavioral changes
- frontend changes
- matching or scoring changes

## Why This Must Be Isolated

If this phase mutates profile behavior, measurement becomes biased.

The purpose here is to answer:

- where is `document_understanding` better than legacy?
- where is it equivalent?
- where is it worse?

That means the system must **observe first, inject later**.

## Hard Guardrail

For Block 1:

- no mutation of final `career_profile` from `document_understanding`
- no identity backfill
- no experience header replacement
- no project separation injected into product behavior
- no changes to downstream matching inputs

If the profile output changes in a way the user can feel, Block 1 has failed its purpose.

## Existing Seam

The necessary seams already exist:

- `apps/api/src/compass/understanding/cv_understanding_agent.py`
- `apps/api/src/compass/pipeline/profile_parse_pipeline.py`
- `apps/api/src/compass/pipeline/cache_hooks.py`

Current flow already gives us:

- `document_understanding`
- legacy `career_profile`
- legacy `experiences`
- `structuring_report`
- `enrichment_report`

That is enough to compare without injecting.

## Metrics To Add

For each parse run, the system must compute and persist at least:

- `identity_detected_legacy`
- `identity_detected_understanding`
- `experience_count_legacy`
- `experience_count_understanding`
- `project_count_understanding`
- `suspicious_merges_count`
- `orphan_lines_count`

These values must live in:

```python
profile["document_understanding"]["parsing_diagnostics"]["comparison_metrics"]
```

If `document_understanding` exists but some metrics cannot be computed, they should default deterministically rather than being omitted.

## Metric Semantics

### `identity_detected_legacy`

Boolean indicating whether the legacy profile path produced any meaningful identity signal in the final profile representation.

V1 acceptable inputs for `True`:

- `career_profile.identity.full_name`
- `career_profile.identity.email`
- `career_profile.identity.phone`
- `career_profile.identity.linkedin`
- `career_profile.identity.location`

### `identity_detected_understanding`

Boolean indicating whether `document_understanding.identity` contains any meaningful identity/contact signal.

### `experience_count_legacy`

Count of legacy experiences persisted in the current backend output.

Primary source:

- `profile["career_profile"]["experiences"]`

Fallback:

- `profile["experiences"]`

### `experience_count_understanding`

Count of:

- `profile["document_understanding"]["experience_blocks"]`

### `project_count_understanding`

Count of:

- `profile["document_understanding"]["project_blocks"]`

### `suspicious_merges_count`

Count of:

- `profile["document_understanding"]["parsing_diagnostics"]["suspicious_merges"]`

### `orphan_lines_count`

Count of:

- `profile["document_understanding"]["parsing_diagnostics"]["orphan_lines"]`

## Comparison Logic

The instrumentation layer should also compute an internal comparison label for evaluation tooling.

Allowed values:

- `better`
- `equal`
- `worse`
- `mixed`

This label does not need to be persisted in the profile if that pollutes the contract, but it must appear in the batch report.

Suggested interpretation:

- `better`:
  - understanding finds identity where legacy does not, or
  - understanding separates more experiences/projects without suspicious merge inflation
- `equal`:
  - counts and identity outcome are effectively the same
- `worse`:
  - understanding loses identity or drastically under-segments compared to legacy
- `mixed`:
  - some signals improve, others degrade

This comparison must remain deterministic and rules-based.

## Logging

For each run, emit a structured log event, for example:

```json
{
  "event": "DOCUMENT_UNDERSTANDING_COMPARISON",
  "identity_detected_legacy": true,
  "identity_detected_understanding": true,
  "experience_count_legacy": 2,
  "experience_count_understanding": 3,
  "project_count_understanding": 1,
  "suspicious_merges_count": 0,
  "orphan_lines_count": 2
}
```

This log is observational only.

It must not affect any downstream decisions.

## Batch Evaluation

Add a dedicated evaluation script that scans:

- `/Users/akimguentas/Downloads/cvtest`

The script must:

1. iterate over a bounded set of CV files
2. run the real backend parse pipeline
3. extract the comparison metrics
4. compute the per-CV comparison label
5. emit:
   - detailed per-file results
   - aggregate summary counts

Recommended output formats:

- JSON artifact in `apps/api/data/eval/`
- optional CSV companion
- readable console summary

## Required Aggregate Outputs

The batch report must summarize at least:

- total CV count
- count where understanding is `better`
- count where understanding is `equal`
- count where understanding is `mixed`
- count where understanding is `worse`
- how often identity improves
- how often understanding detects more experiences
- how often suspicious merges are non-zero

## File Plan

Expected touched files:

- Modify: `apps/api/src/compass/understanding/cv_understanding_agent.py`
- Modify: `apps/api/src/compass/pipeline/cache_hooks.py`
- Add: `apps/api/scripts/evaluate_document_understanding_phase2_block1.py`
- Add tests in:
  - `apps/api/tests/test_cv_understanding_agent.py`
  - `apps/api/tests/test_career_profile_v2_integration.py`
  - or a dedicated instrumentation test file if cleaner

## Integration Strategy

### In the understanding layer

Keep understanding-native metrics inside:

- `document_understanding.parsing_diagnostics`

### In cache hooks

Once the legacy `career_profile` exists, enrich:

- `comparison_metrics`

with the legacy-facing signals:

- `identity_detected_legacy`
- `experience_count_legacy`

This is the right place because the legacy output is actually available there.

### In the batch evaluator

Use the final parse payload as the sole source of truth for evaluation.

Do not call internal helpers in a way that bypasses the real pipeline contract.

## Success Criteria

Block 1 is successful if:

- every parse run persists the required comparison metrics
- the metrics are deterministic and stable
- a batch report can be generated over the corpus
- the team can identify where understanding is better, equal, mixed, or worse
- there is still zero mutation of the final profile behavior

## Explicit Non-Goals

- no identity injection
- no experience reconciliation
- no project-to-profile injection
- no changes to `ProfileStructuringAgent` behavior
- no frontend wiring
- no matching/scoring changes

## Decision Gate After Block 1

Only after Block 1 results exist should the team decide whether to proceed to:

- Block 2: safe identity injection
- Block 3: safe experience header reconciliation

Until then, `document_understanding` remains a measured observational layer, not a behavioral one.
