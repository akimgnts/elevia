# CV Understanding Agent Design

## Goal

Add a persistent backend `CVUnderstandingAgent` that runs automatically after raw text extraction and produces a deterministic, reusable document-understanding layer for CVs before any profile structuring or enrichment logic runs.

This layer must improve how the pipeline understands document structure without changing matching, scoring, canonical mapping ownership, or the final `career_profile` contract.

## Why This Exists

The current pipeline often understands the global domain of a CV correctly, but still fails on document structure:

- summary text can leak into experience parsing
- an education block can be mistaken for a job
- project blocks can be merged into experience blocks
- identity/contact lines can remain unbound
- malformed PDF line breaks can create fake companies or fake titles

The missing layer is a document-understanding step that answers a simpler question before any business structuring:

`What is this document made of, and which lines belong to which block?`

That step must exist before `ProfileStructuringAgent` and `ProfileEnrichmentAgent`, but it must remain additive and diagnostic in V1.

## Chosen Strategy

V1 is intentionally **additive**.

`CVUnderstandingAgent` will:

- run in the real backend pipeline
- persist `profile["document_understanding"]`
- remain deterministic-only
- feed future convergence of the structuring pipeline

`CVUnderstandingAgent` will **not**:

- replace `structure_profile_text_v1()`
- become the source of truth for `career_profile` in V1
- bypass canonical mapping
- inject directly into `skills_uri`
- perform business structuring or enrichment

This keeps the pipeline stable while making the document layer visible, testable, and comparable.

## Existing Seam

The correct insertion point is in:

- `apps/api/src/compass/pipeline/profile_parse_pipeline.py`

Specifically, the agent should run **immediately after**:

1. `ingest_profile_file(...)`
2. `extract_profile_text(...)`

and **before**:

1. canonical pipeline / signal stages
2. `run_profile_cache_hooks(...)`
3. `ProfileStructuringAgent`
4. `ProfileEnrichmentAgent`

Target flow:

1. PDF / file ingestion
2. text extraction
3. `CVUnderstandingAgent`
4. canonical / parsing pipeline
5. `run_profile_cache_hooks(...)`
6. `ProfileStructuringAgent`
7. `ProfileEnrichmentAgent`
8. final persistence

## Fundamental Guardrails

### 1. `document_understanding` must be diagnostic and exploitable

It must be a structured intermediate artifact, not a raw blob of lines or a debugging dump.

It must be shaped enough to:

- inspect document segmentation quality
- compare legacy vs understanding-based structure
- feed future structuring convergence
- surface diagnostics to product and internal evaluation

### 2. In V1, `document_understanding` must never become the final business source of truth

In this iteration:

- `career_profile` still comes from the existing path
- `structure_profile_text_v1()` remains in place
- `ProfileStructuringAgent` remains the business structuring layer

`document_understanding` is persisted and available, but not authoritative for final profile semantics yet.

### 3. Comparison metrics must exist from day one

The agent output must support comparison with the legacy structure.

At minimum, metrics and diagnostics must expose:

- identity detected or not
- number of experience blocks detected
- number of project blocks detected
- number of education blocks detected
- number of suspicious merges
- difference versus legacy structure counts where available

This is required so the team can decide later whether the new layer is mature enough to replace parts of the legacy path.

## New Module

Create:

- `apps/api/src/compass/understanding/cv_understanding_agent.py`
- `apps/api/src/compass/understanding/__init__.py`

Helpers may stay in the same file for V1 unless a boundary becomes clearly reusable.

## Public Interface

```python
class CVUnderstandingAgent:
    def __init__(self, mode: str = "deterministic"):
        ...

    def run(self, payload: dict) -> dict:
        """
        Input:
        {
            "cv_text": str,
            "source_name": Optional[str],
            "raw_profile": Optional[dict],
        }

        Output:
        {
            "document_understanding": {
                "identity": {...},
                "summary": {...},
                "skills_block": {...},
                "experience_blocks": [...],
                "education_blocks": [...],
                "project_blocks": [...],
                "other_blocks": [...],
                "confidence": {...},
                "parsing_diagnostics": {...},
            }
        }
        """
```

Supported mode for V1:

- `deterministic`

If another mode is passed, the class should fail fast or degrade explicitly to deterministic behavior without hidden fallback.

## Input Contract

The agent receives:

```python
{
    "cv_text": str,
    "source_name": Optional[str],
    "raw_profile": Optional[dict],
}
```

Meanings:

- `cv_text`: extracted raw CV text, mandatory
- `source_name`: filename or logical source, optional but useful for diagnostics
- `raw_profile`: current profile snapshot from the canonical pipeline when available, optional and read-only

`raw_profile` can be used as weak context only. It must not override direct documentary evidence from the text.

## Output Contract

The agent returns:

```json
{
  "document_understanding": {
    "identity": {
      "full_name": "",
      "headline": "",
      "email": "",
      "phone": "",
      "linkedin": "",
      "location": ""
    },
    "summary": {
      "text": "",
      "confidence": 0.0
    },
    "skills_block": {
      "raw_lines": [],
      "confidence": 0.0
    },
    "experience_blocks": [
      {
        "title": "",
        "company": "",
        "location": "",
        "start_date": "",
        "end_date": "",
        "description_lines": [],
        "header_raw": "",
        "confidence": 0.0
      }
    ],
    "education_blocks": [
      {
        "title": "",
        "institution": "",
        "start_date": "",
        "end_date": "",
        "description_lines": [],
        "header_raw": "",
        "confidence": 0.0
      }
    ],
    "project_blocks": [
      {
        "title": "",
        "organization": "",
        "start_date": "",
        "end_date": "",
        "description_lines": [],
        "header_raw": "",
        "confidence": 0.0
      }
    ],
    "other_blocks": [],
    "confidence": {
      "identity_confidence": 0.0,
      "sectioning_confidence": 0.0,
      "experience_segmentation_confidence": 0.0
    },
    "parsing_diagnostics": {
      "sections_detected": [],
      "suspicious_merges": [],
      "orphan_lines": [],
      "warnings": [],
      "comparison_metrics": {}
    }
  }
}
```

Notes:

- empty strings are acceptable when information is absent
- no synthetic identity values are allowed
- confidence scores must be deterministic numeric outputs
- no timestamps or runtime-varying artifacts may appear in the returned structure

## Responsibilities

### 1. Section Detection

The agent must separate the document into coherent section-level blocks using deterministic cues:

- explicit headings
- line capitalization patterns
- heading variants in FR / EN
- spacing and separators
- date density
- lexical markers

Supported heading families include, at minimum:

- `WORK EXPERIENCE`
- `EXPERIENCE`
- `PROFESSIONAL EXPERIENCE`
- `EDUCATION`
- `FORMATION`
- `SUMMARY`
- `PROFILE`
- `ABOUT`
- `KEY SKILLS`
- `TECHNICAL SKILLS`
- `PROJECTS`

The output must record detected sections in diagnostics.

### 2. Identity and Contact Understanding

The top of the CV should be parsed conservatively for:

- full name
- headline
- email
- phone
- linkedin
- location

Rules:

- never invent an identity field
- never attach a contact line to an experience block if it appears in the header region
- if identity is partial, return partial values with lower confidence rather than forcing completion

### 3. Summary Detection

The agent should recognize summary/profile/about blocks distinctly from experience content.

Rules:

- summary text belongs to `summary.text`
- summary text must not be reused as experience description by default
- if a summary-like paragraph appears attached to an experience header, mark ambiguity in diagnostics instead of forcing assignment silently

### 4. Skills Block Detection

The agent should detect a global skills / key skills section and preserve its raw lines separately.

Rules:

- this is a documentary block only
- it does not perform canonical mapping
- it does not infer per-experience ownership
- it preserves raw skill lines for downstream consumers

### 5. Experience Segmentation

This is the most important responsibility.

For each experience block, the agent should attempt to extract:

- `title`
- `company`
- `location`
- `start_date`
- `end_date`
- `description_lines`
- `header_raw`
- `confidence`

Expected header forms include:

- `TITLE - COMPANY DATE - DATE`
- `TITLE | COMPANY | LOCATION`
- `COMPANY Sep 2021 - Sep 2022`
- mixed FR / EN date patterns

Rules:

- a description line belongs to one block only
- do not turn a summary sentence into a company name
- do not merge multiple jobs unless evidence is strong
- if the header is ambiguous, preserve `header_raw` and lower confidence
- if lines are orphaned after a block, record them in diagnostics

### 6. Education Segmentation

Education blocks must be recognized separately from work experience.

Expected fields:

- `title`
- `institution`
- `start_date`
- `end_date`
- `description_lines`
- `header_raw`
- `confidence`

Rules:

- school names should not become employers
- degree lines should not become job titles
- if a block looks like education inside a non-education section, flag it

### 7. Project Segmentation

Projects must be separated from professional experience where possible.

Expected fields:

- `title`
- `organization`
- `start_date`
- `end_date`
- `description_lines`
- `header_raw`
- `confidence`

Rules:

- project headers may appear inside dedicated `PROJECTS` sections or mixed elsewhere
- if a likely project appears outside a project section, keep it but add a diagnostic warning

### 8. Other Blocks

Content that does not fit the main expected categories should be stored in `other_blocks`.

This prevents forced misclassification and preserves useful material for later iterations.

## Confidence Model

V1 confidence must stay simple and deterministic.

Required top-level confidence outputs:

- `identity_confidence`
- `sectioning_confidence`
- `experience_segmentation_confidence`

Block-level confidence:

- each experience block
- each education block
- each project block

Signals may include:

- heading presence
- date coherence
- header parse quality
- description ownership consistency
- conflict with nearby section markers

If ambiguity is high, the agent should:

- lower confidence
- emit diagnostics
- avoid forcing strong structure

## Parsing Diagnostics

The agent must output diagnostics that are actionable.

Required fields:

- `sections_detected`
- `suspicious_merges`
- `orphan_lines`
- `warnings`
- `comparison_metrics`

Examples of useful warnings:

- `summary_block_merged_into_experience`
- `education_maybe_misclassified_as_experience`
- `contact_line_not_attached_to_identity`
- `project_block_detected_outside_project_section`

Examples of `comparison_metrics`:

```json
{
  "identity_detected": true,
  "experience_blocks_count": 3,
  "education_blocks_count": 1,
  "project_blocks_count": 2,
  "suspicious_merges_count": 1,
  "legacy_experiences_count": 2,
  "legacy_education_count": 1,
  "experience_count_delta_vs_legacy": 1,
  "education_count_delta_vs_legacy": 0
}
```

These metrics are required for later migration decisions.

## Integration Design

### Primary insertion point

Insert `CVUnderstandingAgent` in:

- `apps/api/src/compass/pipeline/profile_parse_pipeline.py`

immediately after:

- `extract_profile_text(...)`

The understanding output should be attached to the profile payload used by downstream steps.

### Persistence

Persist:

- `profile["document_understanding"] = result["document_understanding"]`

This should survive all later pipeline stages and appear in the final parse payload.

### Downstream availability

`run_profile_cache_hooks(...)` and `ProfileStructuringAgent` should receive the same `profile` object, which now includes `document_understanding`.

In V1:

- they may read it
- they must not depend on it as the sole business source
- legacy path remains active

This allows comparison without breaking the current system.

## What This Must Not Change

This feature must not:

- modify scoring core
- modify `matching_v1`
- write into `skills_uri`
- replace canonical mapping
- replace `ProfileStructuringAgent`
- replace `ProfileEnrichmentAgent`
- invent missing profile facts
- create a second final profile format

The final business profile remains:

- `profile["career_profile"]`

The new agent only adds:

- `profile["document_understanding"]`

## Test Strategy

Create:

- `apps/api/tests/test_cv_understanding_agent.py`

Required unit tests:

1. identity extraction basic case
2. separation of summary from experience
3. separation of education from experience
4. detection of multiple experiences
5. detection of a distinct project block
6. prevention of summary sentence becoming company
7. deterministic output on repeated runs
8. diagnostics produced for ambiguous documents

Add a minimal integration test in pipeline coverage to verify:

- `document_understanding` is attached during real parse pipeline execution
- existing `career_profile`, `structuring_report`, and `enrichment_report` still exist

## Success Criteria

The work is successful if:

- the repo contains a real `CVUnderstandingAgent`
- it runs automatically in the backend pipeline
- it persists a clear intermediate `document_understanding`
- it improves document segmentation observability
- it does not break existing structuring or enrichment
- it reduces cases where:
  - summary becomes experience
  - school becomes employer
  - phrase becomes company
  - project and job blocks are merged

## Explicit Non-Goals For V1

- no replacement of `structure_profile_text_v1()`
- no automatic migration to understanding-first `career_profile` generation
- no LLM mode
- no direct UI work
- no matching changes

## Rollout Posture

V1 is a **measured additive rollout**, not a replacement.

The intent is:

1. persist a better documentary understanding layer
2. compare it against the legacy path
3. accumulate confidence and diagnostics
4. decide later whether parts of the structuring path should migrate to it

This keeps the product stable while introducing the missing document comprehension layer as a real reusable backend agent.
