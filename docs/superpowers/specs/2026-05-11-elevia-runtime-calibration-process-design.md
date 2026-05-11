# Elevia Runtime Calibration Process Design

Date: 2026-05-11
Status: Draft for user review
Scope: audit/operations process only

## Objective

Define a stable process for improving Elevia from real runtime matching errors.

This process must prevent:
- premature theoretical taxonomy growth
- diffuse multi-layer patches
- untraceable heuristic accumulation
- local fixes that are not replayed on real CVs

This process does not define new scoring logic. It defines how runtime issues are observed, diagnosed, patched, replayed, and accepted or rejected.

## Core Principle

Elevia is improved through a short calibration loop:

`real false positive -> runtime audit -> identify missing or weak signal -> targeted patch -> PDF replay -> before/after judgment`

The system is built from real errors first, not from a global theory of all jobs.

## Section 1 — Stable Sentinel Benchmark

Calibration starts from a small fixed panel of real CVs. These become the stable Elevia benchmark.

Initial sentinel panel:
- `Nawel` -> HR
- `Ania` -> finance/compliance
- `Dia` -> wealth management / patrimoine
- `Akim Audit` -> audit/data
- `MouisseTheo` -> software/engineering

Rules:
- the sentinel panel is fixed at the start
- every patch must be replayed against this panel
- a category of drift does not exist before at least one confirmed real case
- new real cases are added later, only after the initial panel is stable enough to be useful

Rationale:
- keep the benchmark stable
- reduce moving variables
- preserve comparability across iterations
- keep real product behavior at the center

## Section 2 — Iteration Protocol

Each iteration targets one sentinel case and one dominant drift family at a time.

Standard loop:
1. Replay the real flow:
   `PDF -> /profile/parse-file -> DB profile_id -> /inbox`
2. Read the top 10 humanly.
3. Assign a simple verdict:
   - `bon`
   - `discutable`
   - `mauvais`
4. For each problematic result, identify one dominant cause if possible.
5. Only then decide whether a patch is justified.
6. After patch, replay the exact same case.
7. Compare before/after on:
   - top 10 quality
   - false positives removed
   - new false positives introduced
   - stability on the other sentinel profiles

Allowed dominant cause families:
- generic overlap too strong
- missing anchor on profile side
- missing anchor on offer side
- weak canonical -> runtime bridge
- domain enrichment too broad
- project or stack signal not exploited enough
- trajectory pattern not understood

Rules:
- one patch = one drift family
- no patch without replay
- if the cause is not localized enough, the valid output is `diagnostic incomplet`
- a local improvement that breaks multiple other sentinels is suspect

## Section 3 — Human Judgment First

At this stage, runtime understanding is still being built. Judgment must start with human reading, not early metrics.

Primary evaluation:
- inspect top 10
- judge `bon / discutable / mauvais`
- explain why

This human-first phase is used to:
- identify real drift patterns
- distinguish generic overlap from missing anchors
- surface missing project or trajectory signals
- build future categories from evidence

Metrics come later, only after the judgments become stable enough to encode.

This means:
- no early optimization around precision-like numbers
- no weighted analytics before the semantics are understood
- no pretending that unstable behavior is already measurable with confidence

## Section 4 — Operational Memory

The process must generate durable operational memory, not just ad hoc conversations.

Required artifacts:

### 1. Sentinel panel file
Contains:
- sentinel profile names
- expected métier orientation
- replay references

### 2. Case sheet per sentinel
Contains:
- current verdict
- main false positives
- suspected dominant cause
- short history of what helped or failed

### 3. Iteration log
Contains:
- triggering case
- targeted drift family
- hypothesis
- patch applied
- before/after result
- regressions observed

### 4. Drift category register
Contains only categories that emerged from repeated real cases.

Examples:
- `finance -> policy/privacy`
- `RH -> process/manager`
- `software -> HR/project`
- `audit/data -> analyst generic drift`

Important rule:
- a category helps read history
- a category does not justify a patch by itself

The process does not try to document all métiers. It documents the real runtime drifts that were actually encountered.

## Section 5 — Patch Admission Rules

A runtime patch is allowed only if:
- a real sentinel case shows a readable drift
- the drift can be stated as one dominant family
- the suspected cause is localizable to a clear layer
- the patch is small, explainable, and replayable

Examples of localizable layers:
- parsing
- canonicalization
- canonical -> runtime bridge
- offer_skills -> runtime bridge
- generic overlap control
- domain enrichment
- project evidence
- trajectory interpretation

## Section 6 — Stop Rules

Do not patch when:
- multiple causes are mixed and still unresolved
- the case itself is too ambiguous to be a stable reference
- the patch would be much broader than the evidence
- the expected gain relies mostly on intuition
- the patch improves one case while clearly threatening several other sentinels

Valid non-patch outputs:
- `diagnostic incomplet`
- `case to replay`
- `signal insuffisant`
- `catégorie immature`

This is intentional. A forced patch under uncertainty is worse than an explicit incomplete diagnosis.

## Section 7 — Acceptance Standard

A signal or rule enters the runtime calibration memory only if it has shown:
- correction of a real observed drift
- no unacceptable regression on the sentinel panel
- causal readability after replay

Signals are not accepted because they sound intelligent.
They are accepted because they proved corrective value on real runtime behavior.

Elevia must optimize for:
- relevance
- causal readability

Not for:
- opaque score improvements
- unexplainable heuristics
- apparent gains that cannot be replayed or defended

## Section 8 — Recommended Near-Term Usage

Near-term usage should follow this order:
1. stabilize the sentinel benchmark
2. run repeated audits on the same profiles
3. record verdicts and main drifts
4. patch only one drift family at a time
5. replay before/after
6. extract drift categories only after repeated confirmation
7. introduce metrics later, after human judgments become stable

## Out of Scope

This design does not define:
- changes to `matching_v1.py`
- changes to `idf.py`
- changes to `weights_*`
- new scoring formulas
- embeddings
- vector search
- LLM reranking
- a global métier taxonomy

## Decision Summary

Elevia should be governed as a progressive runtime calibration system.

It must behave like:
- a stable benchmark
- a replayable audit loop
- an operational memory of real drifts
- a disciplined patch process

It must not drift into:
- a large theoretical taxonomy
- a pile of opportunistic heuristics
- a score-centric system detached from runtime reality
