# Skill Link Structuring Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backend-authoritative structuring step that converts fragmented experience signals into deterministic `skill_links` on `career_profile.experiences[*]` after parsing and canonical mapping, before downstream consumers like Apply Pack or the Profile UI read the profile.

**Architecture:** The structuring step is a new backend module in `apps/api/src/compass/structuring/skill_link_builder.py`. It operates only on existing signals already present in `CareerExperience` and the canonical mapping output, then is wired into `apps/api/src/compass/pipeline/cache_hooks.py` immediately after `from_profile_structured_v1()` and before `to_experience_dicts()`. Existing fields remain persisted for compatibility; `skill_links` becomes the canonical structured representation for downstream consumers.

**Tech Stack:** Python 3.14, FastAPI backend pipeline, Pydantic models in `documents/career_profile.py`, pytest integration tests in `apps/api/tests`

---

### Task 1: Add Deterministic Skill Link Builder Module

**Files:**
- Create: `apps/api/src/compass/structuring/skill_link_builder.py`
- Create: `apps/api/src/compass/structuring/__init__.py`
- Test: `apps/api/tests/test_skill_link_builder.py`

- [ ] **Step 1: Write the failing tests for the builder**

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from compass.structuring.skill_link_builder import build_skill_links_for_experience
from documents.career_profile import CareerExperience, CareerSkillSelection


def test_build_skill_links_attaches_tools_to_matching_canonical_skill():
    exp = CareerExperience(
        title="Data Analyst",
        company="ACME",
        responsibilities=[
            "Analyse de performance avec Python et SQL",
            "Production de tableaux de bord Power BI pour le reporting",
        ],
        tools=["Python", "SQL", "Power BI"],
        canonical_skills_used=[
            CareerSkillSelection(label="Analyse de données"),
            CareerSkillSelection(label="Reporting"),
        ],
        autonomy_level="autonomous",
    )

    links = build_skill_links_for_experience(exp)

    assert len(links) == 2
    assert links[0].skill.label in {"Analyse de données", "Reporting"}
    assert any(tool.label == "Python" for tool in links[0].tools) or any(tool.label == "Python" for tool in links[1].tools)
    assert all(link.autonomy_level == "autonomous" for link in links)


def test_build_skill_links_skips_when_no_canonical_skills_exist():
    exp = CareerExperience(
        title="Assistant",
        company="ACME",
        responsibilities=["Support sur Excel et Outlook"],
        tools=["Excel", "Outlook"],
        canonical_skills_used=[],
    )

    links = build_skill_links_for_experience(exp)

    assert links == []


def test_build_skill_links_uses_closest_canonical_skill_for_unmatched_tool():
    exp = CareerExperience(
        title="Business Analyst",
        company="ACME",
        responsibilities=[
            "Analyse des écarts avec Excel",
            "Structuration du reporting hebdomadaire",
        ],
        tools=["Excel"],
        canonical_skills_used=[CareerSkillSelection(label="Analyse de données")],
        autonomy_level="partial",
    )

    links = build_skill_links_for_experience(exp)

    assert len(links) == 1
    assert links[0].skill.label == "Analyse de données"
    assert [tool.label for tool in links[0].tools] == ["Excel"]
    assert links[0].context
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
./.venv/bin/pytest apps/api/tests/test_skill_link_builder.py -q
```

Expected: FAIL with `ModuleNotFoundError` or missing `build_skill_links_for_experience`.

- [ ] **Step 3: Implement the minimal builder module**

```python
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from documents.career_profile import CareerExperience, SkillLink, ToolRef


def _canon(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _split_sentences(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        if not value:
            continue
        parts = re.split(r"[.;\n]+", value)
        out.extend(part.strip() for part in parts if part.strip())
    return out


def _sentence_score(sentence: str, skill_label: str, tool_label: str) -> tuple[int, int]:
    s = _canon(sentence)
    return (
        1 if _canon(skill_label) in s else 0,
        1 if _canon(tool_label) in s else 0,
    )


def build_skill_links_for_experience(exp: CareerExperience) -> list[SkillLink]:
    if not exp.canonical_skills_used:
        return []

    sentences = _split_sentences(exp.responsibilities)
    links: list[SkillLink] = []
    tools_left = [tool for tool in exp.tools if str(tool).strip()]

    for skill in exp.canonical_skills_used:
        skill_label = skill.label.strip()
        if not skill_label:
            continue

        matched_tools: list[ToolRef] = []
        best_context = ""
        best_context_score = (-1, -1)

        for sentence in sentences:
            score = (1 if _canon(skill_label) in _canon(sentence) else 0, 0)
            if score > best_context_score:
                best_context = sentence
                best_context_score = score

        for tool in list(tools_left):
            best_sentence = ""
            best_score = (-1, -1)
            for sentence in sentences:
                score = _sentence_score(sentence, skill_label, tool)
                if score > best_score:
                    best_score = score
                    best_sentence = sentence
            if best_score[1] == 1 or (len(exp.canonical_skills_used) == 1 and best_score[0] >= 0):
                matched_tools.append(ToolRef(label=tool))
                tools_left.remove(tool)
                if best_sentence and best_score >= best_context_score:
                    best_context = best_sentence
                    best_context_score = best_score

        if matched_tools or best_context:
            links.append(
                SkillLink(
                    skill=skill,
                    tools=matched_tools,
                    context=best_context or None,
                    autonomy_level=exp.autonomy_level,
                )
            )

    if tools_left and links:
        for tool in tools_left:
            links[0].tools.append(ToolRef(label=tool))

    return links
```

- [ ] **Step 4: Export the builder from the package**

```python
# apps/api/src/compass/structuring/__init__.py
from .skill_link_builder import build_skill_links_for_experience

__all__ = ["build_skill_links_for_experience"]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
./.venv/bin/pytest apps/api/tests/test_skill_link_builder.py -q
```

Expected: PASS with `3 passed`.

- [ ] **Step 6: Commit**

```bash
cd /Users/akimguentas/Dev/elevia-compass
git add apps/api/src/compass/structuring/__init__.py apps/api/src/compass/structuring/skill_link_builder.py apps/api/tests/test_skill_link_builder.py
git commit -m "feat: add deterministic skill link builder"
```

### Task 2: Wire Skill Link Structuring Into Career Profile Assembly

**Files:**
- Modify: `apps/api/src/documents/career_profile.py`
- Modify: `apps/api/src/compass/pipeline/cache_hooks.py`
- Test: `apps/api/tests/test_career_profile_v2_integration.py`

- [ ] **Step 1: Write the failing integration tests**

```python
def test_from_profile_structured_v1_builds_skill_links_from_existing_signals():
    result = structure_profile_text_v1(CV_TEXT, debug=False)
    cp = from_profile_structured_v1(result, raw_skills=["Python", "SQL", "Power BI"], raw_languages=[])

    assert cp.experiences
    assert any(exp.skill_links for exp in cp.experiences)
    first = next(exp for exp in cp.experiences if exp.skill_links)
    assert all(link.skill.label for link in first.skill_links)
    assert any(link.tools for link in first.skill_links)


def test_to_experience_dicts_persists_skill_links():
    result = structure_profile_text_v1(CV_TEXT, debug=False)
    cp = from_profile_structured_v1(result, raw_skills=["Python", "SQL", "Power BI"], raw_languages=[])
    dicts = to_experience_dicts(cp)

    assert dicts
    assert "skill_links" in dicts[0]
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
./.venv/bin/pytest apps/api/tests/test_career_profile_v2_integration.py -q
```

Expected: FAIL because `skill_links` are still empty in `from_profile_structured_v1()`.

- [ ] **Step 3: Populate `skill_links` inside `from_profile_structured_v1()`**

```python
from compass.structuring import build_skill_links_for_experience

# inside _extract(), after CareerExperience(...) creation:
        experience = CareerExperience(
            title=title or "Expérience",
            company=company,
            location=str(getattr(exp, "location", None) or "").strip() or None,
            start_date=str(getattr(exp, "start_date", None) or "").strip() or None,
            end_date=str(getattr(exp, "end_date", None) or "").strip() or None,
            duration_months=getattr(exp, "duration_months", None),
            responsibilities=responsibilities[:8],
            achievements=achievements[:5],
            tools=tools[:12],
            skills=skills[:8],
            autonomy=autonomy,
            autonomy_level={
                "HIGH": "ownership",
                "MED": "autonomous",
                "LOW": "execution",
            }.get(autonomy_raw, "autonomous"),
            canonical_skills_used=[],
        )
        experience.skill_links = build_skill_links_for_experience(experience)
        experiences.append(experience)
```

Then, once `canonical_skills_used` is assigned from existing extracted skill labels, rebuild links one more time:

```python
for exp in experiences:
    exp.skill_links = build_skill_links_for_experience(exp)
```

- [ ] **Step 4: Add pipeline-level stats logging in `cache_hooks.py`**

```python
        total_links = sum(len(exp.skill_links) for exp in career_profile.experiences)
        linked_exps = sum(1 for exp in career_profile.experiences if exp.skill_links)
        linked_tools = sum(len(link.tools) for exp in career_profile.experiences for link in exp.skill_links)
        raw_tools = sum(len(exp.tools) for exp in career_profile.experiences)

        logger.info(
            "STRUCTURING_STATS exps=%d linked_exps=%d skill_links=%d tools_attached=%d tools_unattached=%d",
            len(career_profile.experiences),
            linked_exps,
            total_links,
            linked_tools,
            max(0, raw_tools - linked_tools),
        )
```

- [ ] **Step 5: Run the integration tests again**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
./.venv/bin/pytest apps/api/tests/test_career_profile_v2_integration.py -q
```

Expected: PASS, with `skill_links` present and serialized.

- [ ] **Step 6: Commit**

```bash
cd /Users/akimguentas/Dev/elevia-compass
git add apps/api/src/documents/career_profile.py apps/api/src/compass/pipeline/cache_hooks.py apps/api/tests/test_career_profile_v2_integration.py
git commit -m "feat: build skill links during career profile assembly"
```

### Task 3: Verify Parse Pipeline Injection Stays Backend-Authoritative

**Files:**
- Modify: `apps/api/tests/test_career_profile_v2_integration.py`
- Modify: `apps/api/tests/test_apply_pack_cv_engine.py`
- Modify: `apps/api/tests/test_html_renderer.py`

- [ ] **Step 1: Add a regression test that the downstream CV engine receives persisted `skill_links`**

```python
def test_build_targeted_cv_uses_skill_links_from_backend_profile():
    profile = {
        "career_profile": {
            "experiences": [
                {
                    "title": "Data Analyst",
                    "company": "ACME",
                    "skill_links": [
                        {
                            "skill": {"label": "Analyse de données"},
                            "tools": [{"label": "Python"}, {"label": "SQL"}],
                            "context": "analyse de performance",
                            "autonomy_level": "autonomous",
                        }
                    ],
                    "tools": ["Python", "SQL"],
                }
            ]
        }
    }

    payload = build_targeted_cv(profile, OFFER)
    assert payload["adapted_experiences"]
    assert any("Analyse de données" in bullet for bullet in payload["adapted_experiences"][0]["bullets"])
```

- [ ] **Step 2: Add a renderer regression test for backend-produced `skill_links`**

```python
def test_render_cv_html_v2_reads_backend_skill_links_without_profile_page_help():
    payload = _sample_payload()
    profile = {
        "career_profile": {
            "experiences": [
                {
                    "title": "Data Analyst",
                    "company": "ACME",
                    "skill_links": [
                        {
                            "skill": {"label": "Analyse de données"},
                            "tools": [{"label": "Python"}],
                            "context": "reporting de performance",
                            "autonomy_level": "autonomous",
                        }
                    ],
                }
            ]
        }
    }

    html = render_cv_html(payload, template_version="cv_v2", profile=profile, offer={"title": "Data Analyst"})
    assert "Analyse de données" in html
    assert "Python" in html
```

- [ ] **Step 3: Run the regression tests**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
./.venv/bin/pytest apps/api/tests/test_apply_pack_cv_engine.py apps/api/tests/test_html_renderer.py -q
```

Expected: PASS with no matching-core assertions changed.

- [ ] **Step 4: Commit**

```bash
cd /Users/akimguentas/Dev/elevia-compass
git add apps/api/tests/test_apply_pack_cv_engine.py apps/api/tests/test_html_renderer.py
git commit -m "test: verify downstream consumers read backend skill links"
```

### Task 4: Validate End-to-End Parse Hook Behavior

**Files:**
- Modify: `apps/api/tests/test_career_profile_v2_integration.py`
- Optional inspect only: `apps/api/src/compass/pipeline/profile_parse_pipeline.py`

- [ ] **Step 1: Add a cache-hook integration test**

```python
from compass.pipeline.cache_hooks import run_profile_cache_hooks


def test_run_profile_cache_hooks_populates_career_profile_skill_links():
    profile = {
        "skills": ["Python", "SQL", "Power BI"],
        "languages": ["Français"],
    }

    result = run_profile_cache_hooks(cv_text=CV_TEXT, profile=profile)

    assert result.profile_hash
    assert "career_profile" in profile
    assert profile["career_profile"]["experiences"]
    assert any(exp.get("skill_links") for exp in profile["career_profile"]["experiences"])
    assert "experiences" in profile
```

- [ ] **Step 2: Run the targeted test**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
./.venv/bin/pytest apps/api/tests/test_career_profile_v2_integration.py::test_run_profile_cache_hooks_populates_career_profile_skill_links -q
```

Expected: PASS and confirm backend-authoritative population.

- [ ] **Step 3: Run the full targeted validation batch**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
./.venv/bin/pytest \
  apps/api/tests/test_skill_link_builder.py \
  apps/api/tests/test_career_profile_v2_integration.py \
  apps/api/tests/test_apply_pack_cv_engine.py \
  apps/api/tests/test_html_renderer.py -q
```

Expected: PASS with no matching tests touched.

- [ ] **Step 4: Commit**

```bash
cd /Users/akimguentas/Dev/elevia-compass
git add apps/api/tests/test_skill_link_builder.py apps/api/tests/test_career_profile_v2_integration.py
git commit -m "test: validate backend skill link structuring flow"
```

### Task 5: Request Code Review Before Merge

**Files:**
- Review scope: `apps/api/src/compass/structuring/skill_link_builder.py`
- Review scope: `apps/api/src/documents/career_profile.py`
- Review scope: `apps/api/src/compass/pipeline/cache_hooks.py`
- Review scope: `apps/api/tests/test_skill_link_builder.py`
- Review scope: `apps/api/tests/test_career_profile_v2_integration.py`
- Review scope: `apps/api/tests/test_apply_pack_cv_engine.py`
- Review scope: `apps/api/tests/test_html_renderer.py`

- [ ] **Step 1: Capture the review range**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
BASE_SHA=$(git rev-parse HEAD~4)
HEAD_SHA=$(git rev-parse HEAD)
echo "$BASE_SHA $HEAD_SHA"
```

Expected: prints two SHAs covering the structuring-agent work.

- [ ] **Step 2: Request review with the Superpowers reviewer**

Use the reviewer with:

```text
WHAT_WAS_IMPLEMENTED: Backend-authoritative skill link structuring after parsing and canonical mapping, persisted into career_profile and propagated to downstream CV consumers.
PLAN_OR_REQUIREMENTS: docs/superpowers/plans/2026-04-15-skill-link-structuring-agent.md
BASE_SHA: <BASE_SHA>
HEAD_SHA: <HEAD_SHA>
DESCRIPTION: Deterministic skill-link builder, pipeline injection, persistence, stats logging, and regression coverage.
```

- [ ] **Step 3: Fix all Critical or Important issues before merge**

Run:

```bash
cd /Users/akimguentas/Dev/elevia-compass
./.venv/bin/pytest \
  apps/api/tests/test_skill_link_builder.py \
  apps/api/tests/test_career_profile_v2_integration.py \
  apps/api/tests/test_apply_pack_cv_engine.py \
  apps/api/tests/test_html_renderer.py -q
```

Expected: PASS after review fixes.

- [ ] **Step 4: Final commit after review fixes**

```bash
cd /Users/akimguentas/Dev/elevia-compass
git add apps/api/src/compass/structuring/skill_link_builder.py apps/api/src/documents/career_profile.py apps/api/src/compass/pipeline/cache_hooks.py apps/api/tests/test_skill_link_builder.py apps/api/tests/test_career_profile_v2_integration.py apps/api/tests/test_apply_pack_cv_engine.py apps/api/tests/test_html_renderer.py
git commit -m "fix: address review feedback for skill link structuring"
```
