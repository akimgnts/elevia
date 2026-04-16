# Document Understanding Phase 2 Block 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Instrument `document_understanding` versus the legacy profile path, persist deterministic comparison metrics, and produce a batch evaluation report over the CV corpus without changing final product behavior.

**Architecture:** Keep Block 1 strictly observational. Extend `CVUnderstandingAgent` diagnostics with understanding-native metrics, enrich those metrics in `cache_hooks.py` with legacy-facing values once `career_profile` exists, and add a dedicated evaluation script that runs the real deterministic parse pipeline over `/Users/akimguentas/Downloads/cvtest` and outputs per-CV plus aggregate comparison results.

**Tech Stack:** Python, existing Compass backend pipeline, pytest, JSON/CSV reporting

---

## File Map

- Modify: `apps/api/src/compass/understanding/cv_understanding_agent.py`
- Modify: `apps/api/src/compass/pipeline/cache_hooks.py`
- Add: `apps/api/scripts/evaluate_document_understanding_phase2_block1.py`
- Modify: `apps/api/tests/test_cv_understanding_agent.py`
- Modify: `apps/api/tests/test_career_profile_v2_integration.py`
- Add or modify: `apps/api/tests/test_profile_parse_pipeline.py`

## Guardrails

- `document_understanding` must remain strictly observational in Block 1.
- No downstream agent may consume it for behavior changes in this block.
- No mutation of `career_profile`, `profile["experiences"]`, `skills_uri`, matching, scoring, or final product behavior.
- Batch runs must be deterministic:
  - LLM off
  - same pipeline config for all files
  - no random seeds or timestamps in result payloads

## Task 1: Extend understanding-side metrics only

**Files:**
- Modify: `apps/api/src/compass/understanding/cv_understanding_agent.py`
- Modify: `apps/api/tests/test_cv_understanding_agent.py`

- [ ] **Step 1: Add failing tests for Block 1 understanding metrics**

Append tests to `apps/api/tests/test_cv_understanding_agent.py`:

```python
def test_comparison_metrics_include_block1_understanding_fields():
    text = \"\"\"Jean Dupont
PROFILE
Data analyst focused on reporting.

WORK EXPERIENCE
Data Analyst - Acme
2022 - Present
Built dashboards.

PROJECTS
Open Data Portal - City of Paris
2021
Built a public portal.
\"\"\"
    metrics = CVUnderstandingAgent().run(
        {"cv_text": text, "source_name": "cv.txt", "raw_profile": {}}
    )["document_understanding"]["parsing_diagnostics"]["comparison_metrics"]

    assert "identity_detected_understanding" in metrics
    assert "experience_count_understanding" in metrics
    assert "project_count_understanding" in metrics
    assert "suspicious_merges_count" in metrics
    assert "orphan_lines_count" in metrics
    assert "invalid_experience_headers_count" in metrics


def test_invalid_experience_headers_count_flags_polluted_headers():
    text = \"\"\"WORK EXPERIENCE
Engineer - ISEN Lille and I am actively seeking an opportunity.
2022 - Present
Built platform features.
\"\"\"
    metrics = CVUnderstandingAgent().run(
        {"cv_text": text, "source_name": "cv.txt", "raw_profile": {}}
    )["document_understanding"]["parsing_diagnostics"]["comparison_metrics"]

    assert metrics["invalid_experience_headers_count"] >= 1
```

- [ ] **Step 2: Run the test file to verify failure**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_cv_understanding_agent.py -q
```

Expected:

- failure because these new metrics do not all exist yet

- [ ] **Step 3: Add understanding-only metrics and deterministic header invalidation**

In `apps/api/src/compass/understanding/cv_understanding_agent.py`, extend the comparison metric builder so it includes:

```python
{
    "identity_detected_understanding": bool(any(identity.values())),
    "experience_count_understanding": len(experience_blocks),
    "project_count_understanding": len(project_blocks),
    "suspicious_merges_count": len(suspicious_merges),
    "orphan_lines_count": len(orphan_lines),
    "invalid_experience_headers_count": invalid_experience_headers_count,
}
```

Add a deterministic header invalidation helper, for example:

```python
def _is_invalid_experience_header(header: str) -> bool:
    normalized = _normalize_line(header).lower()
    if len(normalized) > 90:
        return True
    if normalized.endswith("."):
        return True
    if " and " in normalized and any(token in normalized for token in {"seeking", "looking", "open to"}):
        return True
    if any(token in normalized for token in {" i am ", " i'm ", " je suis ", " recherche ", " seeking "}):
        return True
    return False
```

Use it only for metrics/diagnostics, not for changing the parsed block behavior in Block 1.

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_cv_understanding_agent.py -q
```

Expected:

- updated understanding tests pass

## Task 2: Enrich comparison metrics with legacy-facing values in cache hooks

**Files:**
- Modify: `apps/api/src/compass/pipeline/cache_hooks.py`
- Modify: `apps/api/tests/test_career_profile_v2_integration.py`

- [ ] **Step 1: Add failing integration tests for legacy-vs-understanding metrics**

Append tests to `apps/api/tests/test_career_profile_v2_integration.py`:

```python
def test_run_profile_cache_hooks_populates_block1_comparison_metrics():
    profile = {
        "skills": ["Python", "SQL", "Power BI"],
        "languages": ["Français"],
        "document_understanding": {
            "identity": {"full_name": "Jean Dupont"},
            "experience_blocks": [{}, {}],
            "project_blocks": [{}],
            "parsing_diagnostics": {
                "suspicious_merges": [{}],
                "orphan_lines": ["line"],
                "comparison_metrics": {},
            },
        },
    }

    run_profile_cache_hooks(cv_text=CV_TEXT, profile=profile)

    metrics = profile["document_understanding"]["parsing_diagnostics"]["comparison_metrics"]
    assert "identity_detected_legacy" in metrics
    assert "identity_detected_understanding" in metrics
    assert "experience_count_legacy" in metrics
    assert "experience_count_understanding" in metrics
    assert "project_count_understanding" in metrics
    assert "suspicious_merges_count" in metrics
    assert "orphan_lines_count" in metrics
```

- [ ] **Step 2: Run targeted test to verify failure**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_career_profile_v2_integration.py -q -k block1_comparison_metrics
```

Expected:

- failure because the legacy-facing metrics are not yet enriched in cache hooks

- [ ] **Step 3: Add cache-hooks metric enrichment and structured logging**

In `apps/api/src/compass/pipeline/cache_hooks.py`, after `career_profile` exists and before return, enrich:

```python
metrics = profile["document_understanding"]["parsing_diagnostics"].setdefault("comparison_metrics", {})
identity = (profile.get("career_profile") or {}).get("identity") or {}
legacy_experiences = (profile.get("career_profile") or {}).get("experiences") or profile.get("experiences") or []

metrics["identity_detected_legacy"] = bool(
    identity.get("full_name")
    or identity.get("email")
    or identity.get("phone")
    or identity.get("linkedin")
    or identity.get("location")
)
metrics.setdefault("identity_detected_understanding", bool(any((profile["document_understanding"].get("identity") or {}).values())))
metrics["experience_count_legacy"] = len(legacy_experiences)
metrics.setdefault("experience_count_understanding", len(profile["document_understanding"].get("experience_blocks") or []))
metrics.setdefault("project_count_understanding", len(profile["document_understanding"].get("project_blocks") or []))
metrics.setdefault("suspicious_merges_count", len(profile["document_understanding"]["parsing_diagnostics"].get("suspicious_merges") or []))
metrics.setdefault("orphan_lines_count", len(profile["document_understanding"]["parsing_diagnostics"].get("orphan_lines") or []))
metrics.setdefault("invalid_experience_headers_count", 0)
```

Also emit an observational log:

```python
logger.info(
    "DOCUMENT_UNDERSTANDING_COMPARISON identity_legacy=%s identity_understanding=%s exp_legacy=%d exp_understanding=%d projects_understanding=%d suspicious_merges=%d orphan_lines=%d invalid_headers=%d",
    metrics["identity_detected_legacy"],
    metrics["identity_detected_understanding"],
    metrics["experience_count_legacy"],
    metrics["experience_count_understanding"],
    metrics["project_count_understanding"],
    metrics["suspicious_merges_count"],
    metrics["orphan_lines_count"],
    metrics["invalid_experience_headers_count"],
)
```

Do not let any downstream agent consume these values for behavior.

- [ ] **Step 4: Run integration tests to verify pass**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_career_profile_v2_integration.py -q
```

Expected:

- all integration tests pass

## Task 3: Add deterministic comparison label rules

**Files:**
- Add: `apps/api/scripts/evaluate_document_understanding_phase2_block1.py`
- Modify: `apps/api/tests/test_profile_parse_pipeline.py` or add dedicated script tests if simpler

- [ ] **Step 1: Add failing unit coverage for comparison label rules**

If you keep helpers inside the script, add a small dedicated test file or extend an existing one with:

```python
def test_block1_comparison_label_rules():
    from apps.api.scripts.evaluate_document_understanding_phase2_block1 import classify_case

    assert classify_case({
        "identity_detected_legacy": False,
        "identity_detected_understanding": True,
        "experience_count_legacy": 1,
        "experience_count_understanding": 1,
        "suspicious_merges_count": 0,
    }) == "better"

    assert classify_case({
        "identity_detected_legacy": True,
        "identity_detected_understanding": False,
        "experience_count_legacy": 1,
        "experience_count_understanding": 1,
        "suspicious_merges_count": 0,
    }) == "worse"
```

- [ ] **Step 2: Run the targeted test to verify failure**

Run the relevant pytest target.

Expected:

- failure because the batch classifier helper does not exist yet

- [ ] **Step 3: Implement deterministic batch classifier and script**

Create `apps/api/scripts/evaluate_document_understanding_phase2_block1.py`.

Recommended structure:

```python
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from compass.pipeline.contracts import ParseFilePipelineRequest
from compass.pipeline.profile_parse_pipeline import build_parse_file_response_payload

CVTEST_DIR = Path("/Users/akimguentas/Downloads/cvtest")
REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_JSON = REPO_ROOT / "apps" / "api" / "data" / "eval" / "document_understanding_phase2_block1.json"
OUTPUT_CSV = REPO_ROOT / "apps" / "api" / "data" / "eval" / "document_understanding_phase2_block1.csv"


def classify_case(metrics: dict[str, Any]) -> str:
    identity_legacy = bool(metrics.get("identity_detected_legacy"))
    identity_understanding = bool(metrics.get("identity_detected_understanding"))
    exp_legacy = int(metrics.get("experience_count_legacy") or 0)
    exp_understanding = int(metrics.get("experience_count_understanding") or 0)
    suspicious = int(metrics.get("suspicious_merges_count") or 0)

    if (not identity_legacy and identity_understanding) or (
        exp_understanding > exp_legacy and suspicious == 0
    ):
        if identity_understanding < identity_legacy or (exp_understanding == 0 and exp_legacy > 0):
            return "mixed"
        return "better"
    if (identity_legacy and not identity_understanding) or (
        exp_understanding == 0 and exp_legacy > 0
    ):
        return "worse"
    if identity_legacy == identity_understanding and exp_legacy == exp_understanding:
        return "equal"
    return "mixed"
```

The script must:

- scan a bounded set of files in `/Users/akimguentas/Downloads/cvtest`
- run `build_parse_file_response_payload(...)`
- keep `enrich_llm=0`
- extract `comparison_metrics`
- compute a per-file label
- write JSON and CSV artifacts
- print an aggregate summary

- [ ] **Step 4: Run the script on the local corpus**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/python apps/api/scripts/evaluate_document_understanding_phase2_block1.py
```

Expected:

- script completes successfully
- JSON and CSV artifacts are written
- per-file labels plus aggregate summary are printed

## Task 4: Add batch report aggregate assertions

**Files:**
- Add or modify tests around the new batch script helper logic

- [ ] **Step 1: Add tests for aggregate reporting behavior**

Add tests that verify the aggregate summary counts:

```python
def test_aggregate_counts_labels_correctly():
    from apps.api.scripts.evaluate_document_understanding_phase2_block1 import aggregate_cases

    summary = aggregate_cases([
        {"comparison": "better", "metrics": {"identity_detected_legacy": False, "identity_detected_understanding": True, "experience_count_understanding": 2, "experience_count_legacy": 1, "suspicious_merges_count": 0}},
        {"comparison": "equal", "metrics": {"identity_detected_legacy": True, "identity_detected_understanding": True, "experience_count_understanding": 1, "experience_count_legacy": 1, "suspicious_merges_count": 0}},
        {"comparison": "worse", "metrics": {"identity_detected_legacy": True, "identity_detected_understanding": False, "experience_count_understanding": 0, "experience_count_legacy": 2, "suspicious_merges_count": 1}},
    ])

    assert summary["total"] == 3
    assert summary["better"] == 1
    assert summary["equal"] == 1
    assert summary["worse"] == 1
```

- [ ] **Step 2: Run tests and fix any issues**

Run the relevant pytest target.

Expected:

- aggregate helper tests pass

## Task 5: Validation batch

**Files:**
- No further code changes expected

- [ ] **Step 1: Run understanding tests**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_cv_understanding_agent.py -q
```

Expected:

- pass

- [ ] **Step 2: Run parse pipeline tests**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_profile_parse_pipeline.py -q
```

Expected:

- pass

- [ ] **Step 3: Run integration and downstream regression tests**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest \
  apps/api/tests/test_career_profile_v2_integration.py \
  apps/api/tests/test_profile_structuring_agent.py \
  apps/api/tests/test_profile_enrichment_agent.py \
  apps/api/tests/test_apply_pack_cv_engine.py \
  apps/api/tests/test_html_renderer.py -q
```

Expected:

- pass

- [ ] **Step 4: Run batch script**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/python apps/api/scripts/evaluate_document_understanding_phase2_block1.py
```

Expected:

- report artifacts created
- aggregate summary printed

- [ ] **Step 5: Refresh graph**

Run:

```bash
graphify update .
```

Expected:

- graph updated successfully

## Spec Coverage Check

Covered requirements:

- instrumentation only, no behavior mutation: Tasks 1-2
- persisted metrics in `comparison_metrics`: Tasks 1-2
- structured per-run logs: Task 2
- deterministic comparison label rules: Task 3
- deterministic batch run over `/Users/akimguentas/Downloads/cvtest`: Task 3
- aggregate report over the corpus: Tasks 3-4
- no downstream consumption of `document_understanding`: maintained as a guardrail, with no plan task that changes agent behavior

No spec requirement is intentionally omitted.

## Self-Review

- No TODO/TBD placeholders remain.
- The plan remains Bloc 1 only.
- No task injects identity or reconciles experiences.
- Comparison labels are explicit and deterministic, not subjective.
- `invalid_experience_headers_count` is included.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-16-document-understanding-phase-2-block-1.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Inline Execution - Execute tasks in this session using the plan as the checklist, with checkpoints after each batch

Which approach?
