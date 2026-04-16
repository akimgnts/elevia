# CV Understanding Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic backend `CVUnderstandingAgent` that runs after text extraction, persists `profile["document_understanding"]`, and improves documentary segmentation observability without changing the final `career_profile` source of truth in V1.

**Architecture:** Introduce a new `compass.understanding` module that parses raw CV text into a structured intermediate document model. Wire it into `profile_parse_pipeline.py` immediately after text extraction, persist the result in the existing profile payload, and keep `structure_profile_text_v1()` plus the current structuring/enrichment flow unchanged for business output generation.

**Tech Stack:** Python, existing Compass pipeline modules, deterministic regex/string heuristics, pytest

---

## File Map

- Create: `apps/api/src/compass/understanding/__init__.py`
- Create: `apps/api/src/compass/understanding/cv_understanding_agent.py`
- Modify: `apps/api/src/compass/pipeline/profile_parse_pipeline.py`
- Modify: `apps/api/src/compass/pipeline/cache_hooks.py`
- Test: `apps/api/tests/test_cv_understanding_agent.py`
- Test: `apps/api/tests/test_profile_parse_pipeline.py`
- Test: `apps/api/tests/test_career_profile_v2_integration.py`

## Task 1: Add the understanding module surface

**Files:**
- Create: `apps/api/src/compass/understanding/__init__.py`
- Create: `apps/api/src/compass/understanding/cv_understanding_agent.py`
- Test: `apps/api/tests/test_cv_understanding_agent.py`

- [ ] **Step 1: Write the failing module smoke tests**

```python
from compass.understanding import CVUnderstandingAgent


def test_agent_returns_document_understanding_root():
    result = CVUnderstandingAgent().run(
        {
            "cv_text": "Jean Dupont\nData Analyst\njean@example.com",
            "source_name": "cv.txt",
            "raw_profile": {},
        }
    )

    assert "document_understanding" in result
    doc = result["document_understanding"]
    assert "identity" in doc
    assert "experience_blocks" in doc
    assert "parsing_diagnostics" in doc


def test_agent_is_deterministic():
    payload = {
        "cv_text": "Jean Dupont\nData Analyst\njean@example.com",
        "source_name": "cv.txt",
        "raw_profile": {},
    }

    first = CVUnderstandingAgent().run(payload)
    second = CVUnderstandingAgent().run(payload)

    assert first == second
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_cv_understanding_agent.py -q
```

Expected:

- fail with import error because `compass.understanding` and `CVUnderstandingAgent` do not exist yet

- [ ] **Step 3: Create the module skeleton**

`apps/api/src/compass/understanding/__init__.py`

```python
from .cv_understanding_agent import CVUnderstandingAgent

__all__ = ["CVUnderstandingAgent"]
```

`apps/api/src/compass/understanding/cv_understanding_agent.py`

```python
from __future__ import annotations

from typing import Any


class CVUnderstandingAgent:
    def __init__(self, mode: str = "deterministic"):
        if mode != "deterministic":
            raise ValueError("CVUnderstandingAgent supports deterministic mode only in v1")
        self.mode = mode

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        cv_text = str(payload.get("cv_text") or "").strip()
        if not cv_text:
            return {
                "document_understanding": {
                    "identity": {
                        "full_name": "",
                        "headline": "",
                        "email": "",
                        "phone": "",
                        "linkedin": "",
                        "location": "",
                    },
                    "summary": {"text": "", "confidence": 0.0},
                    "skills_block": {"raw_lines": [], "confidence": 0.0},
                    "experience_blocks": [],
                    "education_blocks": [],
                    "project_blocks": [],
                    "other_blocks": [],
                    "confidence": {
                        "identity_confidence": 0.0,
                        "sectioning_confidence": 0.0,
                        "experience_segmentation_confidence": 0.0,
                    },
                    "parsing_diagnostics": {
                        "sections_detected": [],
                        "suspicious_merges": [],
                        "orphan_lines": [],
                        "warnings": [],
                        "comparison_metrics": {},
                    },
                }
            }
```

- [ ] **Step 4: Run the tests to verify the skeleton passes**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_cv_understanding_agent.py -q
```

Expected:

- tests pass with a minimal empty-structure implementation

## Task 2: Implement identity, section, and block detection

**Files:**
- Modify: `apps/api/src/compass/understanding/cv_understanding_agent.py`
- Test: `apps/api/tests/test_cv_understanding_agent.py`

- [ ] **Step 1: Add failing tests for sectioning and identity**

Append to `apps/api/tests/test_cv_understanding_agent.py`:

```python
def test_extracts_basic_identity():
    text = \"\"\"Jean Dupont
Data Analyst
jean.dupont@example.com
+33 6 12 34 56 78
linkedin.com/in/jeandupont
Paris
\"\"\"
    doc = CVUnderstandingAgent().run({"cv_text": text, "source_name": "cv.txt", "raw_profile": {}})["document_understanding"]

    assert doc["identity"]["full_name"] == "Jean Dupont"
    assert doc["identity"]["email"] == "jean.dupont@example.com"
    assert "linkedin.com/in/jeandupont" in doc["identity"]["linkedin"]
    assert doc["identity"]["location"] == "Paris"


def test_separates_summary_from_experience_section():
    text = \"\"\"Jane Doe
PROFILE
Full-stack engineer with 4 years of experience building web applications.

WORK EXPERIENCE
Full Stack Developer - Acme
2022 - Present
Built internal tools in React and Node.js.
\"\"\"
    doc = CVUnderstandingAgent().run({"cv_text": text, "source_name": "cv.txt", "raw_profile": {}})["document_understanding"]

    assert "4 years of experience" in doc["summary"]["text"]
    assert len(doc["experience_blocks"]) == 1
    assert doc["experience_blocks"][0]["company"] == "Acme"
    assert "4 years of experience" not in " ".join(doc["experience_blocks"][0]["description_lines"])


def test_separates_education_from_experience():
    text = \"\"\"WORK EXPERIENCE
Data Analyst - Acme
2022 - Present
Built dashboards.

EDUCATION
Master in Data Science - Université Paris-Dauphine
2020 - 2022
\"\"\"
    doc = CVUnderstandingAgent().run({"cv_text": text, "source_name": "cv.txt", "raw_profile": {}})["document_understanding"]

    assert len(doc["experience_blocks"]) == 1
    assert len(doc["education_blocks"]) == 1
    assert doc["education_blocks"][0]["institution"] == "Université Paris-Dauphine"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_cv_understanding_agent.py -q
```

Expected:

- failures because the skeleton agent does not extract sections or identity

- [ ] **Step 3: Implement deterministic section and identity parsing**

Add focused helpers inside `cv_understanding_agent.py`:

```python
SECTION_ALIASES = {
    "summary": {"summary", "profile", "about"},
    "skills": {"key skills", "technical skills", "skills", "core skills"},
    "experience": {"experience", "work experience", "professional experience", "expériences professionnelles", "experience professionnelle"},
    "education": {"education", "formation"},
    "projects": {"projects", "projets"},
}


def _normalize_line(line: str) -> str:
    return " ".join(line.strip().split())


def _split_lines(cv_text: str) -> list[str]:
    return [_normalize_line(line) for line in cv_text.replace("\r", "").split("\n") if _normalize_line(line)]


def _detect_identity(lines: list[str]) -> dict[str, str]:
    identity = {
        "full_name": "",
        "headline": "",
        "email": "",
        "phone": "",
        "linkedin": "",
        "location": "",
    }
    header_lines = lines[:8]
    for line in header_lines:
        lower = line.lower()
        if "@" in line and not identity["email"]:
            identity["email"] = line
        elif "linkedin.com/" in lower and not identity["linkedin"]:
            identity["linkedin"] = line
        elif any(ch.isdigit() for ch in line) and "+" in line and not identity["phone"]:
            identity["phone"] = line
    text_only = [line for line in header_lines if "@" not in line and "linkedin.com/" not in line.lower()]
    if text_only:
        if len(text_only[0].split()) <= 5:
            identity["full_name"] = text_only[0]
        if len(text_only) > 1 and len(text_only[1].split()) <= 10:
            identity["headline"] = text_only[1]
        if len(text_only) > 2 and len(text_only[-1].split()) <= 5 and not any(ch.isdigit() for ch in text_only[-1]):
            identity["location"] = text_only[-1]
    return identity


def _detect_sections(lines: list[str]) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    current_name = "header"
    current_lines: list[str] = []
    for line in lines:
        lower = line.lower().strip(" :-")
        matched = None
        for name, aliases in SECTION_ALIASES.items():
            if lower in aliases:
                matched = name
                break
        if matched:
            sections.append((current_name, current_lines))
            current_name = matched
            current_lines = []
            continue
        current_lines.append(line)
    sections.append((current_name, current_lines))
    return [(name, content) for name, content in sections if content]
```

Then wire these helpers into `run()` to populate:

- `identity`
- `summary`
- `skills_block`
- raw section diagnostics

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_cv_understanding_agent.py -q
```

Expected:

- identity and section tests pass

## Task 3: Implement experience, education, and project segmentation

**Files:**
- Modify: `apps/api/src/compass/understanding/cv_understanding_agent.py`
- Test: `apps/api/tests/test_cv_understanding_agent.py`

- [ ] **Step 1: Add failing segmentation tests**

Append:

```python
def test_detects_multiple_experiences():
    text = \"\"\"WORK EXPERIENCE
Data Analyst - Acme
2022 - Present
Built dashboards.

Backend Developer - Beta
2020 - 2022
Built APIs.
\"\"\"
    doc = CVUnderstandingAgent().run({"cv_text": text, "source_name": "cv.txt", "raw_profile": {}})["document_understanding"]

    assert len(doc["experience_blocks"]) == 2
    assert doc["experience_blocks"][0]["company"] == "Acme"
    assert doc["experience_blocks"][1]["company"] == "Beta"


def test_detects_project_block_separately():
    text = \"\"\"PROJECTS
Dynamic Website Development - Le Havre Est À Vous
2023
Built a showcase website.
\"\"\"
    doc = CVUnderstandingAgent().run({"cv_text": text, "source_name": "cv.txt", "raw_profile": {}})["document_understanding"]

    assert len(doc["project_blocks"]) == 1
    assert doc["project_blocks"][0]["title"] == "Dynamic Website Development"


def test_prevents_summary_sentence_becoming_company():
    text = \"\"\"PROFILE
Engineer focused on product quality and collaboration.

WORK EXPERIENCE
Full Stack Developer - Access It Lille
2022 - Present
Built a customer portal.
\"\"\"
    doc = CVUnderstandingAgent().run({"cv_text": text, "source_name": "cv.txt", "raw_profile": {}})["document_understanding"]

    assert len(doc["experience_blocks"]) == 1
    assert doc["experience_blocks"][0]["company"] == "Access It Lille"
    assert doc["experience_blocks"][0]["company"] != "Engineer focused on product quality and collaboration."
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_cv_understanding_agent.py -q
```

Expected:

- failures because block segmentation is not implemented yet

- [ ] **Step 3: Implement block segmentation with conservative header parsing**

Add helpers in `cv_understanding_agent.py`:

```python
import re

DATE_RE = re.compile(r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|janv|fév|mars|avr|mai|juin|juil|août|sept|oct|nov|déc)?\\s*\\d{4}|present|présent", re.IGNORECASE)


def _looks_like_date_line(line: str) -> bool:
    return bool(DATE_RE.search(line))


def _parse_header_title_org(header: str) -> tuple[str, str]:
    if " - " in header:
        left, right = header.split(" - ", 1)
        return left.strip(), right.strip()
    if " | " in header:
        parts = [part.strip() for part in header.split(" | ") if part.strip()]
        if len(parts) >= 2:
            return parts[0], parts[1]
    return header.strip(), ""


def _segment_blocks(section_lines: list[str], *, kind: str) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in section_lines:
        if not current:
            current = {"header_raw": line, "description_lines": []}
            continue
        if _looks_like_date_line(line) and not current.get("start_date"):
            current["_date_line"] = line
            continue
        if line and current.get("description_lines") and _looks_like_date_line(current["description_lines"][-1] if current["description_lines"] else ""):
            pass
        if current["description_lines"] and not line.startswith(("•", "-", "*")) and len(line.split()) <= 8 and _parse_header_title_org(line)[1]:
            blocks.append(current)
            current = {"header_raw": line, "description_lines": []}
            continue
        current["description_lines"].append(line)
    if current:
        blocks.append(current)
    return blocks
```

Then post-process by kind:

- experience:
  - `title`, `company` from header
  - `start_date` / `end_date` from date line when possible
- education:
  - `title`, `institution`
- projects:
  - `title`, `organization`

Keep `header_raw` and assign conservative confidence values.

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_cv_understanding_agent.py -q
```

Expected:

- segmentation tests pass

## Task 4: Add diagnostics and comparison metrics

**Files:**
- Modify: `apps/api/src/compass/understanding/cv_understanding_agent.py`
- Test: `apps/api/tests/test_cv_understanding_agent.py`

- [ ] **Step 1: Add failing diagnostic tests**

Append:

```python
def test_produces_diagnostics_for_ambiguous_document():
    text = \"\"\"Jane Doe
PROFILE
Engineer focused on delivery.
Master in Computer Science - University X
2020 - 2022
\"\"\"
    doc = CVUnderstandingAgent().run({"cv_text": text, "source_name": "cv.txt", "raw_profile": {}})["document_understanding"]
    diagnostics = doc["parsing_diagnostics"]

    assert "warnings" in diagnostics
    assert diagnostics["comparison_metrics"]["suspicious_merges_count"] >= 0
    assert isinstance(diagnostics["orphan_lines"], list)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_cv_understanding_agent.py -q
```

Expected:

- failure because diagnostics/comparison metrics are incomplete

- [ ] **Step 3: Implement diagnostics and metrics**

Extend `run()` to compute:

```python
comparison_metrics = {
    "identity_detected": bool(identity.get("full_name") or identity.get("email")),
    "experience_blocks_count": len(experience_blocks),
    "education_blocks_count": len(education_blocks),
    "project_blocks_count": len(project_blocks),
    "suspicious_merges_count": len(suspicious_merges),
    "legacy_experiences_count": len((payload.get("raw_profile") or {}).get("experiences") or []),
    "legacy_education_count": len((payload.get("raw_profile") or {}).get("education") or []),
}
comparison_metrics["experience_count_delta_vs_legacy"] = (
    comparison_metrics["experience_blocks_count"] - comparison_metrics["legacy_experiences_count"]
)
comparison_metrics["education_count_delta_vs_legacy"] = (
    comparison_metrics["education_blocks_count"] - comparison_metrics["legacy_education_count"]
)
```

Add warnings conservatively, for example:

- summary-like line detected inside an experience block
- education-like line found in experience section
- project-like header outside project section

- [ ] **Step 4: Run the tests to verify they pass**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_cv_understanding_agent.py -q
```

Expected:

- diagnostics tests pass

## Task 5: Wire the agent into the real parse pipeline

**Files:**
- Modify: `apps/api/src/compass/pipeline/profile_parse_pipeline.py`
- Test: `apps/api/tests/test_profile_parse_pipeline.py`

- [ ] **Step 1: Add a failing pipeline test for `document_understanding` persistence**

Add a focused test to `apps/api/tests/test_profile_parse_pipeline.py`:

```python
def test_parse_file_payload_includes_document_understanding():
    from compass.pipeline.contracts import ParseFilePipelineRequest
    from compass.pipeline.profile_parse_pipeline import build_parse_file_response_payload

    payload = build_parse_file_response_payload(
        ParseFilePipelineRequest(
            request_id="cv-understanding-test",
            raw_filename="sample.txt",
            content_type="text/plain",
            file_bytes=b"Jean Dupont\\nPROFILE\\nData Analyst\\nWORK EXPERIENCE\\nData Analyst - Acme\\n2022 - Present\\nBuilt dashboards.",
            enrich_llm=0,
        )
    )

    profile = payload.get("profile") or {}
    assert "document_understanding" in profile
    assert "experience_blocks" in profile["document_understanding"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_profile_parse_pipeline.py -q
```

Expected:

- failure because the pipeline does not yet persist `document_understanding`

- [ ] **Step 3: Wire the agent after text extraction**

Modify `profile_parse_pipeline.py` to:

```python
from compass.understanding import CVUnderstandingAgent
```

and in `_run_profile_text_pipeline(...)` after:

```python
profile = get_extracted_profile_snapshot(pipeline)
```

add:

```python
document_understanding = CVUnderstandingAgent().run(
    {
        "cv_text": cv_text,
        "source_name": filename,
        "raw_profile": profile,
    }
).get("document_understanding") or {}
profile["document_understanding"] = document_understanding
```

This keeps the understanding layer inside the same profile object used downstream.

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_profile_parse_pipeline.py -q
```

Expected:

- the new pipeline test passes

## Task 6: Preserve understanding through cache hooks and integration coverage

**Files:**
- Modify: `apps/api/src/compass/pipeline/cache_hooks.py`
- Modify: `apps/api/tests/test_career_profile_v2_integration.py`

- [ ] **Step 1: Add a failing integration test**

Add to `apps/api/tests/test_career_profile_v2_integration.py`:

```python
def test_run_profile_cache_hooks_preserves_document_understanding():
    profile = {
        "skills": ["Python"],
        "document_understanding": {
            "identity": {"full_name": "Jean Dupont"},
            "summary": {"text": "Data Analyst", "confidence": 0.8},
            "skills_block": {"raw_lines": ["Python"], "confidence": 0.9},
            "experience_blocks": [],
            "education_blocks": [],
            "project_blocks": [],
            "other_blocks": [],
            "confidence": {
                "identity_confidence": 0.8,
                "sectioning_confidence": 0.7,
                "experience_segmentation_confidence": 0.6,
            },
            "parsing_diagnostics": {
                "sections_detected": ["summary"],
                "suspicious_merges": [],
                "orphan_lines": [],
                "warnings": [],
                "comparison_metrics": {},
            },
        },
    }

    run_profile_cache_hooks(cv_text=CV_TEXT, profile=profile)

    assert "document_understanding" in profile
    assert profile["document_understanding"]["identity"]["full_name"] == "Jean Dupont"
    assert "career_profile" in profile
    assert "structuring_report" in profile
    assert "enrichment_report" in profile
```

- [ ] **Step 2: Run the targeted integration test to verify current behavior**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_career_profile_v2_integration.py -q
```

Expected:

- either failure from unexpected mutation/removal, or pass if already preserved

- [ ] **Step 3: Make preservation explicit in cache hooks**

In `cache_hooks.py`, before business structuring, add a no-op-safe read:

```python
document_understanding = profile.get("document_understanding")
if isinstance(document_understanding, dict):
    profile["document_understanding"] = document_understanding
```

Do not let any later mutation path overwrite it.

Also pass the same `raw_profile` forward unchanged so downstream agents can inspect `raw_profile["document_understanding"]` later.

- [ ] **Step 4: Run the integration test to verify it passes**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_career_profile_v2_integration.py -q
```

Expected:

- integration coverage passes with `document_understanding` preserved alongside existing outputs

## Task 7: Run the validation batch

**Files:**
- No code changes

- [ ] **Step 1: Run understanding unit tests**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_cv_understanding_agent.py -q
```

Expected:

- all understanding tests pass

- [ ] **Step 2: Run parse pipeline tests**

Run:

```bash
PYTHONPATH=apps/api/src ./.venv/bin/pytest apps/api/tests/test_profile_parse_pipeline.py -q
```

Expected:

- parse pipeline tests pass

- [ ] **Step 3: Run core integration and downstream regression tests**

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

- no regression in structuring, enrichment, apply pack, or renderer

- [ ] **Step 4: Run graph refresh after code changes**

Run:

```bash
graphify update .
```

Expected:

- graphify report updates successfully

## Spec Coverage Check

Spec requirements mapped:

- real repo-level agent: Tasks 1-4
- deterministic document-understanding model: Tasks 1-4
- insertion after text extraction: Task 5
- additive persistence in `profile["document_understanding"]`: Tasks 5-6
- no replacement of `career_profile` source: Tasks 5-6
- diagnostics and comparison metrics: Task 4
- integration without matching/scoring changes: Tasks 6-7

No uncovered spec requirement remains.

## Self-Review

- No placeholders such as TODO/TBD remain.
- The plan keeps V1 additive and does not replace `structure_profile_text_v1()`.
- Types and field names are consistent with the approved spec:
  - `document_understanding`
  - `experience_blocks`
  - `education_blocks`
  - `project_blocks`
  - `comparison_metrics`

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-16-cv-understanding-agent.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Inline Execution - Execute tasks in this session using the plan as the checklist, with checkpoints after each batch

Which approach?
