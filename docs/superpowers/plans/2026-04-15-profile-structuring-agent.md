# Profile Structuring Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic backend structuring agent that enriches `career_profile`, persists `structuring_report`, and runs automatically in the parse pipeline before frontend and document consumers read the profile.

**Architecture:** Keep the current backend pipeline intact and insert a new orchestrator after `from_profile_structured_v1(...)` in `cache_hooks.py`. The new `ProfileStructuringAgent` reuses the existing `CareerProfile` schema and `skill_link_builder`, enriches experiences in place, classifies signals, generates user questions, emits canonical candidates, and stores a deterministic `structuring_report` on the profile payload.

**Tech Stack:** Python, Pydantic models in `documents/career_profile.py`, existing Compass pipeline modules, pytest.

---

## File Map

- Create: `apps/api/src/compass/structuring/profile_structuring_agent.py`
  - Deterministic orchestrator for experience cleanup, `skill_links`, diagnostics, questions, and canonical candidates.
- Modify: `apps/api/src/compass/structuring/__init__.py`
  - Export the new agent alongside `build_skill_links_for_experience`.
- Modify: `apps/api/src/compass/pipeline/cache_hooks.py`
  - Run the agent after `from_profile_structured_v1(...)`, persist `career_profile` + `structuring_report`, rebuild `profile["experiences"]`, log stats.
- Modify: `apps/api/src/documents/career_profile.py`
  - Add helper conversion/loading support if needed for round-tripping enriched `CareerProfile` dicts back into model instances without changing the schema.
- Create: `apps/api/tests/test_profile_structuring_agent.py`
  - Focused tests for deterministic agent behavior and reporting.
- Modify: `apps/api/tests/test_career_profile_v2_integration.py`
  - Assert pipeline persistence of `structuring_report` and enriched `skill_links`.
- Verify only: `apps/api/tests/test_apply_pack_cv_engine.py`
  - Ensure Apply Pack still consumes enriched `career_profile`.
- Verify only: `apps/api/tests/test_html_renderer.py`
  - Ensure renderer still consumes enriched `career_profile`.

## Task 1: Add failing tests for the new structuring agent

**Files:**
- Create: `apps/api/tests/test_profile_structuring_agent.py`
- Test: `apps/api/tests/test_profile_structuring_agent.py`

- [ ] **Step 1: Write the failing test module**

```python
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.structuring.profile_structuring_agent import ProfileStructuringAgent


def _profile_input() -> dict:
    return {
        "career_profile": {
            "schema_version": "v2",
            "experiences": [
                {
                    "title": "Data Analyst",
                    "company": "ACME",
                    "responsibilities": [
                        "Analyse de performance avec Python et SQL",
                        "Analyse de performance avec Python et SQL",
                        "Production de tableaux de bord Power BI pour le reporting",
                    ],
                    "tools": ["Python", "SQL", "Power BI", "Power BI"],
                    "skills": ["Analyse de données", "Reporting"],
                    "autonomy_level": "autonomous",
                    "canonical_skills_used": [
                        {"label": "Analyse de données", "uri": "skill:data_analysis"},
                        {"label": "Reporting", "uri": "skill:reporting"},
                    ],
                    "skill_links": [],
                }
            ],
        },
        "raw_profile": {"skills": ["Python", "SQL", "Power BI"]},
        "canonical_skills": [
            {"label": "Analyse de données", "uri": "skill:data_analysis", "raw": "analyse"},
            {"label": "Reporting", "uri": "skill:reporting", "raw": "reporting"},
        ],
        "unresolved": [{"raw": "powerbi dashboards"}],
        "removed": [{"value": "communication", "reason": "generic_without_context"}],
    }


def test_agent_builds_skill_links_without_hallucinating():
    result = ProfileStructuringAgent().run(_profile_input())

    enriched = result["career_profile_enriched"]
    links = enriched["experiences"][0]["skill_links"]

    assert links
    assert {link["skill"]["label"] for link in links} <= {"Analyse de données", "Reporting"}
    assert any(tool["label"] == "Python" for link in links for tool in link["tools"])


def test_agent_is_deterministic():
    payload = _profile_input()
    first = ProfileStructuringAgent().run(copy.deepcopy(payload))
    second = ProfileStructuringAgent().run(copy.deepcopy(payload))

    assert first == second


def test_agent_maps_ambiguity_to_questions_and_uncertain_links():
    payload = _profile_input()
    payload["career_profile"]["experiences"][0]["tools"] = ["Excel"]
    payload["career_profile"]["experiences"][0]["responsibilities"] = [
        "Analyse des indicateurs de performance",
        "Structuration du reporting mensuel",
    ]

    result = ProfileStructuringAgent().run(payload)
    report = result["structuring_report"]

    assert report["questions_for_user"]
    assert any(question["type"] in {"tool", "skill", "context"} for question in report["questions_for_user"])
    assert report["uncertain_links"]


def test_agent_extracts_canonical_candidates_from_unresolved_inputs():
    result = ProfileStructuringAgent().run(_profile_input())
    report = result["structuring_report"]

    assert report["canonical_candidates"]
    assert any(candidate["raw_value"] == "powerbi dashboards" for candidate in report["canonical_candidates"])


def test_agent_keeps_removed_noise_in_report():
    result = ProfileStructuringAgent().run(_profile_input())
    report = result["structuring_report"]

    assert report["rejected_noise"] == [{"value": "communication", "reason": "generic_without_context"}]
```

- [ ] **Step 2: Run the new test file to verify it fails**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
./.venv/bin/pytest apps/api/tests/test_profile_structuring_agent.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `compass.structuring.profile_structuring_agent` or missing `ProfileStructuringAgent`.

- [ ] **Step 3: Commit the failing test**

```bash
git add apps/api/tests/test_profile_structuring_agent.py
git commit -m "test: add profile structuring agent coverage"
```

## Task 2: Implement the deterministic structuring agent

**Files:**
- Create: `apps/api/src/compass/structuring/profile_structuring_agent.py`
- Modify: `apps/api/src/compass/structuring/__init__.py`
- Test: `apps/api/tests/test_profile_structuring_agent.py`

- [ ] **Step 1: Create the agent module skeleton**

```python
from __future__ import annotations

from copy import deepcopy
from typing import Any


class ProfileStructuringAgent:
    def __init__(self, mode: str = "deterministic"):
        if mode != "deterministic":
            raise ValueError("Only deterministic mode is supported")
        self.mode = mode

    def run(self, profile_input: dict) -> dict:
        payload = deepcopy(profile_input or {})
        career_profile = payload.get("career_profile") or {}
        return {
            "career_profile_enriched": career_profile,
            "structuring_report": {
                "used_signals": [],
                "uncertain_links": [],
                "questions_for_user": [],
                "canonical_candidates": [],
                "rejected_noise": [],
                "unresolved_candidates": [],
                "stats": {
                    "experiences_processed": 0,
                    "skill_links_created": 0,
                    "questions_generated": 0,
                    "coverage_ratio": 0.0,
                },
            },
        }
```

- [ ] **Step 2: Export the agent**

Update `apps/api/src/compass/structuring/__init__.py`:

```python
from .profile_structuring_agent import ProfileStructuringAgent
from .skill_link_builder import build_skill_links_for_experience

__all__ = ["ProfileStructuringAgent", "build_skill_links_for_experience"]
```

- [ ] **Step 3: Add deterministic cleanup and conversion helpers**

Add these helpers inside `profile_structuring_agent.py`:

```python
import re
from copy import deepcopy

from documents.career_profile import CareerExperience, CareerProfile


def _canon(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = re.sub(r"\s+", " ", str(value or "").strip())
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result


def _coerce_career_profile(data: dict[str, Any]) -> CareerProfile:
    return CareerProfile.model_validate(data or {})


def _normalize_responsibilities(exp: CareerExperience) -> CareerExperience:
    exp.responsibilities = _dedupe_strings(exp.responsibilities)
    exp.tools = _dedupe_strings(exp.tools)
    exp.skills = _dedupe_strings(exp.skills)
    return exp
```

- [ ] **Step 4: Implement signal classification, question generation, and canonical candidates**

Add these helpers inside `profile_structuring_agent.py`:

```python
def _build_canonical_candidates(unresolved: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in unresolved or []:
        raw = str(item.get("raw") or item.get("value") or "").strip() if isinstance(item, dict) else str(item or "").strip()
        if not raw:
            continue
        normalized = _canon(raw)
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(
            {
                "raw_value": raw,
                "normalized_value": normalized,
                "type": "tool" if any(token in normalized for token in ("excel", "power bi", "powerbi", "sql", "python")) else "alias",
                "confidence": 0.6,
                "reason": "unresolved parsing signal kept for canonical review",
            }
        )
    return out


def _build_uncertain_links(exp: CareerExperience, experience_index: int) -> list[dict[str, Any]]:
    if len(exp.canonical_skills_used) <= 1:
        return []
    if exp.skill_links:
        return []
    if not exp.tools:
        return []
    return [
        {
            "experience_index": experience_index,
            "tool": tool,
            "candidate_skills": [skill.label for skill in exp.canonical_skills_used],
            "reason": "tool could not be attached with strong evidence",
        }
        for tool in exp.tools
    ]


def _build_questions(exp: CareerExperience, experience_index: int, uncertain_links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    if uncertain_links:
        questions.append(
            {
                "type": "tool",
                "experience_index": experience_index,
                "question": "Quel outil principal utilisiez-vous pour cette expérience ?",
            }
        )
    if exp.canonical_skills_used and not exp.skill_links:
        questions.append(
            {
                "type": "context",
                "experience_index": experience_index,
                "question": "Quel était le contexte principal de cette expérience ?",
            }
        )
    if exp.autonomy_level is None:
        questions.append(
            {
                "type": "autonomy",
                "experience_index": experience_index,
                "question": "Quel niveau d'autonomie aviez-vous sur cette expérience ?",
            }
        )
    return questions[:5]
```

- [ ] **Step 5: Implement the agent orchestration using the existing skill-link builder**

Replace `run(...)` in `profile_structuring_agent.py` with:

```python
from compass.structuring.skill_link_builder import build_skill_links_for_experience


class ProfileStructuringAgent:
    def __init__(self, mode: str = "deterministic"):
        if mode != "deterministic":
            raise ValueError("Only deterministic mode is supported")
        self.mode = mode

    def run(self, profile_input: dict) -> dict:
        payload = deepcopy(profile_input or {})
        career_profile = _coerce_career_profile(payload.get("career_profile") or {})
        unresolved = list(payload.get("unresolved") or [])
        removed = list(payload.get("removed") or [])

        used_signals: list[dict[str, Any]] = []
        uncertain_links: list[dict[str, Any]] = []
        questions_for_user: list[dict[str, Any]] = []

        for experience_index, exp in enumerate(career_profile.experiences):
            _normalize_responsibilities(exp)
            exp.skill_links = build_skill_links_for_experience(exp)

            for link in exp.skill_links:
                used_signals.append(
                    {
                        "experience_index": experience_index,
                        "skill": link.skill.label,
                        "tools": [tool.label for tool in link.tools],
                        "context": link.context,
                    }
                )

            exp_uncertain_links = _build_uncertain_links(exp, experience_index)
            uncertain_links.extend(exp_uncertain_links)
            questions_for_user.extend(_build_questions(exp, experience_index, exp_uncertain_links))

        experiences_processed = len(career_profile.experiences)
        skill_links_created = sum(len(exp.skill_links) for exp in career_profile.experiences)
        experiences_with_links = sum(1 for exp in career_profile.experiences if exp.skill_links)
        canonical_candidates = _build_canonical_candidates(unresolved)
        unresolved_candidates = [
            {"raw_value": item.get("raw") or item.get("value") or str(item)}
            for item in unresolved
        ]

        structuring_report = {
            "used_signals": used_signals,
            "uncertain_links": uncertain_links,
            "questions_for_user": questions_for_user,
            "canonical_candidates": canonical_candidates,
            "rejected_noise": removed,
            "unresolved_candidates": unresolved_candidates,
            "stats": {
                "experiences_processed": experiences_processed,
                "skill_links_created": skill_links_created,
                "questions_generated": len(questions_for_user),
                "coverage_ratio": round((experiences_with_links / experiences_processed), 4) if experiences_processed else 0.0,
            },
        }

        return {
            "career_profile_enriched": career_profile.model_dump(),
            "structuring_report": structuring_report,
        }
```

- [ ] **Step 6: Run the focused tests**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
./.venv/bin/pytest apps/api/tests/test_profile_structuring_agent.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit the agent**

```bash
git add apps/api/src/compass/structuring/__init__.py apps/api/src/compass/structuring/profile_structuring_agent.py apps/api/tests/test_profile_structuring_agent.py
git commit -m "feat: add deterministic profile structuring agent"
```

## Task 3: Integrate the agent into the parse pipeline

**Files:**
- Modify: `apps/api/src/compass/pipeline/cache_hooks.py`
- Modify: `apps/api/tests/test_career_profile_v2_integration.py`

- [ ] **Step 1: Add the pipeline integration test first**

Append to `apps/api/tests/test_career_profile_v2_integration.py`:

```python
def test_run_profile_cache_hooks_persists_structuring_report():
    profile = {
        "skills": ["Python", "SQL", "Power BI"],
        "languages": ["Français"],
        "canonical_skills": [
            {"label": "Analyse de données", "uri": "skill:data_analysis"},
            {"label": "Reporting", "uri": "skill:reporting"},
        ],
        "unresolved": [{"raw": "powerbi dashboards"}],
        "generic_filter_removed": [{"value": "communication", "reason": "generic_without_context"}],
    }

    run_profile_cache_hooks(cv_text=CV_TEXT, profile=profile)

    assert "structuring_report" in profile
    assert "stats" in profile["structuring_report"]
    assert "career_profile" in profile
    assert "experiences" in profile
```

- [ ] **Step 2: Run the integration test to verify it fails**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
./.venv/bin/pytest apps/api/tests/test_career_profile_v2_integration.py::test_run_profile_cache_hooks_persists_structuring_report -q
```

Expected: FAIL because `structuring_report` is not persisted yet.

- [ ] **Step 3: Wire the agent into `cache_hooks.py`**

Update imports:

```python
from compass.structuring import ProfileStructuringAgent
```

Update the career-profile block in `run_profile_cache_hooks(...)`:

```python
        career_profile = from_profile_structured_v1(
            structured,
            raw_skills=profile.get("skills") or [],
            raw_languages=raw_languages,
        )

        career_profile_dict = career_profile.model_dump()
        raw_profile = dict(profile)
        canonical_skills = list(profile.get("canonical_skills") or [])
        unresolved = list(profile.get("unresolved") or [])
        removed = list(profile.get("generic_filter_removed") or profile.get("removed") or [])

        agent = ProfileStructuringAgent()
        agent_result = agent.run(
            {
                "career_profile": career_profile_dict,
                "raw_profile": raw_profile,
                "canonical_skills": canonical_skills,
                "unresolved": unresolved,
                "removed": removed,
            }
        )
        career_profile_dict = agent_result["career_profile_enriched"]
        profile["structuring_report"] = agent_result["structuring_report"]

        profile["career_profile"] = career_profile_dict
        enriched_career_profile = career_profile.__class__.model_validate(career_profile_dict)
        if enriched_career_profile.experiences:
            profile["experiences"] = to_experience_dicts(enriched_career_profile)
```

- [ ] **Step 4: Update the structuring stats log to use the persisted report**

Replace the existing stats logging block in `cache_hooks.py` with:

```python
        stats = profile["structuring_report"].get("stats", {})
        linked_tools = sum(
            len(link.get("tools") or [])
            for exp in career_profile_dict.get("experiences", [])
            for link in exp.get("skill_links", [])
        )
        raw_tools = sum(len(exp.get("tools") or []) for exp in career_profile_dict.get("experiences", []))

        logger.info(
            "STRUCTURING_STATS exps=%d skill_links=%d questions=%d coverage_ratio=%.4f tools_attached=%d tools_unattached=%d",
            int(stats.get("experiences_processed", 0) or 0),
            int(stats.get("skill_links_created", 0) or 0),
            int(stats.get("questions_generated", 0) or 0),
            float(stats.get("coverage_ratio", 0.0) or 0.0),
            linked_tools,
            max(0, raw_tools - linked_tools),
        )
```

- [ ] **Step 5: Run the targeted integration tests**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
./.venv/bin/pytest \
  apps/api/tests/test_profile_structuring_agent.py \
  apps/api/tests/test_career_profile_v2_integration.py::test_run_profile_cache_hooks_persists_structuring_report \
  apps/api/tests/test_career_profile_v2_integration.py::test_run_profile_cache_hooks_populates_career_profile_skill_links \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit the pipeline integration**

```bash
git add apps/api/src/compass/pipeline/cache_hooks.py apps/api/tests/test_career_profile_v2_integration.py
git commit -m "feat: persist structuring report in profile cache hooks"
```

## Task 4: Add round-trip helper support for enriched career profiles

**Files:**
- Modify: `apps/api/src/documents/career_profile.py`
- Test: `apps/api/tests/test_career_profile_v2_integration.py`

- [ ] **Step 1: Add a helper for loading an enriched `CareerProfile` dict**

Near `from_profile_structured_v1(...)`, add:

```python
def load_career_profile(data: Dict[str, Any]) -> CareerProfile:
    """Round-trip helper for persisted career_profile dicts."""
    return CareerProfile.model_validate(data or {})
```

- [ ] **Step 2: Use the helper in `cache_hooks.py`**

Replace:

```python
        enriched_career_profile = career_profile.__class__.model_validate(career_profile_dict)
```

with:

```python
        enriched_career_profile = load_career_profile(career_profile_dict)
```

and add the import:

```python
from documents.career_profile import from_profile_structured_v1, load_career_profile, to_experience_dicts
```

- [ ] **Step 3: Add a round-trip regression test**

Append to `apps/api/tests/test_career_profile_v2_integration.py`:

```python
def test_load_career_profile_round_trips_skill_links():
    result = structure_profile_text_v1(CV_TEXT, debug=False)
    cp = from_profile_structured_v1(result, raw_skills=["Python", "SQL", "Power BI"], raw_languages=[])
    data = cp.model_dump()

    from documents.career_profile import load_career_profile

    loaded = load_career_profile(data)
    assert loaded.model_dump() == data
```

- [ ] **Step 4: Run the focused round-trip test**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
./.venv/bin/pytest apps/api/tests/test_career_profile_v2_integration.py::test_load_career_profile_round_trips_skill_links -q
```

Expected: PASS.

- [ ] **Step 5: Commit the helper**

```bash
git add apps/api/src/documents/career_profile.py apps/api/src/compass/pipeline/cache_hooks.py apps/api/tests/test_career_profile_v2_integration.py
git commit -m "refactor: add career profile round-trip helper"
```

## Task 5: Run downstream regressions and final verification

**Files:**
- Verify only: `apps/api/tests/test_apply_pack_cv_engine.py`
- Verify only: `apps/api/tests/test_html_renderer.py`

- [ ] **Step 1: Run the regression batch**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
./.venv/bin/pytest \
  apps/api/tests/test_profile_structuring_agent.py \
  apps/api/tests/test_career_profile_v2_integration.py \
  apps/api/tests/test_apply_pack_cv_engine.py \
  apps/api/tests/test_html_renderer.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Verify the full payload contract manually**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
./.venv/bin/pytest apps/api/tests/test_career_profile_v2_integration.py::test_run_profile_cache_hooks_persists_structuring_report -vv
```

Expected assertions confirmed:

- `profile["career_profile"]` exists
- `profile["structuring_report"]` exists
- `profile["experiences"]` exists
- final experiences contain `skill_links`

- [ ] **Step 3: Update the code graph**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
graphify update .
```

Expected: graph updated successfully.

- [ ] **Step 4: Commit the verified implementation**

```bash
git add apps/api/src/compass/structuring/profile_structuring_agent.py \
        apps/api/src/compass/structuring/__init__.py \
        apps/api/src/compass/pipeline/cache_hooks.py \
        apps/api/src/documents/career_profile.py \
        apps/api/tests/test_profile_structuring_agent.py \
        apps/api/tests/test_career_profile_v2_integration.py \
        docs/superpowers/specs/2026-04-15-profile-structuring-agent-design.md \
        docs/superpowers/plans/2026-04-15-profile-structuring-agent.md
git commit -m "feat: add backend profile structuring agent"
```

## Self-Review

- Spec coverage:
  - new persistent agent module: covered in Task 2
  - pipeline integration and persistence: covered in Task 3
  - diagnostics and stats: covered in Tasks 2 and 3
  - deterministic behavior and no hallucination: covered in Task 1 tests
  - downstream compatibility: covered in Task 5
- Placeholder scan:
  - no `TODO`, `TBD`, or “implement later” placeholders remain
- Type consistency:
  - `ProfileStructuringAgent.run(...)` consistently returns `career_profile_enriched` and `structuring_report`
  - `structuring_report["stats"]` consistently contains `experiences_processed`, `skill_links_created`, `questions_generated`, `coverage_ratio`

